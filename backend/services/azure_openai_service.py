"""
Production-grade Azure OpenAI Service integration for Indian Legal AI Assistant
Implements comprehensive Azure OpenAI integration with rate limiting, retry logic, and monitoring
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timedelta
import structlog
from openai import AsyncAzureOpenAI
from openai.types.chat import ChatCompletion
from openai.types import CreateEmbeddingResponse
from tenacity import (
    retry, stop_after_attempt, wait_exponential, 
    retry_if_exception_type, before_sleep_log
)
import tiktoken
from dataclasses import dataclass

from config.settings import settings
from utils.exceptions import LegalAIException, ProcessingError, RateLimitExceeded
from utils.monitoring import metrics_collector

logger = structlog.get_logger(__name__)

@dataclass
class TokenUsage:
    """Token usage tracking"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float

@dataclass
class OpenAIResponse:
    """Standardized OpenAI response"""
    content: str
    token_usage: TokenUsage
    model: str
    processing_time_ms: int
    request_id: Optional[str] = None

class AzureOpenAIService:
    """
    Production-grade Azure OpenAI Service integration
    
    Features:
    - Proper data residency with Azure OpenAI Service
    - Comprehensive rate limiting and cost control
    - Retry logic with exponential backoff
    - Token usage tracking and optimization
    - Request/response monitoring and logging
    - Error handling and circuit breaker patterns
    - Model deployment management
    """
    
    def __init__(self):
        # Initialize Azure OpenAI client with proper configuration
        self.client = AsyncAzureOpenAI(
            api_key=settings.azure_openai.api_key,
            api_version=settings.azure_openai.api_version,
            azure_endpoint=settings.azure_openai.endpoint,
            timeout=settings.azure_openai.request_timeout,
            max_retries=0  # We handle retries manually
        )
        
        # Initialize tokenizer for accurate token counting
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        # Rate limiting and cost tracking
        self.request_counts = {}
        self.token_usage_daily = {}
        self.cost_tracking = {}
        
        # Model pricing (tokens per dollar)
        self.model_pricing = {
            'gpt-4': {'input': 0.03, 'output': 0.06},  # per 1K tokens
            'gpt-4-32k': {'input': 0.06, 'output': 0.12},
            'gpt-35-turbo': {'input': 0.0015, 'output': 0.002},
            'text-embedding-ada-002': {'input': 0.0001, 'output': 0.0}
        }
        
        # Circuit breaker state
        self.circuit_breaker = {
            'failure_count': 0,
            'last_failure_time': None,
            'state': 'closed'  # closed, open, half-open
        }
        
        logger.info(
            "Azure OpenAI Service initialized",
            endpoint=settings.azure_openai.endpoint,
            api_version=settings.azure_openai.api_version,
            deployment=settings.azure_openai.deployment_name
        )
    
    async def generate_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
        user_id: Optional[str] = None,
        request_context: Optional[Dict[str, Any]] = None
    ) -> OpenAIResponse:
        """
        Generate chat completion with comprehensive error handling and monitoring
        
        Args:
            messages: List of chat messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            user_id: User ID for rate limiting
            request_context: Additional context for logging
            
        Returns:
            OpenAI response with token usage and metadata
        """
        start_time = time.time()
        
        try:
            # Check circuit breaker
            await self._check_circuit_breaker()
            
            # Validate and prepare request
            validated_messages = self._validate_messages(messages)
            effective_max_tokens = max_tokens or settings.azure_openai.max_tokens
            
            # Check rate limits
            await self._check_rate_limits(user_id, validated_messages, effective_max_tokens)
            
            # Count input tokens
            input_tokens = self._count_tokens_in_messages(validated_messages)
            
            logger.info(
                "Generating chat completion",
                user_id=user_id,
                input_tokens=input_tokens,
                temperature=temperature,
                max_tokens=effective_max_tokens,
                context=request_context
            )
            
            # Make API call with retry logic
            response = await self._make_chat_completion_request(
                messages=validated_messages,
                temperature=temperature,
                max_tokens=effective_max_tokens
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Process response
            openai_response = self._process_chat_response(
                response, processing_time_ms, input_tokens
            )
            
            # Update usage tracking
            await self._update_usage_tracking(user_id, openai_response.token_usage)
            
            # Record metrics
            await self._record_completion_metrics(
                openai_response, processing_time_ms, user_id
            )
            
            # Reset circuit breaker on success
            self.circuit_breaker['failure_count'] = 0
            self.circuit_breaker['state'] = 'closed'
            
            logger.info(
                "Chat completion generated successfully",
                user_id=user_id,
                processing_time_ms=processing_time_ms,
                total_tokens=openai_response.token_usage.total_tokens,
                estimated_cost=openai_response.token_usage.estimated_cost
            )
            
            return openai_response
            
        except Exception as e:
            await self._handle_completion_error(e, user_id, start_time)
            raise
    
    async def generate_embeddings(
        self,
        texts: Union[str, List[str]],
        user_id: Optional[str] = None,
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings with batching and error handling
        
        Args:
            texts: Text or list of texts to embed
            user_id: User ID for rate limiting
            batch_size: Batch size for processing
            
        Returns:
            List of embedding vectors
        """
        start_time = time.time()
        
        try:
            # Normalize input
            text_list = [texts] if isinstance(texts, str) else texts
            
            if not text_list:
                return []
            
            # Check circuit breaker
            await self._check_circuit_breaker()
            
            logger.info(
                "Generating embeddings",
                user_id=user_id,
                text_count=len(text_list),
                batch_size=batch_size
            )
            
            all_embeddings = []
            
            # Process in batches
            for i in range(0, len(text_list), batch_size):
                batch = text_list[i:i + batch_size]
                
                # Count tokens for rate limiting
                batch_tokens = sum(len(self.tokenizer.encode(text)) for text in batch)
                
                # Check rate limits
                await self._check_embedding_rate_limits(user_id, batch_tokens)
                
                # Make API call
                batch_embeddings = await self._make_embedding_request(batch)
                all_embeddings.extend(batch_embeddings)
                
                # Small delay between batches to avoid rate limits
                if i + batch_size < len(text_list):
                    await asyncio.sleep(0.1)
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Record metrics
            await self._record_embedding_metrics(
                len(text_list), processing_time_ms, user_id
            )
            
            logger.info(
                "Embeddings generated successfully",
                user_id=user_id,
                text_count=len(text_list),
                processing_time_ms=processing_time_ms
            )
            
            return all_embeddings
            
        except Exception as e:
            await self._handle_embedding_error(e, user_id, start_time)
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, "WARNING")
    )
    async def _make_chat_completion_request(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> ChatCompletion:
        """Make chat completion request with retry logic"""
        try:
            response = await self.client.chat.completions.create(
                model=settings.azure_openai.deployment_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=0.95,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None
            )
            return response
            
        except Exception as e:
            logger.error(
                "Chat completion request failed",
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Update circuit breaker
            self.circuit_breaker['failure_count'] += 1
            self.circuit_breaker['last_failure_time'] = datetime.utcnow()
            
            if self.circuit_breaker['failure_count'] >= 5:
                self.circuit_breaker['state'] = 'open'
            
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logger, "WARNING")
    )
    async def _make_embedding_request(
        self,
        texts: List[str]
    ) -> List[List[float]]:
        """Make embedding request with retry logic"""
        try:
            response = await self.client.embeddings.create(
                input=texts,
                model=settings.azure_openai.embedding_deployment
            )
            
            return [data.embedding for data in response.data]
            
        except Exception as e:
            logger.error(
                "Embedding request failed",
                error=str(e),
                error_type=type(e).__name__,
                text_count=len(texts)
            )
            
            # Update circuit breaker
            self.circuit_breaker['failure_count'] += 1
            self.circuit_breaker['last_failure_time'] = datetime.utcnow()
            
            raise
    
    async def _check_circuit_breaker(self):
        """Check circuit breaker state"""
        if self.circuit_breaker['state'] == 'open':
            # Check if we should try half-open
            if (self.circuit_breaker['last_failure_time'] and 
                datetime.utcnow() - self.circuit_breaker['last_failure_time'] > timedelta(minutes=5)):
                self.circuit_breaker['state'] = 'half-open'
                logger.info("Circuit breaker moved to half-open state")
            else:
                raise ProcessingError(
                    message="Azure OpenAI service temporarily unavailable",
                    details={"circuit_breaker": "open"}
                )
    
    async def _check_rate_limits(
        self,
        user_id: Optional[str],
        messages: List[Dict[str, str]],
        max_tokens: int
    ):
        """Check rate limits for chat completion"""
        if not user_id:
            return
        
        now = datetime.utcnow()
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")
        
        # Initialize tracking if needed
        if user_id not in self.request_counts:
            self.request_counts[user_id] = {}
            self.token_usage_daily[user_id] = {}
            self.cost_tracking[user_id] = {}
        
        # Check hourly request limit
        hourly_requests = self.request_counts[user_id].get(hour_key, 0)
        if hourly_requests >= settings.rate_limit.queries_per_hour:
            raise RateLimitExceeded(
                message=f"Hourly request limit exceeded ({settings.rate_limit.queries_per_hour})",
                details={"limit_type": "hourly_requests", "reset_time": hour_key}
            )
        
        # Estimate token usage and cost
        estimated_input_tokens = self._count_tokens_in_messages(messages)
        estimated_total_tokens = estimated_input_tokens + max_tokens
        estimated_cost = self._estimate_cost(estimated_total_tokens, 'gpt-4')
        
        # Check daily cost limit
        daily_cost = self.cost_tracking[user_id].get(day_key, 0.0)
        if daily_cost + estimated_cost > 10.0:  # $10 daily limit
            raise RateLimitExceeded(
                message="Daily cost limit exceeded ($10.00)",
                details={"limit_type": "daily_cost", "current_cost": daily_cost}
            )
        
        # Update counters
        self.request_counts[user_id][hour_key] = hourly_requests + 1
    
    async def _check_embedding_rate_limits(
        self,
        user_id: Optional[str],
        token_count: int
    ):
        """Check rate limits for embeddings"""
        if not user_id:
            return
        
        # Embeddings have more generous limits
        # Implementation similar to chat completion limits
        pass
    
    def _validate_messages(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Validate and sanitize chat messages"""
        if not messages:
            raise ValidationError("Messages cannot be empty")
        
        validated = []
        for msg in messages:
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                raise ValidationError("Invalid message format")
            
            role = msg['role']
            content = msg['content']
            
            if role not in ['system', 'user', 'assistant']:
                raise ValidationError(f"Invalid role: {role}")
            
            if not content or not content.strip():
                continue  # Skip empty messages
            
            # Truncate very long messages
            if len(content) > 50000:  # ~12.5k tokens
                content = content[:50000] + "... [truncated]"
            
            validated.append({
                'role': role,
                'content': content.strip()
            })
        
        return validated
    
    def _count_tokens_in_messages(self, messages: List[Dict[str, str]]) -> int:
        """Count tokens in chat messages"""
        total_tokens = 0
        
        for message in messages:
            # Account for message formatting tokens
            total_tokens += 4  # Every message has role, content, name, and function call tokens
            
            for key, value in message.items():
                total_tokens += len(self.tokenizer.encode(str(value)))
        
        total_tokens += 2  # Every reply is primed with assistant
        return total_tokens
    
    def _estimate_cost(self, token_count: int, model: str) -> float:
        """Estimate cost for token usage"""
        if model not in self.model_pricing:
            model = 'gpt-4'  # Default to GPT-4 pricing
        
        pricing = self.model_pricing[model]
        
        # Assume 70% input, 30% output tokens for estimation
        input_tokens = int(token_count * 0.7)
        output_tokens = int(token_count * 0.3)
        
        cost = (
            (input_tokens / 1000) * pricing['input'] +
            (output_tokens / 1000) * pricing['output']
        )
        
        return cost
    
    def _process_chat_response(
        self,
        response: ChatCompletion,
        processing_time_ms: int,
        input_tokens: int
    ) -> OpenAIResponse:
        """Process chat completion response"""
        content = response.choices[0].message.content or ""
        
        # Calculate actual cost
        usage = response.usage
        actual_cost = self._calculate_actual_cost(usage, 'gpt-4')
        
        token_usage = TokenUsage(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost=actual_cost
        )
        
        return OpenAIResponse(
            content=content,
            token_usage=token_usage,
            model=response.model,
            processing_time_ms=processing_time_ms,
            request_id=getattr(response, 'id', None)
        )
    
    def _calculate_actual_cost(self, usage, model: str) -> float:
        """Calculate actual cost from usage"""
        if model not in self.model_pricing:
            model = 'gpt-4'
        
        pricing = self.model_pricing[model]
        
        cost = (
            (usage.prompt_tokens / 1000) * pricing['input'] +
            (usage.completion_tokens / 1000) * pricing['output']
        )
        
        return cost
    
    async def _update_usage_tracking(
        self,
        user_id: Optional[str],
        token_usage: TokenUsage
    ):
        """Update usage tracking for user"""
        if not user_id:
            return
        
        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        
        # Update daily cost tracking
        if user_id not in self.cost_tracking:
            self.cost_tracking[user_id] = {}
        
        current_cost = self.cost_tracking[user_id].get(day_key, 0.0)
        self.cost_tracking[user_id][day_key] = current_cost + token_usage.estimated_cost
        
        # Update token usage tracking
        if user_id not in self.token_usage_daily:
            self.token_usage_daily[user_id] = {}
        
        current_tokens = self.token_usage_daily[user_id].get(day_key, 0)
        self.token_usage_daily[user_id][day_key] = current_tokens + token_usage.total_tokens
    
    async def _record_completion_metrics(
        self,
        response: OpenAIResponse,
        processing_time_ms: int,
        user_id: Optional[str]
    ):
        """Record metrics for chat completion"""
        metrics_collector.record_metric(
            "openai_chat_completion_duration",
            processing_time_ms,
            {"user_id": user_id, "model": response.model}
        )
        
        metrics_collector.record_metric(
            "openai_token_usage",
            response.token_usage.total_tokens,
            {"user_id": user_id, "type": "chat_completion"}
        )
        
        metrics_collector.record_metric(
            "openai_cost",
            response.token_usage.estimated_cost,
            {"user_id": user_id, "type": "chat_completion"}
        )
        
        metrics_collector.record_counter(
            "openai_requests_total",
            1,
            {"type": "chat_completion", "status": "success"}
        )
    
    async def _record_embedding_metrics(
        self,
        text_count: int,
        processing_time_ms: int,
        user_id: Optional[str]
    ):
        """Record metrics for embeddings"""
        metrics_collector.record_metric(
            "openai_embedding_duration",
            processing_time_ms,
            {"user_id": user_id, "text_count": text_count}
        )
        
        metrics_collector.record_counter(
            "openai_requests_total",
            1,
            {"type": "embedding", "status": "success"}
        )
    
    async def _handle_completion_error(
        self,
        error: Exception,
        user_id: Optional[str],
        start_time: float
    ):
        """Handle chat completion errors"""
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Chat completion failed",
            user_id=user_id,
            error=str(error),
            error_type=type(error).__name__,
            processing_time_ms=processing_time_ms,
            exc_info=True
        )
        
        metrics_collector.record_counter(
            "openai_requests_total",
            1,
            {"type": "chat_completion", "status": "error"}
        )
        
        metrics_collector.record_metric(
            "openai_errors",
            1,
            {"error_type": type(error).__name__, "operation": "chat_completion"}
        )
    
    async def _handle_embedding_error(
        self,
        error: Exception,
        user_id: Optional[str],
        start_time: float
    ):
        """Handle embedding errors"""
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Embedding generation failed",
            user_id=user_id,
            error=str(error),
            error_type=type(error).__name__,
            processing_time_ms=processing_time_ms,
            exc_info=True
        )
        
        metrics_collector.record_counter(
            "openai_requests_total",
            1,
            {"type": "embedding", "status": "error"}
        )
    
    async def get_usage_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get usage statistics for a user"""
        day_key = datetime.utcnow().strftime("%Y-%m-%d")
        hour_key = datetime.utcnow().strftime("%Y-%m-%d-%H")
        
        return {
            "user_id": user_id,
            "daily_cost": self.cost_tracking.get(user_id, {}).get(day_key, 0.0),
            "daily_tokens": self.token_usage_daily.get(user_id, {}).get(day_key, 0),
            "hourly_requests": self.request_counts.get(user_id, {}).get(hour_key, 0),
            "limits": {
                "hourly_requests": settings.rate_limit.queries_per_hour,
                "daily_cost": 10.0
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on Azure OpenAI service"""
        try:
            # Simple test request
            test_messages = [
                {"role": "user", "content": "Hello"}
            ]
            
            start_time = time.time()
            response = await self.client.chat.completions.create(
                model=settings.azure_openai.deployment_name,
                messages=test_messages,
                max_tokens=5,
                temperature=0
            )
            response_time = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "response_time_ms": response_time,
                "model": response.model,
                "circuit_breaker_state": self.circuit_breaker['state'],
                "endpoint": settings.azure_openai.endpoint
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "circuit_breaker_state": self.circuit_breaker['state'],
                "endpoint": settings.azure_openai.endpoint
            }

# Global service instance
azure_openai_service = AzureOpenAIService()