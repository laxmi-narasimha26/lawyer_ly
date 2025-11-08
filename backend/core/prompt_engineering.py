"""
Advanced prompt engineering for Indian Legal AI Assistant
Implements sophisticated prompt strategies as specified in the PDF
"""
from typing import List, Dict, Any, Optional
from enum import Enum
import structlog
from datetime import datetime

from database import QueryMode, DocumentType
from config import settings

logger = structlog.get_logger(__name__)

class PromptTemplate(Enum):
    """Prompt template types"""
    QA_FACTUAL = "qa_factual"
    QA_PROCEDURAL = "qa_procedural" 
    QA_CASE_LAW = "qa_case_law"
    QA_STATUTE = "qa_statute"
    DRAFTING_CONTRACT = "drafting_contract"
    DRAFTING_NOTICE = "drafting_notice"
    DRAFTING_PETITION = "drafting_petition"
    SUMMARIZATION_CASE = "summarization_case"
    SUMMARIZATION_DOCUMENT = "summarization_document"
    ANALYSIS_COMPARATIVE = "analysis_comparative"

class PromptEngineer:
    """
    Production-grade prompt engineering system
    
    Features:
    - Context-aware prompt construction
    - Legal domain-specific templates
    - Citation instruction integration
    - Hallucination prevention
    - Indian legal format compliance
    """
    
    def __init__(self):
        self.system_messages = self._initialize_system_messages()
        self.prompt_templates = self._initialize_prompt_templates()
        self.citation_instructions = self._initialize_citation_instructions()
        
        logger.info("Prompt engineering system initialized")
    
    def get_system_message(self, mode: QueryMode = QueryMode.QA) -> str:
        """Get system message based on query mode"""
        return self.system_messages.get(mode, self.system_messages[QueryMode.QA])
    
    async def build_prompt(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        mode: QueryMode,
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        query_intent: Optional[str] = None
    ) -> str:
        """
        Build comprehensive prompt with all context
        
        Args:
            query: User's legal query
            chunks: Retrieved document chunks
            mode: Query processing mode
            conversation_context: Previous conversation turns
            query_intent: Detected query intent
            
        Returns:
            Complete prompt for LLM
        """
        try:
            # Select appropriate template
            template_type = self._select_template(mode, query_intent, chunks)
            template = self.prompt_templates[template_type]
            
            # Format retrieved context
            formatted_context = self._format_context_chunks(chunks)
            
            # Format conversation history
            formatted_history = self._format_conversation_history(conversation_context)
            
            # Build complete prompt
            prompt = template.format(
                context=formatted_context,
                conversation_history=formatted_history,
                query=query,
                current_date=datetime.now().strftime("%B %d, %Y"),
                citation_instructions=self.citation_instructions[mode]
            )
            
            # Validate prompt length
            if len(prompt) > 15000:  # Approximate token limit check
                prompt = self._truncate_prompt(prompt, chunks)
            
            logger.debug(
                "Prompt built successfully",
                template_type=template_type.value,
                prompt_length=len(prompt),
                chunks_count=len(chunks)
            )
            
            return prompt
            
        except Exception as e:
            logger.error("Prompt building failed", error=str(e), exc_info=True)
            # Fallback to basic prompt
            return self._build_fallback_prompt(query, chunks, mode)
    
    def _initialize_system_messages(self) -> Dict[QueryMode, str]:
        """Initialize system messages for different modes"""
        return {
            QueryMode.QA: """You are an expert AI legal assistant specialized in Indian law with deep knowledge of the Indian Constitution, statutes, case law, and legal procedures. You serve as a research assistant to qualified lawyers and legal professionals.

CORE RESPONSIBILITIES:
1. Provide accurate, well-researched answers based on Indian legal sources
2. Always cite specific legal authorities (cases, statutes, sections, articles)
3. Use proper Indian legal citation format and terminology
4. Maintain the highest standards of legal accuracy and precision
5. Never fabricate or hallucinate legal information

CRITICAL GUIDELINES:
- Base all answers on the provided legal documents and established Indian law
- If information is not available in sources, clearly state "I cannot find this information in the available sources"
- Use formal legal language appropriate for legal professionals
- Distinguish between binding precedents and persuasive authorities
- Consider jurisdiction-specific variations (Central vs State law)
- Always include relevant disclaimers about legal advice

INDIAN LEGAL CONTEXT:
- Follow Indian legal citation conventions
- Recognize the hierarchy of Indian courts (Supreme Court, High Courts, District Courts)
- Understand the federal structure (Union and State jurisdictions)
- Apply principles of Indian jurisprudence and constitutional law""",

            QueryMode.DRAFTING: """You are an expert legal drafting assistant specialized in Indian legal documents. You help qualified lawyers create professional, legally sound documents following Indian legal conventions and best practices.

DRAFTING EXPERTISE:
1. Indian contract law and commercial agreements
2. Legal notices and formal communications
3. Writ petitions and court pleadings
4. Corporate legal documents
5. Compliance and regulatory filings

DRAFTING STANDARDS:
- Follow Indian legal drafting conventions and precedents
- Use precise legal terminology and formal language
- Include appropriate legal clauses and safeguards
- Ensure compliance with relevant Indian statutes
- Structure documents logically with proper numbering and formatting
- Include necessary recitals, definitions, and operative clauses

QUALITY REQUIREMENTS:
- All drafts must be legally sound and enforceable under Indian law
- Include relevant statutory references and legal authorities
- Ensure clarity, precision, and professional presentation
- Consider practical enforceability and commercial viability
- Maintain consistency with established legal precedents""",

            QueryMode.SUMMARIZATION: """You are an expert legal analyst specialized in summarizing complex Indian legal documents with precision and clarity for legal professionals.

SUMMARIZATION EXPERTISE:
1. Case law analysis and judgment summaries
2. Statutory interpretation and legislative analysis
3. Contract review and key clause identification
4. Legal research compilation
5. Regulatory compliance summaries

ANALYSIS STANDARDS:
- Extract key legal principles and holdings
- Identify critical facts and legal issues
- Highlight important precedents and authorities
- Summarize reasoning and judicial observations
- Note practical implications and applications
- Maintain legal accuracy and context

OUTPUT REQUIREMENTS:
- Structured, professional summaries
- Clear identification of legal issues and holdings
- Proper citation of authorities and sources
- Logical organization with headings and bullet points
- Concise yet comprehensive coverage of material points
- Professional language suitable for legal practitioners"""
        }
    
    def _initialize_prompt_templates(self) -> Dict[PromptTemplate, str]:
        """Initialize detailed prompt templates"""
        return {
            PromptTemplate.QA_FACTUAL: """Based on the following Indian legal authorities and documents, provide a comprehensive answer to the legal question.

LEGAL AUTHORITIES AND SOURCES:
{context}

CONVERSATION HISTORY:
{conversation_history}

CURRENT DATE: {current_date}

LEGAL QUESTION:
{query}

INSTRUCTIONS:
{citation_instructions}

Provide a detailed, accurate answer that:
1. Directly addresses the legal question
2. Cites specific legal authorities using proper Indian legal citation format
3. Explains the legal principles and their application
4. Considers relevant precedents and statutory provisions
5. Notes any jurisdictional variations or recent developments
6. Maintains professional legal language and structure

ANSWER:""",

            PromptTemplate.QA_CASE_LAW: """Analyze the following case law and legal authorities to answer the question about Indian jurisprudence.

CASE LAW AND JUDICIAL AUTHORITIES:
{context}

CONVERSATION HISTORY:
{conversation_history}

CURRENT DATE: {current_date}

CASE LAW QUESTION:
{query}

INSTRUCTIONS:
{citation_instructions}

Provide a comprehensive case law analysis that:
1. Identifies relevant judicial precedents and their holdings
2. Explains the ratio decidendi and obiter dicta
3. Traces the evolution of legal principles through cases
4. Distinguishes between binding and persuasive precedents
5. Notes any overruling or modification of earlier decisions
6. Considers the hierarchical value of different court decisions

CASE LAW ANALYSIS:""",

            PromptTemplate.QA_STATUTE: """Interpret the following statutory provisions and legal authorities to answer the question about Indian legislation.

STATUTORY PROVISIONS AND AUTHORITIES:
{context}

CONVERSATION HISTORY:
{conversation_history}

CURRENT DATE: {current_date}

STATUTORY QUESTION:
{query}

INSTRUCTIONS:
{citation_instructions}

Provide a detailed statutory interpretation that:
1. Identifies relevant statutory provisions and their scope
2. Explains the legislative intent and purpose
3. Analyzes the language and construction of provisions
4. Considers judicial interpretation of the statute
5. Notes any amendments or recent changes
6. Explains practical application and compliance requirements

STATUTORY INTERPRETATION:""",

            PromptTemplate.DRAFTING_CONTRACT: """Draft a professional legal document based on the following legal authorities and requirements.

RELEVANT LEGAL AUTHORITIES:
{context}

CONVERSATION HISTORY:
{conversation_history}

CURRENT DATE: {current_date}

DRAFTING REQUEST:
{query}

INSTRUCTIONS:
{citation_instructions}

Create a professional legal draft that:
1. Follows Indian legal drafting conventions and best practices
2. Includes appropriate legal clauses and safeguards
3. Ensures compliance with relevant Indian statutes
4. Uses precise legal terminology and formal language
5. Structures the document logically with proper formatting
6. Includes necessary recitals, definitions, and operative provisions
7. Considers enforceability under Indian law

LEGAL DRAFT:""",

            PromptTemplate.SUMMARIZATION_CASE: """Provide a comprehensive summary of the following legal case and related authorities.

CASE MATERIALS AND AUTHORITIES:
{context}

CONVERSATION HISTORY:
{conversation_history}

CURRENT DATE: {current_date}

SUMMARIZATION REQUEST:
{query}

INSTRUCTIONS:
{citation_instructions}

Provide a structured case summary that includes:
1. **Case Details**: Court, judges, citation, date
2. **Facts**: Key factual background and parties
3. **Legal Issues**: Primary legal questions presented
4. **Holdings**: Court's decisions and rulings
5. **Reasoning**: Legal analysis and judicial observations
6. **Precedential Value**: Binding nature and scope
7. **Practical Implications**: Impact on legal practice

CASE SUMMARY:""",

            PromptTemplate.SUMMARIZATION_DOCUMENT: """Analyze and summarize the following legal document with focus on key provisions and implications.

DOCUMENT CONTENT AND AUTHORITIES:
{context}

CONVERSATION HISTORY:
{conversation_history}

CURRENT DATE: {current_date}

DOCUMENT ANALYSIS REQUEST:
{query}

INSTRUCTIONS:
{citation_instructions}

Provide a comprehensive document summary that includes:
1. **Document Overview**: Type, parties, purpose, date
2. **Key Provisions**: Important clauses and terms
3. **Legal Framework**: Applicable laws and regulations
4. **Rights and Obligations**: Party responsibilities and entitlements
5. **Risk Analysis**: Potential legal issues or concerns
6. **Compliance Requirements**: Regulatory obligations
7. **Recommendations**: Suggested actions or considerations

DOCUMENT SUMMARY:"""
        }
    
    def _initialize_citation_instructions(self) -> Dict[QueryMode, str]:
        """Initialize citation instructions for different modes"""
        return {
            QueryMode.QA: """CITATION REQUIREMENTS:
- Cite all legal authorities using proper Indian legal citation format
- Use [Doc1], [Doc2] format to reference provided sources
- Include case names, years, courts, and citation numbers
- For statutes: Act name, year, section/article numbers
- For regulations: Notification number, date, issuing authority
- Always verify citations against provided sources
- If citing established law not in sources, clearly indicate general legal knowledge""",

            QueryMode.DRAFTING: """DRAFTING CITATION REQUIREMENTS:
- Reference relevant statutory provisions with full citations
- Include applicable case law supporting drafted clauses
- Cite regulatory requirements and compliance standards
- Use [Doc1], [Doc2] format for provided source materials
- Ensure all legal references are accurate and current
- Include explanatory notes for complex legal provisions""",

            QueryMode.SUMMARIZATION: """SUMMARIZATION CITATION REQUIREMENTS:
- Maintain all original citations from source documents
- Use [Doc1], [Doc2] format to reference source materials
- Preserve case citations, statutory references, and authorities
- Note the source of each summarized point
- Maintain accuracy of all legal references and citations
- Clearly distinguish between different types of authorities"""
        }
    
    def _select_template(
        self,
        mode: QueryMode,
        query_intent: Optional[str],
        chunks: List[Dict[str, Any]]
    ) -> PromptTemplate:
        """Select the most appropriate prompt template"""
        
        # Analyze document types in chunks
        doc_types = [chunk.get('source_type', '') for chunk in chunks]
        
        if mode == QueryMode.QA:
            if query_intent == 'case_law' or 'case_law' in doc_types:
                return PromptTemplate.QA_CASE_LAW
            elif query_intent == 'statute' or 'statute' in doc_types:
                return PromptTemplate.QA_STATUTE
            else:
                return PromptTemplate.QA_FACTUAL
        
        elif mode == QueryMode.DRAFTING:
            # Could be enhanced to detect specific drafting types
            return PromptTemplate.DRAFTING_CONTRACT
        
        elif mode == QueryMode.SUMMARIZATION:
            if 'case_law' in doc_types:
                return PromptTemplate.SUMMARIZATION_CASE
            else:
                return PromptTemplate.SUMMARIZATION_DOCUMENT
        
        # Default fallback
        return PromptTemplate.QA_FACTUAL
    
    def _format_context_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into structured context"""
        if not chunks:
            return "No relevant legal authorities found in the knowledge base."
        
        formatted_chunks = []
        
        for i, chunk in enumerate(chunks, 1):
            # Build chunk header with metadata
            header_parts = [f"[Doc{i}]"]
            
            if chunk.get('source_name'):
                header_parts.append(f"Source: {chunk['source_name']}")
            
            if chunk.get('source_type'):
                header_parts.append(f"Type: {chunk['source_type'].title()}")
            
            if chunk.get('section_number'):
                header_parts.append(f"Section: {chunk['section_number']}")
            
            if chunk.get('page_range'):
                header_parts.append(f"Pages: {chunk['page_range']}")
            
            header = " | ".join(header_parts)
            
            # Format the chunk
            formatted_chunk = f"{header}\n{'-' * len(header)}\n{chunk['text']}\n"
            formatted_chunks.append(formatted_chunk)
        
        return "\n".join(formatted_chunks)
    
    def _format_conversation_history(
        self,
        conversation_context: Optional[List[Dict[str, Any]]]
    ) -> str:
        """Format conversation history for context"""
        if not conversation_context:
            return "No previous conversation context."
        
        formatted_history = []
        for turn in conversation_context[-6:]:  # Last 6 turns
            role = turn.get('role', 'unknown')
            content = turn.get('content', '')
            
            if role == 'user':
                formatted_history.append(f"Previous Question: {content}")
            elif role == 'assistant':
                # Truncate long responses
                truncated_content = content[:200] + "..." if len(content) > 200 else content
                formatted_history.append(f"Previous Answer: {truncated_content}")
        
        return "\n".join(formatted_history) if formatted_history else "No previous conversation context."
    
    def _truncate_prompt(self, prompt: str, chunks: List[Dict[str, Any]]) -> str:
        """Truncate prompt if it's too long while preserving important parts"""
        # Keep system message and query, truncate context
        lines = prompt.split('\n')
        
        # Find context section
        context_start = -1
        context_end = -1
        
        for i, line in enumerate(lines):
            if 'LEGAL AUTHORITIES' in line or 'CONTEXT' in line:
                context_start = i
            elif context_start != -1 and ('QUESTION:' in line or 'REQUEST:' in line):
                context_end = i
                break
        
        if context_start != -1 and context_end != -1:
            # Keep only top chunks
            top_chunks = chunks[:3]  # Reduce to top 3 chunks
            truncated_context = self._format_context_chunks(top_chunks)
            
            # Rebuild prompt with truncated context
            new_lines = lines[:context_start+2] + [truncated_context] + lines[context_end:]
            return '\n'.join(new_lines)
        
        return prompt
    
    def _build_fallback_prompt(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        mode: QueryMode
    ) -> str:
        """Build a simple fallback prompt if main prompt building fails"""
        context = self._format_context_chunks(chunks)
        
        return f"""You are an expert Indian legal assistant. Answer the following question based on the provided legal sources.

LEGAL SOURCES:
{context}

QUESTION: {query}

Provide an accurate answer with proper citations. If the answer is not in the sources, say so clearly.

ANSWER:"""
    
    def validate_prompt(self, prompt: str) -> Dict[str, Any]:
        """Validate prompt quality and structure"""
        validation_results = {
            'is_valid': True,
            'warnings': [],
            'length': len(prompt),
            'estimated_tokens': len(prompt) // 4  # Rough estimate
        }
        
        # Check length
        if len(prompt) > 20000:
            validation_results['warnings'].append("Prompt is very long, may exceed token limits")
        
        # Check for required sections
        required_sections = ['QUESTION:', 'INSTRUCTIONS:', 'ANSWER:']
        for section in required_sections:
            if section not in prompt:
                validation_results['warnings'].append(f"Missing required section: {section}")
        
        # Check for citation instructions
        if 'citation' not in prompt.lower():
            validation_results['warnings'].append("No citation instructions found")
        
        if validation_results['warnings']:
            validation_results['is_valid'] = False
        
        return validation_results