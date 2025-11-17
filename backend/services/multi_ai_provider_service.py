"""
Multi-AI Provider Service
Integrates multiple AI APIs: OpenAI GPT-4, Claude Opus, Google Gemini, Cohere, Perplexity
"""
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field
from enum import Enum
import httpx
import asyncio
from datetime import datetime
import os


class AIProvider(str, Enum):
    """Available AI providers"""
    OPENAI_GPT4 = "openai_gpt4"
    OPENAI_GPT4_TURBO = "openai_gpt4_turbo"
    OPENAI_GPT5 = "openai_gpt5"
    CLAUDE_OPUS = "claude_opus"
    CLAUDE_SONNET = "claude_sonnet"
    CLAUDE_HAIKU = "claude_haiku"
    GEMINI_PRO = "gemini_pro"
    GEMINI_ULTRA = "gemini_ultra"
    COHERE_COMMAND = "cohere_command"
    PERPLEXITY = "perplexity"


class Message(BaseModel):
    """Standardized message format"""
    role: str  # "system", "user", "assistant"
    content: str


class AIResponse(BaseModel):
    """Standardized AI response"""
    provider: AIProvider
    model: str
    content: str
    finish_reason: str
    usage: Dict[str, int]
    latency_ms: int
    cost_estimate: float = 0.0


class MultiAIProviderConfig(BaseModel):
    """Configuration for multi-AI provider"""
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    cohere_api_key: Optional[str] = None
    perplexity_api_key: Optional[str] = None

    default_provider: AIProvider = AIProvider.OPENAI_GPT4
    enable_fallback: bool = True
    fallback_chain: List[AIProvider] = Field(default_factory=lambda: [
        AIProvider.OPENAI_GPT4,
        AIProvider.CLAUDE_OPUS,
        AIProvider.GEMINI_PRO
    ])


class MultiAIProviderService:
    """
    Multi-AI Provider Service supporting multiple LLM APIs

    Features:
    - Unified interface for multiple AI providers
    - Automatic fallback on failures
    - Load balancing across providers
    - Cost optimization
    - Provider-specific optimizations
    """

    # Model pricing (per 1M tokens) - Approximate as of 2024
    PRICING = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-5": {"input": 50.0, "output": 100.0},
        "claude-opus-3": {"input": 15.0, "output": 75.0},
        "claude-sonnet-3.5": {"input": 3.0, "output": 15.0},
        "claude-haiku-3": {"input": 0.25, "output": 1.25},
        "gemini-pro": {"input": 0.5, "output": 1.5},
        "gemini-ultra": {"input": 5.0, "output": 15.0},
        "command-r-plus": {"input": 3.0, "output": 15.0},
        "pplx-70b-online": {"input": 1.0, "output": 1.0}
    }

    def __init__(self, config: Optional[MultiAIProviderConfig] = None):
        self.config = config or MultiAIProviderConfig()

        # Initialize API keys from environment if not provided
        self.config.openai_api_key = self.config.openai_api_key or os.getenv("OPENAI_API_KEY")
        self.config.anthropic_api_key = self.config.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.config.google_api_key = self.config.google_api_key or os.getenv("GOOGLE_API_KEY")
        self.config.cohere_api_key = self.config.cohere_api_key or os.getenv("COHERE_API_KEY")
        self.config.perplexity_api_key = self.config.perplexity_api_key or os.getenv("PERPLEXITY_API_KEY")

        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate_completion(
        self,
        messages: List[Message],
        provider: Optional[AIProvider] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
        enable_fallback: bool = True
    ) -> AIResponse:
        """
        Generate completion using specified provider or default

        Args:
            messages: List of messages in conversation
            provider: Specific AI provider to use (or default)
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens in response
            enable_fallback: Whether to fallback on error
        """
        provider = provider or self.config.default_provider

        try:
            return await self._call_provider(
                provider=provider,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            if enable_fallback and self.config.enable_fallback:
                return await self._fallback_generation(
                    messages=messages,
                    failed_provider=provider,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            raise

    async def _call_provider(
        self,
        provider: AIProvider,
        messages: List[Message],
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Call specific AI provider"""

        start_time = datetime.utcnow()

        if provider in [AIProvider.OPENAI_GPT4, AIProvider.OPENAI_GPT4_TURBO, AIProvider.OPENAI_GPT5]:
            response = await self._call_openai(provider, messages, temperature, max_tokens)
        elif provider in [AIProvider.CLAUDE_OPUS, AIProvider.CLAUDE_SONNET, AIProvider.CLAUDE_HAIKU]:
            response = await self._call_claude(provider, messages, temperature, max_tokens)
        elif provider in [AIProvider.GEMINI_PRO, AIProvider.GEMINI_ULTRA]:
            response = await self._call_gemini(provider, messages, temperature, max_tokens)
        elif provider == AIProvider.COHERE_COMMAND:
            response = await self._call_cohere(provider, messages, temperature, max_tokens)
        elif provider == AIProvider.PERPLEXITY:
            response = await self._call_perplexity(provider, messages, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        latency = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        response.latency_ms = latency

        return response

    async def _call_openai(
        self,
        provider: AIProvider,
        messages: List[Message],
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Call OpenAI API"""

        model_map = {
            AIProvider.OPENAI_GPT4: "gpt-4",
            AIProvider.OPENAI_GPT4_TURBO: "gpt-4-turbo",
            AIProvider.OPENAI_GPT5: "gpt-5"  # When available
        }

        model = model_map.get(provider, "gpt-4")

        request_body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        headers = {
            "Authorization": f"Bearer {self.config.openai_api_key}",
            "Content-Type": "application/json"
        }

        response = await self.client.post(
            "https://api.openai.com/v1/chat/completions",
            json=request_body,
            headers=headers
        )

        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        cost = self._calculate_cost(
            model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )

        return AIResponse(
            provider=provider,
            model=model,
            content=data["choices"][0]["message"]["content"],
            finish_reason=data["choices"][0]["finish_reason"],
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            },
            latency_ms=0,  # Set by caller
            cost_estimate=cost
        )

    async def _call_claude(
        self,
        provider: AIProvider,
        messages: List[Message],
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Call Anthropic Claude API"""

        model_map = {
            AIProvider.CLAUDE_OPUS: "claude-3-opus-20240229",
            AIProvider.CLAUDE_SONNET: "claude-3-5-sonnet-20240620",
            AIProvider.CLAUDE_HAIKU: "claude-3-haiku-20240307"
        }

        model = model_map.get(provider, "claude-3-opus-20240229")

        # Separate system message from conversation
        system_message = None
        conversation_messages = []

        for msg in messages:
            if msg.role == "system":
                system_message = msg.content
            else:
                conversation_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        request_body = {
            "model": model,
            "messages": conversation_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        if system_message:
            request_body["system"] = system_message

        headers = {
            "x-api-key": self.config.anthropic_api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }

        response = await self.client.post(
            "https://api.anthropic.com/v1/messages",
            json=request_body,
            headers=headers
        )

        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        cost = self._calculate_cost(
            model,
            usage.get("input_tokens", 0),
            usage.get("output_tokens", 0)
        )

        return AIResponse(
            provider=provider,
            model=model,
            content=data["content"][0]["text"],
            finish_reason=data.get("stop_reason", "end_turn"),
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
                "total_tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            },
            latency_ms=0,
            cost_estimate=cost
        )

    async def _call_gemini(
        self,
        provider: AIProvider,
        messages: List[Message],
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Call Google Gemini API"""

        model_map = {
            AIProvider.GEMINI_PRO: "gemini-1.5-pro",
            AIProvider.GEMINI_ULTRA: "gemini-1.5-ultra"
        }

        model = model_map.get(provider, "gemini-1.5-pro")

        # Convert messages to Gemini format
        gemini_messages = []
        for msg in messages:
            role = "model" if msg.role == "assistant" else "user"
            gemini_messages.append({
                "role": role,
                "parts": [{"text": msg.content}]
            })

        request_body = {
            "contents": gemini_messages,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.config.google_api_key}"

        response = await self.client.post(
            url,
            json=request_body
        )

        response.raise_for_status()
        data = response.json()

        content = data["candidates"][0]["content"]["parts"][0]["text"]

        # Estimate token usage (Gemini doesn't always provide exact counts)
        prompt_tokens = sum(len(m.content.split()) * 1.3 for m in messages)  # Rough estimate
        completion_tokens = len(content.split()) * 1.3

        cost = self._calculate_cost(model, int(prompt_tokens), int(completion_tokens))

        return AIResponse(
            provider=provider,
            model=model,
            content=content,
            finish_reason=data["candidates"][0].get("finishReason", "STOP"),
            usage={
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens + completion_tokens)
            },
            latency_ms=0,
            cost_estimate=cost
        )

    async def _call_cohere(
        self,
        provider: AIProvider,
        messages: List[Message],
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Call Cohere API"""

        model = "command-r-plus"

        # Convert messages to Cohere chat format
        chat_history = []
        message = ""

        for msg in messages:
            if msg.role == "user":
                message = msg.content
            elif msg.role == "assistant":
                chat_history.append({
                    "role": "CHATBOT",
                    "message": msg.content
                })

        request_body = {
            "model": model,
            "message": message,
            "chat_history": chat_history,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        headers = {
            "Authorization": f"Bearer {self.config.cohere_api_key}",
            "Content-Type": "application/json"
        }

        response = await self.client.post(
            "https://api.cohere.ai/v1/chat",
            json=request_body,
            headers=headers
        )

        response.raise_for_status()
        data = response.json()

        usage = data.get("meta", {}).get("billed_units", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        cost = self._calculate_cost(model, prompt_tokens, completion_tokens)

        return AIResponse(
            provider=provider,
            model=model,
            content=data["text"],
            finish_reason=data.get("finish_reason", "COMPLETE"),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            },
            latency_ms=0,
            cost_estimate=cost
        )

    async def _call_perplexity(
        self,
        provider: AIProvider,
        messages: List[Message],
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Call Perplexity API (with real-time web search)"""

        model = "pplx-70b-online"  # Online model with web search

        request_body = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        headers = {
            "Authorization": f"Bearer {self.config.perplexity_api_key}",
            "Content-Type": "application/json"
        }

        response = await self.client.post(
            "https://api.perplexity.ai/chat/completions",
            json=request_body,
            headers=headers
        )

        response.raise_for_status()
        data = response.json()

        usage = data.get("usage", {})
        cost = self._calculate_cost(
            model,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0)
        )

        return AIResponse(
            provider=provider,
            model=model,
            content=data["choices"][0]["message"]["content"],
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            },
            latency_ms=0,
            cost_estimate=cost
        )

    async def _fallback_generation(
        self,
        messages: List[Message],
        failed_provider: AIProvider,
        temperature: float,
        max_tokens: int
    ) -> AIResponse:
        """Fallback to alternative providers on failure"""

        fallback_providers = [
            p for p in self.config.fallback_chain
            if p != failed_provider
        ]

        last_error = None

        for provider in fallback_providers:
            try:
                return await self._call_provider(
                    provider=provider,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                last_error = e
                continue

        raise Exception(f"All providers failed. Last error: {last_error}")

    def _calculate_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate estimated cost for API call"""

        # Normalize model name
        for price_model, prices in self.PRICING.items():
            if price_model in model:
                input_cost = (prompt_tokens / 1_000_000) * prices["input"]
                output_cost = (completion_tokens / 1_000_000) * prices["output"]
                return round(input_cost + output_cost, 6)

        return 0.0

    async def parallel_generation(
        self,
        messages: List[Message],
        providers: List[AIProvider],
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> List[AIResponse]:
        """Generate completions from multiple providers in parallel"""

        tasks = [
            self._call_provider(
                provider=provider,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            for provider in providers
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_responses = [
            r for r in responses
            if isinstance(r, AIResponse)
        ]

        return valid_responses

    async def best_of_n_generation(
        self,
        messages: List[Message],
        providers: List[AIProvider],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        selection_criteria: str = "longest"
    ) -> AIResponse:
        """Generate from multiple providers and select best response"""

        responses = await self.parallel_generation(
            messages=messages,
            providers=providers,
            temperature=temperature,
            max_tokens=max_tokens
        )

        if not responses:
            raise Exception("No valid responses generated")

        # Select best based on criteria
        if selection_criteria == "longest":
            return max(responses, key=lambda r: len(r.content))
        elif selection_criteria == "cheapest":
            return min(responses, key=lambda r: r.cost_estimate)
        elif selection_criteria == "fastest":
            return min(responses, key=lambda r: r.latency_ms)
        else:
            return responses[0]

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global instance
multi_ai_provider = MultiAIProviderService()
