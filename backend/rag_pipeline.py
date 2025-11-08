"""
Retrieval-Augmented Generation (RAG) Pipeline
Core component for semantic search and answer generation
"""
import structlog
from typing import List, Optional, Dict
import time
import asyncio
from openai import AsyncAzureOpenAI
import tiktoken

from config import settings
from models import QueryResponse, Citation, QueryMode, ConversationMessage
from vector_store import VectorStore
from prompt_templates import PromptTemplates
from cache_manager import CacheManager

logger = structlog.get_logger()

class RAGPipeline:
    def __init__(self):
        self.client = AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        self.vector_store = VectorStore()
        self.prompt_templates = PromptTemplates()
        self.cache = CacheManager()
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    async def process_query(
        self,
        query: str,
        mode: QueryMode,
        document_ids: Optional[List[str]],
        user_id: str,
        conversation_history: Optional[List[ConversationMessage]],
        db
    ) -> QueryResponse:
        """
        Main RAG pipeline processing
        """
        start_time = time.time()
        
        try:
            # Check cache
            cache_key = self.cache.generate_cache_key(query, mode, document_ids)
            cached_response = await self.cache.get(cache_key)
            if cached_response:
                logger.info("Cache hit", query_hash=cache_key[:8])
                return cached_response
            
            # Step 1: Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Step 2: Retrieve relevant chunks
            retrieved_chunks = await self._retrieve_relevant_chunks(
                query_embedding=query_embedding,
                query_text=query,
                document_ids=document_ids,
                user_id=user_id,
                db=db
            )
            
            # Step 3: Re-rank and filter chunks
            filtered_chunks = await self._rerank_chunks(query, retrieved_chunks)
            
            # Step 4: Construct prompt
            prompt = self._construct_prompt(
                query=query,
                chunks=filtered_chunks,
                mode=mode,
                conversation_history=conversation_history
            )
            
            # Step 5: Generate answer
            answer = await self._generate_answer(prompt, mode)
            
            # Step 6: Post-process and format citations
            formatted_answer, citations = await self._format_answer_with_citations(
                answer=answer,
                chunks=filtered_chunks
            )
            
            # Step 7: Verify answer (hallucination detection)
            verified_answer = await self._verify_answer(formatted_answer, citations)
            
            processing_time = time.time() - start_time
            
            response = QueryResponse(
                answer=verified_answer,
                citations=citations,
                mode=mode,
                processing_time=processing_time,
                metadata={
                    "chunks_retrieved": len(retrieved_chunks),
                    "chunks_used": len(filtered_chunks),
                    "tokens_used": self._count_tokens(prompt + answer)
                }
            )
            
            # Cache the response
            await self.cache.set(cache_key, response)
            
            return response
            
        except Exception as e:
            logger.error("RAG pipeline error", error=str(e), exc_info=True)
            raise
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text"""
        try:
            # Check cache
            cache_key = f"emb:{hash(text)}"
            cached_embedding = await self.cache.get(cache_key)
            if cached_embedding:
                return cached_embedding
            
            response = await self.client.embeddings.create(
                input=text,
                model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT
            )
            embedding = response.data[0].embedding
            
            # Cache embedding
            await self.cache.set(cache_key, embedding, ttl=3600)
            
            return embedding
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise
    
    async def _retrieve_relevant_chunks(
        self,
        query_embedding: List[float],
        query_text: str,
        document_ids: Optional[List[str]],
        user_id: str,
        db
    ) -> List[Dict]:
        """
        Retrieve relevant chunks using hybrid search
        Combines dense vector search with keyword filtering
        """
        try:
            # Perform vector similarity search
            vector_results = await self.vector_store.similarity_search(
                embedding=query_embedding,
                top_k=settings.TOP_K_RETRIEVAL * 2,  # Get more for re-ranking
                document_ids=document_ids,
                user_id=user_id,
                db=db
            )
            
            # Apply keyword boosting for legal terms
            boosted_results = await self._apply_keyword_boosting(
                query_text=query_text,
                results=vector_results
            )
            
            return boosted_results[:settings.TOP_K_RETRIEVAL]
            
        except Exception as e:
            logger.error("Retrieval failed", error=str(e))
            raise
    
    async def _apply_keyword_boosting(
        self,
        query_text: str,
        results: List[Dict]
    ) -> List[Dict]:
        """
        Boost results containing exact matches for case citations or section numbers
        """
        import re
        
        # Extract potential case citations and section numbers
        case_pattern = r'\b\d{4}\s+\w+\s+\d+\b'
        section_pattern = r'\bSection\s+\d+[A-Z]?\b'
        
        case_matches = re.findall(case_pattern, query_text, re.IGNORECASE)
        section_matches = re.findall(section_pattern, query_text, re.IGNORECASE)
        
        for result in results:
            boost_score = 0
            text = result.get('text', '')
            
            # Boost if contains exact case citation
            for case in case_matches:
                if case.lower() in text.lower():
                    boost_score += 0.2
            
            # Boost if contains exact section number
            for section in section_matches:
                if section.lower() in text.lower():
                    boost_score += 0.15
            
            result['relevance_score'] = result.get('relevance_score', 0) + boost_score
        
        # Re-sort by boosted scores
        results.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return results
    
    async def _rerank_chunks(self, query: str, chunks: List[Dict]) -> List[Dict]:
        """
        Re-rank retrieved chunks for better relevance
        Filter out low-quality chunks
        """
        filtered = []
        
        for chunk in chunks:
            text = chunk.get('text', '')
            
            # Filter out boilerplate or very short chunks
            if len(text.strip()) < 50:
                continue
            
            # Filter out chunks with very low relevance
            if chunk.get('relevance_score', 0) < 0.3:
                continue
            
            filtered.append(chunk)
        
        return filtered
    
    def _construct_prompt(
        self,
        query: str,
        chunks: List[Dict],
        mode: QueryMode,
        conversation_history: Optional[List[ConversationMessage]]
    ) -> str:
        """
        Construct the prompt for the LLM
        """
        # Format retrieved context
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_name = chunk.get('source_name', 'Unknown')
            text = chunk.get('text', '')
            context_parts.append(f"[Doc{i}] {source_name}:\n{text}\n")
        
        context = "\n".join(context_parts)
        
        # Get appropriate template based on mode
        if mode == QueryMode.QA:
            template = self.prompt_templates.get_qa_template()
        elif mode == QueryMode.DRAFTING:
            template = self.prompt_templates.get_drafting_template()
        else:  # SUMMARIZATION
            template = self.prompt_templates.get_summarization_template()
        
        # Include conversation history if provided
        history_text = ""
        if conversation_history:
            history_parts = []
            for msg in conversation_history[-5:]:  # Last 5 exchanges
                history_parts.append(f"{msg.role}: {msg.content}")
            history_text = "\n".join(history_parts)
        
        # Fill template
        prompt = template.format(
            context=context,
            history=history_text,
            query=query
        )
        
        return prompt
    
    async def _generate_answer(self, prompt: str, mode: QueryMode) -> str:
        """
        Generate answer using Azure OpenAI
        """
        try:
            # Set temperature based on mode
            temperature = (
                settings.TEMPERATURE_CREATIVE if mode == QueryMode.DRAFTING
                else settings.TEMPERATURE_FACTUAL
            )
            
            response = await self.client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "system", "content": self.prompt_templates.get_system_message()},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=2000
            )
            
            answer = response.choices[0].message.content
            return answer
            
        except Exception as e:
            logger.error("Answer generation failed", error=str(e))
            raise
    
    async def _format_answer_with_citations(
        self,
        answer: str,
        chunks: List[Dict]
    ) -> tuple[str, List[Citation]]:
        """
        Format answer and extract citations
        """
        import re
        
        citations = []
        formatted_answer = answer
        
        # Find citation markers like [Doc1], [Doc2], etc.
        citation_pattern = r'\[Doc(\d+)\]'
        matches = re.finditer(citation_pattern, answer)
        
        citation_map = {}
        for match in matches:
            doc_num = int(match.group(1))
            if 1 <= doc_num <= len(chunks):
                chunk = chunks[doc_num - 1]
                
                citation_id = f"cit_{hash(chunk.get('id', ''))}"
                
                citation = Citation(
                    id=citation_id,
                    source_name=chunk.get('source_name', 'Unknown'),
                    source_type=chunk.get('source_type', 'unknown'),
                    reference=self._format_citation_reference(chunk),
                    text_snippet=chunk.get('text', '')[:200] + "...",
                    relevance_score=chunk.get('relevance_score', 0)
                )
                
                citations.append(citation)
                citation_map[match.group(0)] = f"[{len(citations)}]"
        
        # Replace [Doc1] with [1], etc.
        for old, new in citation_map.items():
            formatted_answer = formatted_answer.replace(old, new)
        
        return formatted_answer, citations
    
    def _format_citation_reference(self, chunk: Dict) -> str:
        """
        Format citation according to Indian legal conventions
        """
        source_type = chunk.get('source_type', '')
        source_name = chunk.get('source_name', '')
        metadata = chunk.get('metadata', {})
        
        if source_type == 'case_law':
            # Format: Case Name, Year Court Citation
            year = metadata.get('year', '')
            court = metadata.get('court', '')
            citation = metadata.get('citation', '')
            return f"{source_name}, {year} {court} {citation}"
        
        elif source_type == 'statute':
            # Format: Act Name, Year, Section X
            section = metadata.get('section', '')
            return f"{source_name}, Section {section}"
        
        else:
            return source_name
    
    async def _verify_answer(self, answer: str, citations: List[Citation]) -> str:
        """
        Verify answer for hallucinations
        Add disclaimers if needed
        """
        # Basic verification: check if answer makes claims without citations
        sentences = answer.split('.')
        
        has_unsupported_claims = False
        for sentence in sentences:
            # Check if sentence makes a factual claim but has no citation
            if len(sentence.strip()) > 20 and '[' not in sentence:
                # Simple heuristic: if it contains legal keywords, it might need citation
                legal_keywords = ['court', 'held', 'section', 'act', 'law', 'judgment']
                if any(keyword in sentence.lower() for keyword in legal_keywords):
                    has_unsupported_claims = True
                    break
        
        if has_unsupported_claims and len(citations) == 0:
            answer += "\n\n*Note: This answer is based on general legal knowledge. Please verify with authoritative sources.*"
        
        return answer
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))
    
    async def get_citation_text(
        self,
        citation_id: str,
        user_id: str,
        db
    ) -> str:
        """
        Retrieve full text for a citation
        """
        try:
            text = await self.vector_store.get_chunk_by_id(
                chunk_id=citation_id,
                user_id=user_id,
                db=db
            )
            return text
        except Exception as e:
            logger.error("Failed to retrieve citation text", error=str(e))
            raise
