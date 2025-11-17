"""
Multi-AI Provider Integration System
Supports OpenAI GPT-4, Anthropic Claude, Google Gemini, Cohere, and Perplexity
"""

from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import os
import asyncio
import aiohttp
from abc import ABC, abstractmethod

class AIProvider(Enum):
    """Supported AI providers"""
    OPENAI_GPT4 = "openai_gpt4"
    OPENAI_GPT4_TURBO = "openai_gpt4_turbo"
    ANTHROPIC_CLAUDE_OPUS = "anthropic_claude_opus"
    ANTHROPIC_CLAUDE_SONNET = "anthropic_claude_sonnet"
    GOOGLE_GEMINI_PRO = "google_gemini_pro"
    GOOGLE_GEMINI_ULTRA = "google_gemini_ultra"
    COHERE_COMMAND = "cohere_command"
    PERPLEXITY_ONLINE = "perplexity_online"

@dataclass
class AIProviderConfig:
    """Configuration for each AI provider"""
    name: str
    provider: AIProvider
    model_id: str
    api_base_url: str
    max_tokens: int
    supports_streaming: bool
    supports_function_calling: bool
    supports_vision: bool
    cost_per_1k_input_tokens: float
    cost_per_1k_output_tokens: float
    strengths: List[str]
    best_for: List[str]

# Provider configurations
PROVIDER_CONFIGS: Dict[AIProvider, AIProviderConfig] = {
    AIProvider.OPENAI_GPT4: AIProviderConfig(
        name="OpenAI GPT-4",
        provider=AIProvider.OPENAI_GPT4,
        model_id="gpt-4",
        api_base_url="https://api.openai.com/v1/chat/completions",
        max_tokens=8192,
        supports_streaming=True,
        supports_function_calling=True,
        supports_vision=False,
        cost_per_1k_input_tokens=0.03,
        cost_per_1k_output_tokens=0.06,
        strengths=[
            "Excellent reasoning and analysis",
            "Strong legal knowledge",
            "Good at complex tasks",
            "Reliable and consistent"
        ],
        best_for=[
            "Complex legal analysis",
            "Contract drafting",
            "Legal research",
            "General legal queries"
        ]
    ),

    AIProvider.ANTHROPIC_CLAUDE_OPUS: AIProviderConfig(
        name="Claude 3 Opus",
        provider=AIProvider.ANTHROPIC_CLAUDE_OPUS,
        model_id="claude-3-opus-20240229",
        api_base_url="https://api.anthropic.com/v1/messages",
        max_tokens=200000,  # Massive context window
        supports_streaming=True,
        supports_function_calling=False,
        supports_vision=True,
        cost_per_1k_input_tokens=0.015,
        cost_per_1k_output_tokens=0.075,
        strengths=[
            "Massive 200K context window",
            "Excellent at following instructions",
            "Strong reasoning capabilities",
            "Good at structured outputs",
            "Constitutional AI (ethical)
"        ],
        best_for=[
            "Long document analysis",
            "Complex multi-document reviews",
            "Ethical reasoning",
            "Structured legal outputs"
        ]
    ),

    AIProvider.ANTHROPIC_CLAUDE_SONNET: AIProviderConfig(
        name="Claude 3 Sonnet",
        provider=AIProvider.ANTHROPIC_CLAUDE_SONNET,
        model_id="claude-3-sonnet-20240229",
        api_base_url="https://api.anthropic.com/v1/messages",
        max_tokens=200000,
        supports_streaming=True,
        supports_function_calling=False,
        supports_vision=True,
        cost_per_1k_input_tokens=0.003,
        cost_per_1k_output_tokens=0.015,
        strengths=[
            "Good balance of speed and capability",
            "Large context window",
            "Cost-effective",
            "Fast response times"
        ],
        best_for=[
            "Balanced legal queries",
            "Cost-sensitive applications",
            "Quick document reviews",
            "Standard legal analysis"
        ]
    ),

    AIProvider.GOOGLE_GEMINI_PRO: AIProviderConfig(
        name="Google Gemini Pro",
        provider=AIProvider.GOOGLE_GEMINI_PRO,
        model_id="gemini-pro",
        api_base_url="https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent",
        max_tokens=32000,
        supports_streaming=True,
        supports_function_calling=True,
        supports_vision=False,
        cost_per_1k_input_tokens=0.00025,
        cost_per_1k_output_tokens=0.0005,
        strengths=[
            "Very cost-effective",
            "Good multilingual support",
            "Fast processing",
            "Google search integration"
        ],
        best_for=[
            "High-volume queries",
            "Multilingual legal work",
            "Cost-sensitive deployments",
            "Quick lookups"
        ]
    ),

    AIProvider.PERPLEXITY_ONLINE: AIProviderConfig(
        name="Perplexity Online",
        provider=AIProvider.PERPLEXITY_ONLINE,
        model_id="pplx-70b-online",
        api_base_url="https://api.perplexity.ai/chat/completions",
        max_tokens=4096,
        supports_streaming=True,
        supports_function_calling=False,
        supports_vision=False,
        cost_per_1k_input_tokens=0.001,
        cost_per_1k_output_tokens=0.001,
        strengths=[
            "Real-time web search",
            "Current information access",
            "Excellent citations",
            "Up-to-date legal developments"
        ],
        best_for=[
            "Current legal news",
            "Recent case law",
            "Regulatory updates",
            "Real-time legal research"
        ]
    ),

    AIProvider.COHERE_COMMAND: AIProviderConfig(
        name="Cohere Command",
        provider=AIProvider.COHERE_COMMAND,
        model_id="command",
        api_base_url="https://api.cohere.ai/v1/generate",
        max_tokens=4096,
        supports_streaming=True,
        supports_function_calling=False,
        supports_vision=False,
        cost_per_1k_input_tokens=0.001,
        cost_per_1k_output_tokens=0.002,
        strengths=[
            "Good for summarization",
            "Enterprise-focused",
            "Strong multilingual",
            "Cost-effective"
        ],
        best_for=[
            "Document summarization",
            "Enterprise use cases",
            "Multilingual support",
            "Cost-effective deployments"
        ]
    ),
}

class BaseAIProvider(ABC):
    """Base class for AI providers"""

    def __init__(self, config: AIProviderConfig, api_key: str):
        self.config = config
        self.api_key = api_key

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response from AI provider"""
        pass

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """Stream response from AI provider"""
        pass


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT provider"""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using OpenAI API"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.config.max_tokens
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.config.api_base_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenAI API error: {error_text}")

                result = await response.json()
                return {
                    "provider": self.config.provider.value,
                    "model": self.config.model_id,
                    "response": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {}),
                    "finish_reason": result["choices"][0].get("finish_reason")
                }

    async def stream_generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        """Stream generation (implement if needed)"""
        # Implementation for streaming
        pass


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude provider"""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using Anthropic API"""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model_id,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        if system_prompt:
            payload["system"] = system_prompt

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.config.api_base_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Anthropic API error: {error_text}")

                result = await response.json()
                return {
                    "provider": self.config.provider.value,
                    "model": self.config.model_id,
                    "response": result["content"][0]["text"],
                    "usage": result.get("usage", {}),
                    "stop_reason": result.get("stop_reason")
                }

    async def stream_generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        """Stream generation"""
        pass


class GoogleGeminiProvider(BaseAIProvider):
    """Google Gemini provider"""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using Google Gemini API"""
        url = f"{self.config.api_base_url}?key={self.api_key}"

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": full_prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or self.config.max_tokens
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Gemini API error: {error_text}")

                result = await response.json()
                return {
                    "provider": self.config.provider.value,
                    "model": self.config.model_id,
                    "response": result["candidates"][0]["content"]["parts"][0]["text"],
                    "usage": result.get("usageMetadata", {}),
                    "finish_reason": result["candidates"][0].get("finishReason")
                }

    async def stream_generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        """Stream generation"""
        pass


class PerplexityProvider(BaseAIProvider):
    """Perplexity AI provider with web search"""

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using Perplexity API with web search"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.config.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.config.max_tokens
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.config.api_base_url,
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Perplexity API error: {error_text}")

                result = await response.json()
                return {
                    "provider": self.config.provider.value,
                    "model": self.config.model_id,
                    "response": result["choices"][0]["message"]["content"],
                    "citations": result.get("citations", []),  # Perplexity includes web citations
                    "usage": result.get("usage", {}),
                }

    async def stream_generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        """Stream generation"""
        pass


class MultiAIOrchestrator:
    """
    Orchestrates multiple AI providers for optimal results
    Can use consensus, fallback, or specialized routing
    """

    def __init__(self):
        self.providers: Dict[AIProvider, BaseAIProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all available AI providers based on API keys"""
        # OpenAI
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.providers[AIProvider.OPENAI_GPT4] = OpenAIProvider(
                PROVIDER_CONFIGS[AIProvider.OPENAI_GPT4],
                openai_key
            )

        # Anthropic Claude
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.providers[AIProvider.ANTHROPIC_CLAUDE_OPUS] = AnthropicProvider(
                PROVIDER_CONFIGS[AIProvider.ANTHROPIC_CLAUDE_OPUS],
                anthropic_key
            )
            self.providers[AIProvider.ANTHROPIC_CLAUDE_SONNET] = AnthropicProvider(
                PROVIDER_CONFIGS[AIProvider.ANTHROPIC_CLAUDE_SONNET],
                anthropic_key
            )

        # Google Gemini
        gemini_key = os.getenv("GOOGLE_API_KEY")
        if gemini_key:
            self.providers[AIProvider.GOOGLE_GEMINI_PRO] = GoogleGeminiProvider(
                PROVIDER_CONFIGS[AIProvider.GOOGLE_GEMINI_PRO],
                gemini_key
            )

        # Perplexity
        perplexity_key = os.getenv("PERPLEXITY_API_KEY")
        if perplexity_key:
            self.providers[AIProvider.PERPLEXITY_ONLINE] = PerplexityProvider(
                PROVIDER_CONFIGS[AIProvider.PERPLEXITY_ONLINE],
                perplexity_key
            )

    async def generate_with_provider(
        self,
        provider: AIProvider,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using a specific provider"""
        if provider not in self.providers:
            # Fallback to available provider
            provider = list(self.providers.keys())[0]

        return await self.providers[provider].generate(
            prompt=prompt,
            system_prompt=system_prompt,
            **kwargs
        )

    async def generate_with_consensus(
        self,
        providers: List[AIProvider],
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate responses from multiple providers and find consensus
        Used for high-stakes decisions requiring verification
        """
        tasks = []
        for provider in providers:
            if provider in self.providers:
                task = self.providers[provider].generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    **kwargs
                )
                tasks.append(task)

        # Run all providers in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out errors
        valid_results = [r for r in results if not isinstance(r, Exception)]

        if not valid_results:
            raise Exception("All AI providers failed")

        # For now, return the first result with a note about consensus
        # In production, implement actual consensus logic (similarity analysis, voting, etc.)
        return {
            "provider": "consensus",
            "models": [r["model"] for r in valid_results],
            "response": valid_results[0]["response"],
            "consensus_responses": [r["response"] for r in valid_results],
            "agreement_score": self._calculate_agreement(valid_results)
        }

    def _calculate_agreement(self, results: List[Dict[str, Any]]) -> float:
        """Calculate agreement score between multiple responses"""
        # Simple implementation - in production, use semantic similarity
        if len(results) < 2:
            return 1.0

        # Placeholder: calculate based on response length similarity
        lengths = [len(r["response"]) for r in results]
        avg_length = sum(lengths) / len(lengths)
        variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)

        # High variance = low agreement
        agreement = 1.0 / (1.0 + variance / (avg_length ** 2))
        return min(1.0, agreement)

    def select_optimal_provider(
        self,
        task_type: str,
        requires_web_search: bool = False,
        context_size: int = 0,
        budget_conscious: bool = False
    ) -> AIProvider:
        """
        Select the optimal AI provider based on task requirements
        """
        # Web search required
        if requires_web_search and AIProvider.PERPLEXITY_ONLINE in self.providers:
            return AIProvider.PERPLEXITY_ONLINE

        # Large context
        if context_size > 32000 and AIProvider.ANTHROPIC_CLAUDE_OPUS in self.providers:
            return AIProvider.ANTHROPIC_CLAUDE_OPUS

        # Budget conscious
        if budget_conscious and AIProvider.GOOGLE_GEMINI_PRO in self.providers:
            return AIProvider.GOOGLE_GEMINI_PRO

        # Default to GPT-4 or first available
        if AIProvider.OPENAI_GPT4 in self.providers:
            return AIProvider.OPENAI_GPT4

        # Return first available provider
        return list(self.providers.keys())[0]

    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available providers for UI"""
        return [
            {
                "id": provider.value,
                "name": PROVIDER_CONFIGS[provider].name,
                "strengths": PROVIDER_CONFIGS[provider].strengths,
                "best_for": PROVIDER_CONFIGS[provider].best_for
            }
            for provider in self.providers.keys()
        ]


# Singleton instance
multi_ai_orchestrator = MultiAIOrchestrator()
