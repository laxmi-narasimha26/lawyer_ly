"""
Enhanced RAG Pipeline with Conversation Context
Integrates conversation history and context management for ChatGPT-like experience
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
import json

from services.local_openai_service import local_openai_service
from services.conversation_manager import conversation_manager
from core.vector_search import VectorSearch
from core.citation_manager import CitationManager
from core.hallucination_detector import HallucinationDetector
from utils.text_processing import TextProcessor
from utils.monitoring import log_rag_metrics
from config.local_settings import RAG_CONFIG

@dataclass
class RAGResponse:
    answer: str
    citations: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]]
    conversation_context_used: bool
    processing_time: float
    token_usage: Dict[str, int]
    confidence_score: float
    query_id: str

class EnhancedRAGPipeline:
    """
    Enhanced RAG Pipeline with conversation context management
    Features:
    - Conversation history integration
    - Context-aware retrieval
    - Multi-turn conversation support
    - Intelligent context window management
    - Citation verification with context
    """
    
    def __init__(self):
        self.openai_service = local_openai_service
        self.vector_search = VectorSearch()
        self.citation_manager = CitationManager()
        self.hallucination_detector = HallucinationDetector()
        self.text_processor = TextProcessor()
        
        # Configuration
        self.max_context_length = RAG_CONFIG["max_context_length"]
        self.chunk_size = RAG_CONFIG["chunk_size"]
        self.citation_format = RAG_CONFIG["citation_format"]
        
    async def process_query(
        self,
        query: str,
        user_id: str,
        mode: str = "qa",
        conversation_context: Optional[List[Dict[str, str]]] = None,
        document_filters: Optional[Dict[str, Any]] = None
    ) -> RAGResponse:
        """
        Process a query with full conversation context support
        """
        start_time = datetime.now()
        query_id = f"query_{int(start_time.timestamp())}"
        
        try:
            # Step 1: Enhance query with conversation context
            enhanced_query = await self._enhance_query_with_context(
                query, conversation_context
            )
            
            # Step 2: Retrieve relevant chunks
            retrieved_chunks = await self.vector_search.hybrid_search(
                query=enhanced_query,
                limit=5,
                filters=document_filters,
                user_id=user_id
            )
            
            # Step 3: Build context-aware prompt
            prompt_messages = await self._build_context_aware_prompt(
                original_query=query,
                enhanced_query=enhanced_query,
                retrieved_chunks=retrieved_chunks,
                conversation_context=conversation_context,
                mode=mode
            )
            
            # Step 4: Generate response
            llm_response = await self.openai_service.generate_response(
                messages=prompt_messages,
                mode=mode
            )
            
            # Step 5: Extract and format citations
            citations = await self.citation_manager.extract_citations(
                response_text=llm_response["content"],
                retrieved_chunks=retrieved_chunks,
                format_style=self.citation_format
            )
            
            # Step 6: Calculate metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Step 7: Create response
            rag_response = RAGResponse(
                answer=llm_response["content"],
                citations=citations,
                retrieved_chunks=retrieved_chunks,
                conversation_context_used=conversation_context is not None and len(conversation_context) > 0,
                processing_time=processing_time,
                token_usage=llm_response["usage"],
                confidence_score=await self._calculate_confidence_score(
                    llm_response["content"], retrieved_chunks, citations
                ),
                query_id=query_id
            )
            
            # Step 8: Log metrics
            await log_rag_metrics(
                query=query,
                response=rag_response,
                user_id=user_id,
                mode=mode
            )
            
            return rag_response
            
        except Exception as e:
            # Log error and return error response
            await log_rag_metrics(
                query=query,
                response=None,
                user_id=user_id,
                mode=mode,
                error=str(e)
            )
            raise
    
    async def _enhance_query_with_context(
        self,
        query: str,
        conversation_context: Optional[List[Dict[str, str]]]
    ) -> str:
        """
        Enhance the query using conversation context for better retrieval
        """
        if not conversation_context or len(conversation_context) == 0:
            return query
        
        # Extract key legal terms and entities from conversation history
        context_text = ""
        for msg in conversation_context[-5:]:  # Use last 5 messages
            if msg["role"] == "user":
                context_text += f"Previous question: {msg['content']}\n"
            elif msg["role"] == "assistant":
                # Extract key legal concepts from previous answers
                key_concepts = await self._extract_legal_concepts(msg['content'])
                if key_concepts:
                    context_text += f"Related concepts: {', '.join(key_concepts)}\n"
        
        # Create enhanced query
        if context_text:
            enhanced_query = f"""
Context from conversation:
{context_text}

Current question: {query}

Enhanced search query combining context and current question: {query}
"""
            return enhanced_query
        
        return query
    
    async def _extract_legal_concepts(self, text: str) -> List[str]:
        """Extract key legal concepts from text"""
        legal_keywords = [
            "contract", "agreement", "liability", "damages", "breach", "tort",
            "criminal", "civil", "constitutional", "property", "divorce", "marriage",
            "employment", "labor", "intellectual property", "patent", "trademark",
            "company", "corporate", "tax", "GST", "limitation", "procedure",
            "section", "act", "article", "clause", "provision", "statute",
            "judgment", "case law", "precedent", "ruling", "court", "supreme court"
        ]
        
        text_lower = text.lower()
        found_concepts = []
        
        for keyword in legal_keywords:
            if keyword in text_lower:
                found_concepts.append(keyword)
        
        return found_concepts[:5]  # Return top 5 concepts
    
    async def _build_context_aware_prompt(
        self,
        original_query: str,
        enhanced_query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_context: Optional[List[Dict[str, str]]],
        mode: str
    ) -> List[Dict[str, str]]:
        """
        Build a context-aware prompt that includes conversation history
        """
        messages = []
        
        # System message based on mode
        system_message = await self._get_system_message(mode)
        messages.append({"role": "system", "content": system_message})
        
        # Add relevant conversation context (limited to avoid token overflow)
        if conversation_context:
            # Include last few exchanges for context
            context_messages = conversation_context[-6:]  # Last 3 exchanges (6 messages)
            
            # Add context with a separator
            if context_messages:
                context_summary = "Previous conversation context:\n"
                for msg in context_messages:
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                    context_summary += f"{role_label}: {msg['content'][:200]}...\n"
                
                messages.append({
                    "role": "system", 
                    "content": f"{context_summary}\n---\nNow answering the current question with this context in mind."
                })
        
        # Add retrieved legal context
        if retrieved_chunks:
            legal_context = "Relevant legal information:\n\n"
            for i, chunk in enumerate(retrieved_chunks):
                legal_context += f"Source {i+1}: {chunk['content']}\n"
                if chunk.get('metadata', {}).get('source_name'):
                    legal_context += f"From: {chunk['metadata']['source_name']}\n"
                legal_context += "\n"
            
            messages.append({"role": "system", "content": legal_context})
        
        # Add the current user query
        messages.append({"role": "user", "content": original_query})
        
        return messages
    
    async def _get_system_message(self, mode: str) -> str:
        """Get system message based on mode"""
        
        base_instructions = """You are an expert Indian legal AI assistant. You provide accurate, well-researched legal information based on Indian law, including statutes, case law, and legal procedures.

IMPORTANT GUIDELINES:
1. Always base your answers on the provided legal sources
2. Include proper citations in Indian legal format
3. If information is not available in the sources, clearly state this
4. Never speculate or provide information not supported by the sources
5. Consider the conversation context when relevant
6. Provide practical, actionable legal guidance when appropriate"""
        
        mode_specific = {
            "qa": """
MODE: Legal Q&A
- Provide clear, factual answers to legal questions
- Focus on accuracy and proper citation
- Explain legal concepts in accessible language
- Reference specific sections, cases, or provisions""",
            
            "drafting": """
MODE: Legal Drafting
- Help draft legal documents, clauses, and notices
- Use appropriate legal language and formatting
- Include necessary legal provisions and safeguards
- Ensure compliance with Indian legal requirements""",
            
            "summarization": """
MODE: Legal Summarization
- Provide concise summaries of legal documents or concepts
- Highlight key points and important provisions
- Maintain accuracy while being concise
- Structure information logically"""
        }
        
        return f"{base_instructions}\n\n{mode_specific.get(mode, mode_specific['qa'])}"
    
    async def _calculate_confidence_score(
        self,
        response: str,
        retrieved_chunks: List[Dict[str, Any]],
        citations: List[Dict[str, Any]]
    ) -> float:
        """
        Calculate confidence score based on various factors
        """
        score = 0.0
        
        # Factor 1: Number and quality of citations (40%)
        if citations:
            citation_score = min(len(citations) / 3, 1.0)  # Normalize to max 3 citations
            score += citation_score * 0.4
        
        # Factor 2: Relevance of retrieved chunks (30%)
        if retrieved_chunks:
            avg_relevance = sum(chunk.get('relevance_score', 0.5) for chunk in retrieved_chunks) / len(retrieved_chunks)
            score += avg_relevance * 0.3
        
        # Factor 3: Response length and detail (20%)
        response_length_score = min(len(response) / 500, 1.0)  # Normalize to 500 chars
        score += response_length_score * 0.2
        
        # Factor 4: Presence of legal terminology (10%)
        legal_terms = ["section", "act", "case", "court", "judgment", "provision", "clause"]
        legal_term_count = sum(1 for term in legal_terms if term.lower() in response.lower())
        legal_term_score = min(legal_term_count / 3, 1.0)
        score += legal_term_score * 0.1
        
        return min(score, 1.0)  # Ensure score doesn't exceed 1.0

# Global instance
enhanced_rag_pipeline = EnhancedRAGPipeline()