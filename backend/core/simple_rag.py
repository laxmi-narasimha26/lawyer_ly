"""
Simple RAG Pipeline for Local Development
"""

from typing import List, Dict, Any
from dataclasses import dataclass
import time
import uuid

from services.local_openai_service import local_openai_service

@dataclass
class RAGResponse:
    answer: str
    citations: List[Dict[str, Any]]
    retrieved_chunks: List[Dict[str, Any]]
    processing_time: float
    token_usage: Dict[str, int]
    confidence_score: float
    query_id: str

class SimpleRAGPipeline:
    """Simple RAG pipeline for testing"""
    
    def __init__(self):
        self.openai_service = local_openai_service
    
    async def process_query(
        self,
        query: str,
        user_id: str,
        mode: str = "qa",
        conversation_context: List[Dict[str, str]] = None
    ) -> RAGResponse:
        """Process a query and return response"""
        start_time = time.time()
        
        # Build messages
        messages = []
        
        # System message
        messages.append({
            "role": "system",
            "content": "You are an expert Indian legal AI assistant. Provide accurate, well-cited answers about Indian law."
        })
        
        # Add conversation context if provided
        if conversation_context:
            messages.extend(conversation_context[-10:])  # Last 10 messages
        
        # Add current query
        messages.append({
            "role": "user",
            "content": query
        })
        
        # Generate response
        response = await self.openai_service.generate_response(
            messages=messages,
            mode=mode
        )
        
        processing_time = time.time() - start_time
        
        return RAGResponse(
            answer=response["content"],
            citations=[],  # Simplified for now
            retrieved_chunks=[],
            processing_time=processing_time,
            token_usage=response["usage"],
            confidence_score=0.8,
            query_id=str(uuid.uuid4())
        )

# Global instance
rag_pipeline = SimpleRAGPipeline()
