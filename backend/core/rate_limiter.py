"""
Advanced rate limiting and cost control system
Implements multiple rate limiting strategies with cost tracking
"""
import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from config import settings
from database.models import User, Query
from core.cache_manager import cache_manager
from utils.exceptions import RateLimitExceeded, QuotaExceededError

logger = structlog.get_logger(__name__)

class LimitType(str, Enum):
    """Rate limit types"""
    REQUESTS_PER_MINUTE = "requests_per_minute"
    REQUESTS_PER_HOUR = "requests_per_hour"
    REQUESTS_PER_DAY = "requests_per_day"
    TOKENS_PER_HOUR = "tokens_per_hour"
    TOKENS_PER_DAY = "tokens_per_day"
    COST_PER_HOUR = "cost_per_hour"
    COST_PER_DAY = "cost_per_day"
    CONCURRENT_REQUESTS = "concurrent_requests"

@dataclass
class RateLimit:
    """Rate limit configuration"""
    limit_type: LimitType
    limit: int
    window_seconds: int
    burst_allowance: int = 0
    cost_per_unit: float = 0.0

@dataclass
class UsageRecord:
    """Usage tracking record"""
    timestamp: float
    count: int
    tokens: int = 0
    cost: float = 0.0
    metadata: Dict[str, Any] = None

class TokenBucket:
    """Token bucket implementation for burst control"""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket"""
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def available_tokens(self) -> int:
        """Get number of available tokens"""
        self._refill()
        return int(self.tokens)

class SlidingWindowCounter:
    """Sliding window counter for rate limiting"""
    
    def __init__(self, window_seconds: int, max_requests: int):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self.requests = deque()
    
    def is_allowed(self) -> Tuple[bool, int]:
        """Check if request is allowed, return (allowed, remaining)"""
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Remove old requests
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
        
        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True, self.max_requests - len(self.requests)
        
        return False, 0
    
    def time_until_reset(self) -> int:
        """Get seconds until window resets"""
        if not self.requests:
            return 0
        
        oldest_request = self.requests[0]
        reset_time = oldest_request + self.window_seconds
        return max(0, int(reset_time - time.time()))

class CostTracker:
    """Track API costs and token usage"""
    
    def __init__(self):
        self.cost_per_token = {
            "gpt-4": 0.00003,  # $0.03 per 1K tokens
            "gpt-3.5-turbo": 0.000002,  # $0.002 per 1K tokens
            "text-embedding-ada-002": 0.0000001  # $0.0001 per 1K tokens
        }
        
        self.user_costs = defaultdict(lambda: defaultdict(float))
        self.user_tokens = defaultdict(lambda: defaultdict(int))
        
        logger.info("Cost tracker initialized")
    
    def calculate_cost(self, model: str, input_tokens: int, output_tokens: int = 0) -> float:
        """Calculate cost for API call"""
        if model not in self.cost_per_token:
            logger.warning("Unknown model for cost calculation", model=model)
            return 0.0
        
        total_tokens = input_tokens + output_tokens
        cost = total_tokens * self.cost_per_token[model]
        
        return cost
    
    def record_usage(
        self,
        user_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
        timestamp: Optional[datetime] = None
    ) -> float:
        """Record token usage and calculate cost"""
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        total_tokens = input_tokens + output_tokens
        
        # Record daily usage
        date_key = timestamp.strftime("%Y-%m-%d")
        self.user_costs[user_id][date_key] += cost
        self.user_tokens[user_id][date_key] += total_tokens
        
        # Record hourly usage
        hour_key = timestamp.strftime("%Y-%m-%d-%H")
        self.user_costs[user_id][hour_key] += cost
        self.user_tokens[user_id][hour_key] += total_tokens
        
        logger.debug(
            "Usage recorded",
            user_id=user_id,
            model=model,
            tokens=total_tokens,
            cost=cost
        )
        
        return cost
    
    def get_user_usage(
        self,
        user_id: str,
        period: str = "day"
    ) -> Dict[str, Any]:
        """Get user usage statistics"""
        now = datetime.utcnow()
        
        if period == "hour":
            key = now.strftime("%Y-%m-%d-%H")
        else:  # day
            key = now.strftime("%Y-%m-%d")
        
        return {
            "period": period,
            "key": key,
            "tokens": self.user_tokens[user_id].get(key, 0),
            "cost": self.user_costs[user_id].get(key, 0.0),
            "timestamp": now.isoformat()
        }
    
    def check_cost_limit(self, user_id: str, limit: float, period: str = "day") -> bool:
        """Check if user is within cost limit"""
        usage = self.get_user_usage(user_id, period)
        return usage["cost"] <= limit

class RateLimiter:
    """
    Comprehensive rate limiting system
    
    Features:
    - Multiple rate limiting algorithms
    - Per-user and per-endpoint limits
    - Token bucket for burst control
    - Sliding window counters
    - Cost tracking and limits
    - Redis-backed persistence
    """
    
    def __init__(self):
        self.limits = {}
        self.user_buckets = defaultdict(dict)
        self.user_counters = defaultdict(dict)
        self.cost_tracker = CostTracker()
        
        # Default rate limits
        self._setup_default_limits()
        
        logger.info("Rate limiter initialized")
    
    def _setup_default_limits(self):
        """Setup default rate limits"""
        # Query limits
        self.add_limit(
            "query_requests_per_hour",
            RateLimit(
                limit_type=LimitType.REQUESTS_PER_HOUR,
                limit=settings.rate_limit.queries_per_hour,
                window_seconds=3600,
                burst_allowance=10
            )
        )
        
        self.add_limit(
            "query_requests_per_minute",
            RateLimit(
                limit_type=LimitType.REQUESTS_PER_MINUTE,
                limit=20,
                window_seconds=60,
                burst_allowance=5
            )
        )
        
        # Upload limits
        self.add_limit(
            "upload_requests_per_hour",
            RateLimit(
                limit_type=LimitType.REQUESTS_PER_HOUR,
                limit=settings.rate_limit.uploads_per_hour,
                window_seconds=3600,
                burst_allowance=3
            )
        )
        
        # Token limits
        self.add_limit(
            "tokens_per_hour",
            RateLimit(
                limit_type=LimitType.TOKENS_PER_HOUR,
                limit=100000,  # 100K tokens per hour
                window_seconds=3600
            )
        )
        
        # Cost limits
        self.add_limit(
            "cost_per_day",
            RateLimit(
                limit_type=LimitType.COST_PER_DAY,
                limit=10.0,  # $10 per day
                window_seconds=86400
            )
        )
        
        # Concurrent request limits
        self.add_limit(
            "concurrent_requests",
            RateLimit(
                limit_type=LimitType.CONCURRENT_REQUESTS,
                limit=settings.rate_limit.max_concurrent_requests,
                window_seconds=0  # No window for concurrent limits
            )
        )
    
    def add_limit(self, name: str, rate_limit: RateLimit):
        """Add a rate limit configuration"""
        self.limits[name] = rate_limit
        logger.info("Rate limit added", name=name, limit=rate_limit.limit, type=rate_limit.limit_type)
    
    async def check_rate_limit(
        self,
        user_id: str,
        endpoint: str,
        tokens: int = 0,
        cost: float = 0.0
    ) -> Dict[str, Any]:
        """
        Check all applicable rate limits for a request
        
        Returns:
            Dict with rate limit status and metadata
        """
        results = {
            "allowed": True,
            "limits_checked": [],
            "remaining": {},
            "reset_times": {},
            "violations": []
        }
        
        # Get applicable limits for endpoint
        applicable_limits = self._get_applicable_limits(endpoint)
        
        for limit_name in applicable_limits:
            limit_config = self.limits[limit_name]
            
            try:
                limit_result = await self._check_single_limit(
                    user_id, limit_name, limit_config, tokens, cost
                )
                
                results["limits_checked"].append(limit_name)
                results["remaining"][limit_name] = limit_result.get("remaining", 0)
                results["reset_times"][limit_name] = limit_result.get("reset_time", 0)
                
                if not limit_result["allowed"]:
                    results["allowed"] = False
                    results["violations"].append({
                        "limit": limit_name,
                        "type": limit_config.limit_type.value,
                        "message": limit_result.get("message", "Rate limit exceeded"),
                        "retry_after": limit_result.get("retry_after", 60)
                    })
                    
            except Exception as e:
                logger.error("Rate limit check failed", limit=limit_name, error=str(e))
                # Don't block request on rate limit check failure
                continue
        
        return results
    
    def _get_applicable_limits(self, endpoint: str) -> List[str]:
        """Get applicable rate limits for an endpoint"""
        endpoint_limits = {
            "/api/query": [
                "query_requests_per_hour",
                "query_requests_per_minute",
                "tokens_per_hour",
                "cost_per_day",
                "concurrent_requests"
            ],
            "/api/upload": [
                "upload_requests_per_hour",
                "concurrent_requests"
            ]
        }
        
        return endpoint_limits.get(endpoint, ["concurrent_requests"])
    
    async def _check_single_limit(
        self,
        user_id: str,
        limit_name: str,
        limit_config: RateLimit,
        tokens: int,
        cost: float
    ) -> Dict[str, Any]:
        """Check a single rate limit"""
        
        if limit_config.limit_type == LimitType.CONCURRENT_REQUESTS:
            return await self._check_concurrent_limit(user_id, limit_config)
        
        elif limit_config.limit_type in [
            LimitType.REQUESTS_PER_MINUTE,
            LimitType.REQUESTS_PER_HOUR,
            LimitType.REQUESTS_PER_DAY
        ]:
            return await self._check_request_limit(user_id, limit_name, limit_config)
        
        elif limit_config.limit_type in [
            LimitType.TOKENS_PER_HOUR,
            LimitType.TOKENS_PER_DAY
        ]:
            return await self._check_token_limit(user_id, limit_name, limit_config, tokens)
        
        elif limit_config.limit_type in [
            LimitType.COST_PER_HOUR,
            LimitType.COST_PER_DAY
        ]:
            return await self._check_cost_limit(user_id, limit_name, limit_config, cost)
        
        else:
            return {"allowed": True, "remaining": limit_config.limit}
    
    async def _check_concurrent_limit(
        self,
        user_id: str,
        limit_config: RateLimit
    ) -> Dict[str, Any]:
        """Check concurrent request limit"""
        # This would track active requests per user
        # For now, return allowed
        return {
            "allowed": True,
            "remaining": limit_config.limit,
            "message": "Concurrent limit check"
        }
    
    async def _check_request_limit(
        self,
        user_id: str,
        limit_name: str,
        limit_config: RateLimit
    ) -> Dict[str, Any]:
        """Check request-based rate limit"""
        counter_key = f"{user_id}:{limit_name}"
        
        # Get or create sliding window counter
        if counter_key not in self.user_counters[user_id]:
            self.user_counters[user_id][counter_key] = SlidingWindowCounter(
                limit_config.window_seconds,
                limit_config.limit
            )
        
        counter = self.user_counters[user_id][counter_key]
        allowed, remaining = counter.is_allowed()
        
        if not allowed:
            retry_after = counter.time_until_reset()
            return {
                "allowed": False,
                "remaining": remaining,
                "retry_after": retry_after,
                "message": f"Request rate limit exceeded: {limit_config.limit} per {limit_config.window_seconds}s"
            }
        
        # Check burst limit if configured
        if limit_config.burst_allowance > 0:
            bucket_key = f"{user_id}:{limit_name}:burst"
            
            if bucket_key not in self.user_buckets[user_id]:
                self.user_buckets[user_id][bucket_key] = TokenBucket(
                    limit_config.burst_allowance,
                    limit_config.burst_allowance / 60  # Refill rate per second
                )
            
            bucket = self.user_buckets[user_id][bucket_key]
            
            if not bucket.consume(1):
                return {
                    "allowed": False,
                    "remaining": bucket.available_tokens(),
                    "retry_after": 60,
                    "message": f"Burst limit exceeded: {limit_config.burst_allowance} requests"
                }
        
        return {
            "allowed": True,
            "remaining": remaining,
            "reset_time": counter.time_until_reset()
        }
    
    async def _check_token_limit(
        self,
        user_id: str,
        limit_name: str,
        limit_config: RateLimit,
        tokens: int
    ) -> Dict[str, Any]:
        """Check token-based rate limit"""
        period = "hour" if "hour" in limit_name else "day"
        usage = self.cost_tracker.get_user_usage(user_id, period)
        
        if usage["tokens"] + tokens > limit_config.limit:
            return {
                "allowed": False,
                "remaining": max(0, limit_config.limit - usage["tokens"]),
                "retry_after": 3600 if period == "hour" else 86400,
                "message": f"Token limit exceeded: {limit_config.limit} tokens per {period}"
            }
        
        return {
            "allowed": True,
            "remaining": limit_config.limit - usage["tokens"] - tokens
        }
    
    async def _check_cost_limit(
        self,
        user_id: str,
        limit_name: str,
        limit_config: RateLimit,
        cost: float
    ) -> Dict[str, Any]:
        """Check cost-based rate limit"""
        period = "hour" if "hour" in limit_name else "day"
        usage = self.cost_tracker.get_user_usage(user_id, period)
        
        if usage["cost"] + cost > limit_config.limit:
            return {
                "allowed": False,
                "remaining": max(0.0, limit_config.limit - usage["cost"]),
                "retry_after": 3600 if period == "hour" else 86400,
                "message": f"Cost limit exceeded: ${limit_config.limit} per {period}"
            }
        
        return {
            "allowed": True,
            "remaining": limit_config.limit - usage["cost"] - cost
        }
    
    async def record_request(
        self,
        user_id: str,
        endpoint: str,
        tokens: int = 0,
        cost: float = 0.0,
        model: str = "gpt-4"
    ):
        """Record a successful request for rate limiting"""
        try:
            # Record token usage and cost
            if tokens > 0:
                actual_cost = self.cost_tracker.record_usage(
                    user_id, model, tokens
                )
                
                logger.debug(
                    "Request recorded",
                    user_id=user_id,
                    endpoint=endpoint,
                    tokens=tokens,
                    cost=actual_cost
                )
            
        except Exception as e:
            logger.error("Failed to record request", user_id=user_id, error=str(e))
    
    async def get_user_limits_status(self, user_id: str) -> Dict[str, Any]:
        """Get current rate limit status for user"""
        status = {
            "user_id": user_id,
            "limits": {},
            "usage": {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get usage statistics
        hourly_usage = self.cost_tracker.get_user_usage(user_id, "hour")
        daily_usage = self.cost_tracker.get_user_usage(user_id, "day")
        
        status["usage"] = {
            "hourly": hourly_usage,
            "daily": daily_usage
        }
        
        # Check each limit
        for limit_name, limit_config in self.limits.items():
            try:
                limit_result = await self._check_single_limit(
                    user_id, limit_name, limit_config, 0, 0.0
                )
                
                status["limits"][limit_name] = {
                    "type": limit_config.limit_type.value,
                    "limit": limit_config.limit,
                    "remaining": limit_result.get("remaining", 0),
                    "allowed": limit_result.get("allowed", True),
                    "reset_time": limit_result.get("reset_time", 0)
                }
                
            except Exception as e:
                logger.error("Failed to check limit status", limit=limit_name, error=str(e))
        
        return status
    
    async def create_usage_alert(
        self,
        user_id: str,
        alert_type: str,
        threshold: float,
        current_value: float
    ):
        """Create usage alert for monitoring"""
        alert_data = {
            "user_id": user_id,
            "alert_type": alert_type,
            "threshold": threshold,
            "current_value": current_value,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": "warning" if current_value < threshold * 0.9 else "critical"
        }
        
        logger.warning("Usage alert created", **alert_data)
        
        # In production, this would send notifications
        # For now, just log the alert

# Global rate limiter instance
rate_limiter = RateLimiter()

# Utility functions
async def check_user_rate_limits(
    user_id: str,
    endpoint: str,
    tokens: int = 0,
    estimated_cost: float = 0.0
) -> Dict[str, Any]:
    """Check rate limits for a user request"""
    return await rate_limiter.check_rate_limit(user_id, endpoint, tokens, estimated_cost)

async def record_user_request(
    user_id: str,
    endpoint: str,
    tokens: int = 0,
    model: str = "gpt-4"
):
    """Record a user request for rate limiting"""
    await rate_limiter.record_request(user_id, endpoint, tokens, model=model)

async def get_user_usage_status(user_id: str) -> Dict[str, Any]:
    """Get user's current usage and limits status"""
    return await rate_limiter.get_user_limits_status(user_id)

def estimate_query_cost(query_length: int, mode: str = "qa") -> Tuple[int, float]:
    """Estimate tokens and cost for a query"""
    # Rough estimation based on query length and mode
    base_tokens = len(query_length.split()) * 1.3  # ~1.3 tokens per word
    
    if mode == "drafting":
        estimated_tokens = int(base_tokens * 3)  # More context needed
    elif mode == "summarization":
        estimated_tokens = int(base_tokens * 2)
    else:  # qa
        estimated_tokens = int(base_tokens * 1.5)
    
    # Add response tokens estimate
    response_tokens = min(1000, estimated_tokens // 2)
    total_tokens = estimated_tokens + response_tokens
    
    # Calculate cost (using GPT-4 pricing)
    cost = total_tokens * 0.00003
    
    return total_tokens, cost