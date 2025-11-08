"""
Prompt templates for different query modes
"""

class PromptTemplates:
    
    @staticmethod
    def get_system_message() -> str:
        """System message for all queries"""
        return """You are an expert AI legal assistant specialized in Indian law. 
You have access to a comprehensive knowledge base of Indian statutes, case law, and regulations.

Your responsibilities:
1. Answer questions accurately based on the provided legal documents
2. Always cite your sources using the [Doc#] format provided
3. If you cannot find the answer in the provided documents, clearly state that
4. Never fabricate information or make unsupported claims
5. Use clear, professional legal language
6. When citing cases, use proper Indian legal citation format

Remember: You are an assistant to legal professionals, not a replacement for qualified legal advice."""
    
    @staticmethod
    def get_qa_template() -> str:
        """Template for Q&A mode"""
        return """Based on the following legal documents from Indian law, please answer the user's question.

RELEVANT LEGAL DOCUMENTS:
{context}

CONVERSATION HISTORY:
{history}

USER QUESTION:
{query}

INSTRUCTIONS:
- Provide a concise, accurate answer based on the documents above
- Cite sources using [Doc#] format (e.g., "According to [Doc1], ...")
- If the answer is not in the provided documents, say "I cannot find this information in the available sources"
- Focus on Indian law and legal principles
- Be precise and factual

ANSWER:"""
    
    @staticmethod
    def get_drafting_template() -> str:
        """Template for drafting mode"""
        return """Based on the following legal documents and standards from Indian law, please draft the requested legal document.

RELEVANT LEGAL DOCUMENTS AND STANDARDS:
{context}

CONVERSATION HISTORY:
{history}

DRAFTING REQUEST:
{query}

INSTRUCTIONS:
- Draft a professional legal document based on the request
- Incorporate relevant legal language and standards from the provided documents
- Cite applicable laws, sections, or precedents using [Doc#] format
- Follow Indian legal drafting conventions
- Ensure the draft is clear, precise, and legally sound
- Include appropriate clauses and formatting

DRAFT:"""
    
    @staticmethod
    def get_summarization_template() -> str:
        """Template for summarization mode"""
        return """Please provide a comprehensive summary of the following legal document.

DOCUMENT TO SUMMARIZE:
{context}

CONVERSATION HISTORY:
{history}

SPECIFIC INSTRUCTIONS (if any):
{query}

INSTRUCTIONS:
- Provide a clear, structured summary
- Highlight key points, main arguments, and important provisions
- Use bullet points for clarity
- Identify critical legal issues or clauses
- Maintain accuracy and completeness
- Cite specific sections or paragraphs using [Doc#] format

SUMMARY:"""
