"""
Local OpenAI Service
Direct integration with OpenAI API for local development
"""

import openai
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import time

from config.local_settings import OPENAI_CONFIG
from utils.monitoring import log_api_call
from utils.exceptions import LegalAIException

class LocalOpenAIService:
    """
    OpenAI service for local development with proper error handling and monitoring
    """
    
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=OPENAI_CONFIG["api_key"],
            timeout=OPENAI_CONFIG.get("timeout", 30)
        )
        
        self.model = OPENAI_CONFIG["model"]
        self.embedding_model = OPENAI_CONFIG["embedding_model"]
        self.max_tokens = OPENAI_CONFIG["max_tokens"]
        self.temperature = OPENAI_CONFIG["temperature"]
        
        # Rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # 100ms between requests
    
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        mode: str = "qa"
    ) -> Dict[str, Any]:
        """
        Generate response using OpenAI Chat Completions API
        """
        try:
            # Rate limiting
            await self._rate_limit()
            
            # Prepare parameters
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature or self._get_temperature_for_mode(mode),
                "max_tokens": max_tokens or self.max_tokens,
                "stream": False
            }
            
            start_time = time.time()
            
            # Make API call
            response = self.client.chat.completions.create(**params)
            
            processing_time = time.time() - start_time
            
            # Extract response data
            result = {
                "content": response.choices[0].message.content,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "processing_time": processing_time,
                "finish_reason": response.choices[0].finish_reason
            }
            
            # Log the API call
            await log_api_call(
                service="openai_chat",
                model=self.model,
                tokens_used=result["usage"]["total_tokens"],
                processing_time=processing_time,
                success=True
            )
            
            return result
            
        except openai.RateLimitError as e:
            await log_api_call("openai_chat", self.model, 0, 0, False, str(e))
            raise LegalAIException(f"OpenAI rate limit exceeded: {str(e)}")
            
        except openai.APIError as e:
            await log_api_call("openai_chat", self.model, 0, 0, False, str(e))
            raise LegalAIException(f"OpenAI API error: {str(e)}")
            
        except Exception as e:
            await log_api_call("openai_chat", self.model, 0, 0, False, str(e))
            raise LegalAIException(f"Error generating response: {str(e)}")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI Embeddings API
        """
        try:
            # Rate limiting
            await self._rate_limit()
            
            start_time = time.time()
            
            # Make API call
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            
            processing_time = time.time() - start_time
            
            # Extract embedding
            embedding = response.data[0].embedding
            
            # Log the API call
            await log_api_call(
                service="openai_embeddings",
                model=self.embedding_model,
                tokens_used=response.usage.total_tokens,
                processing_time=processing_time,
                success=True
            )
            
            return embedding
            
        except openai.RateLimitError as e:
            await log_api_call("openai_embeddings", self.embedding_model, 0, 0, False, str(e))
            raise LegalAIException(f"OpenAI rate limit exceeded: {str(e)}")
            
        except openai.APIError as e:
            await log_api_call("openai_embeddings", self.embedding_model, 0, 0, False, str(e))
            raise LegalAIException(f"OpenAI API error: {str(e)}")
            
        except Exception as e:
            await log_api_call("openai_embeddings", self.embedding_model, 0, 0, False, str(e))
            raise LegalAIException(f"Error generating embedding: {str(e)}")
    
    async def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch
        """
        try:
            # Rate limiting
            await self._rate_limit()
            
            start_time = time.time()
            
            # Make API call
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            
            processing_time = time.time() - start_time
            
            # Extract embeddings
            embeddings = [data.embedding for data in response.data]
            
            # Log the API call
            await log_api_call(
                service="openai_embeddings_batch",
                model=self.embedding_model,
                tokens_used=response.usage.total_tokens,
                processing_time=processing_time,
                success=True,
                metadata={"batch_size": len(texts)}
            )
            
            return embeddings
            
        except openai.RateLimitError as e:
            await log_api_call("openai_embeddings_batch", self.embedding_model, 0, 0, False, str(e))
            raise LegalAIException(f"OpenAI rate limit exceeded: {str(e)}")
            
        except openai.APIError as e:
            await log_api_call("openai_embeddings_batch", self.embedding_model, 0, 0, False, str(e))
            raise LegalAIException(f"OpenAI API error: {str(e)}")
            
        except Exception as e:
            await log_api_call("openai_embeddings_batch", self.embedding_model, 0, 0, False, str(e))
            raise LegalAIException(f"Error generating embeddings: {str(e)}")
    
    def _get_temperature_for_mode(self, mode: str) -> float:
        """Get appropriate temperature based on mode"""
        temperature_map = {
            "qa": 0.2,          # Low temperature for factual Q&A
            "drafting": 0.7,    # Higher temperature for creative drafting
            "summarization": 0.3 # Medium temperature for summarization
        }
        return temperature_map.get(mode, self.temperature)
    
    async def _rate_limit(self):
        """Simple rate limiting to avoid hitting API limits"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        
        self.last_request_time = time.time()
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection"""
        try:
            # Test with a simple completion
            response = await self.generate_response([
                {"role": "user", "content": "Hello, this is a test."}
            ])
            
            return {
                "status": "connected",
                "model": self.model,
                "embedding_model": self.embedding_model,
                "test_response_length": len(response["content"]),
                "tokens_used": response["usage"]["total_tokens"]
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "model": self.model,
                "embedding_model": self.embedding_model
            }

# Global instance
local_openai_service = LocalOpenAIService()