"""
Multi-AI Provider Integration System
Supports OpenAI, Anthropic Claude, Google Gemini, Cohere, and more
Exploits unique features of each provider for optimal legal AI responses
"""

from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod
import os
import asyncio
import httpx
from datetime import datetime
import json


class AIProvider(str, Enum):
    """Supported AI providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE_GEMINI = "google_gemini"
    COHERE = "cohere"
    TOGETHER_AI = "together_ai"
    MISTRAL = "mistral"


class AIModel(BaseModel):
    """AI Model configuration"""
    provider: AIProvider
    model_name: str
    display_name: str
    context_window: int
    supports_function_calling: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    best_for: List[str] = []
    cost_per_1k_tokens: float = 0.0
    description: str = ""


# Define available models with their unique capabilities
AVAILABLE_MODELS: Dict[str, AIModel] = {
    # OpenAI Models
    "gpt-4-turbo": AIModel(
        provider=AIProvider.OPENAI,
        model_name="gpt-4-turbo-preview",
        display_name="GPT-4 Turbo",
        context_window=128000,
        supports_function_calling=True,
        supports_vision=True,
        supports_json_mode=True,
        best_for=["complex_reasoning", "code_generation", "analysis"],
        cost_per_1k_tokens=0.01,
        description="Most capable OpenAI model with vision and function calling"
    ),
    "gpt-4": AIModel(
        provider=AIProvider.OPENAI,
        model_name="gpt-4",
        display_name="GPT-4",
        context_window=8192,
        supports_function_calling=True,
        supports_json_mode=True,
        best_for=["legal_reasoning", "complex_analysis"],
        cost_per_1k_tokens=0.03,
        description="Powerful reasoning and analysis"
    ),
    "gpt-3.5-turbo": AIModel(
        provider=AIProvider.OPENAI,
        model_name="gpt-3.5-turbo",
        display_name="GPT-3.5 Turbo",
        context_window=16385,
        supports_function_calling=True,
        supports_json_mode=True,
        best_for=["quick_answers", "cost_effective"],
        cost_per_1k_tokens=0.0015,
        description="Fast and cost-effective for simple queries"
    ),

    # Anthropic Claude Models
    "claude-opus": AIModel(
        provider=AIProvider.ANTHROPIC,
        model_name="claude-3-opus-20240229",
        display_name="Claude 3 Opus",
        context_window=200000,
        supports_function_calling=True,
        supports_vision=True,
        best_for=["complex_legal_research", "long_documents", "nuanced_analysis"],
        cost_per_1k_tokens=0.015,
        description="Most capable Claude model with exceptional reasoning"
    ),
    "claude-sonnet": AIModel(
        provider=AIProvider.ANTHROPIC,
        model_name="claude-3-5-sonnet-20241022",
        display_name="Claude 3.5 Sonnet",
        context_window=200000,
        supports_function_calling=True,
        supports_vision=True,
        best_for=["balanced_performance", "coding", "analysis"],
        cost_per_1k_tokens=0.003,
        description="Balanced performance and speed"
    ),
    "claude-haiku": AIModel(
        provider=AIProvider.ANTHROPIC,
        model_name="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        context_window=200000,
        supports_function_calling=False,
        best_for=["fast_responses", "simple_queries"],
        cost_per_1k_tokens=0.00025,
        description="Fastest and most cost-effective Claude model"
    ),

    # Google Gemini Models
    "gemini-pro": AIModel(
        provider=AIProvider.GOOGLE_GEMINI,
        model_name="gemini-1.5-pro",
        display_name="Gemini 1.5 Pro",
        context_window=1000000,  # 1M tokens!
        supports_function_calling=True,
        supports_vision=True,
        supports_json_mode=True,
        best_for=["massive_documents", "multi_modal", "long_context"],
        cost_per_1k_tokens=0.00125,
        description="Largest context window - 1M tokens, excellent for massive documents"
    ),
    "gemini-flash": AIModel(
        provider=AIProvider.GOOGLE_GEMINI,
        model_name="gemini-1.5-flash",
        display_name="Gemini 1.5 Flash",
        context_window=1000000,
        supports_function_calling=True,
        supports_vision=True,
        best_for=["fast_processing", "large_documents"],
        cost_per_1k_tokens=0.000075,
        description="Extremely fast with 1M context"
    ),

    # Cohere Models
    "command-r-plus": AIModel(
        provider=AIProvider.COHERE,
        model_name="command-r-plus",
        display_name="Command R+",
        context_window=128000,
        supports_function_calling=True,
        best_for=["rag", "retrieval", "citations"],
        cost_per_1k_tokens=0.003,
        description="Optimized for RAG and retrieval tasks with grounded citations"
    ),
}


class AIResponse(BaseModel):
    """Standardized AI response"""
    content: str
    model: str
    provider: AIProvider
    usage: Dict[str, int] = {}
    finish_reason: str = "stop"
    citations: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class BaseAIProvider(ABC):
    """Base class for AI providers"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = self._initialize_client()

    @abstractmethod
    def _initialize_client(self):
        """Initialize provider-specific client"""
        pass

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs
    ) -> AIResponse:
        """Generate response"""
        pass


class OpenAIProvider(BaseAIProvider):
    """OpenAI GPT provider with advanced features"""

    def _initialize_client(self):
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self.api_key)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        json_mode: bool = False,
        functions: Optional[List[Dict]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate using OpenAI"""
        try:
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            # Unique feature: JSON mode
            if json_mode:
                params["response_format"] = {"type": "json_object"}

            # Unique feature: Function calling
            if functions:
                params["functions"] = functions
                params["function_call"] = "auto"

            response = await self.client.chat.completions.create(**params)

            return AIResponse(
                content=response.choices[0].message.content or "",
                model=model,
                provider=AIProvider.OPENAI,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                finish_reason=response.choices[0].finish_reason,
                metadata={"response_id": response.id}
            )

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")


class AnthropicProvider(BaseAIProvider):
    """Anthropic Claude provider with unique capabilities"""

    def _initialize_client(self):
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self.api_key)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AIResponse:
        """Generate using Claude with extended thinking"""
        try:
            # Unique feature: Extended thinking (for Opus and Sonnet)
            # Claude excels at long-form reasoning
            params = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }

            # Claude-specific: System prompt is separate parameter
            if system_prompt:
                params["system"] = system_prompt
            else:
                # Extract system message if present
                if messages and messages[0].get("role") == "system":
                    params["system"] = messages[0]["content"]
                    messages = messages[1:]
                    params["messages"] = messages

            response = await self.client.messages.create(**params)

            return AIResponse(
                content=response.content[0].text,
                model=model,
                provider=AIProvider.ANTHROPIC,
                usage={
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens
                },
                finish_reason=response.stop_reason,
                metadata={"response_id": response.id}
            )

        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")


class GoogleGeminiProvider(BaseAIProvider):
    """Google Gemini provider with 1M token context"""

    def _initialize_client(self):
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        return genai

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-1.5-pro",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        **kwargs
    ) -> AIResponse:
        """Generate using Gemini - exploit massive 1M context"""
        try:
            # Unique feature: 1 million token context window
            # Perfect for analyzing entire legal codebooks, massive case files

            genai_model = self.client.GenerativeModel(model)

            # Convert messages to Gemini format
            history = []
            current_message = ""

            for msg in messages:
                role = "user" if msg["role"] in ["user", "system"] else "model"
                content = msg["content"]

                if role == "user":
                    current_message = content
                else:
                    history.append({
                        "role": "user",
                        "parts": [current_message]
                    })
                    history.append({
                        "role": "model",
                        "parts": [content]
                    })
                    current_message = ""

            # Generate
            chat = genai_model.start_chat(history=history[:-1] if history else [])

            response = await asyncio.to_thread(
                chat.send_message,
                current_message,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                }
            )

            return AIResponse(
                content=response.text,
                model=model,
                provider=AIProvider.GOOGLE_GEMINI,
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count,
                    "completion_tokens": response.usage_metadata.candidates_token_count,
                    "total_tokens": response.usage_metadata.total_token_count
                },
                finish_reason="stop",
                metadata={}
            )

        except Exception as e:
            raise Exception(f"Google Gemini API error: {str(e)}")


class CohereProvider(BaseAIProvider):
    """Cohere provider optimized for RAG and citations"""

    def _initialize_client(self):
        import cohere
        return cohere.AsyncClient(api_key=self.api_key)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "command-r-plus",
        temperature: float = 0.3,
        max_tokens: int = 4000,
        documents: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> AIResponse:
        """Generate using Cohere - exploit grounded generation with citations"""
        try:
            # Unique feature: Grounded generation with automatic citations
            # Perfect for legal AI where citations are critical

            # Convert messages to Cohere format
            message = messages[-1]["content"] if messages else ""

            # Build chat history
            chat_history = []
            for i in range(0, len(messages) - 1, 2):
                if i + 1 < len(messages):
                    chat_history.append({
                        "role": "USER",
                        "message": messages[i]["content"]
                    })
                    if i + 1 < len(messages):
                        chat_history.append({
                            "role": "CHATBOT",
                            "message": messages[i + 1]["content"]
                        })

            params = {
                "message": message,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "chat_history": chat_history if chat_history else None,
            }

            # Unique feature: Pass documents for grounded generation
            if documents:
                params["documents"] = documents
                params["citation_quality"] = "accurate"  # Cohere-specific
                params["connectors"] = [{"id": "web-search"}]  # Can enable web search

            response = await self.client.chat(**params)

            # Extract Cohere's automatic citations
            citations = []
            if hasattr(response, 'citations') and response.citations:
                for cite in response.citations:
                    citations.append({
                        "text": cite.text,
                        "document_ids": cite.document_ids,
                        "start": cite.start,
                        "end": cite.end
                    })

            return AIResponse(
                content=response.text,
                model=model,
                provider=AIProvider.COHERE,
                usage={
                    "prompt_tokens": response.meta.tokens.input_tokens if hasattr(response.meta, 'tokens') else 0,
                    "completion_tokens": response.meta.tokens.output_tokens if hasattr(response.meta, 'tokens') else 0,
                },
                finish_reason="stop",
                citations=citations,  # Cohere's automatic citations
                metadata={"generation_id": response.generation_id}
            )

        except Exception as e:
            raise Exception(f"Cohere API error: {str(e)}")


class MultiAIOrchestrator:
    """
    Orchestrates multiple AI providers for optimal legal AI responses
    Intelligently routes queries to best provider based on query characteristics
    """

    def __init__(self):
        self.providers: Dict[AIProvider, BaseAIProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize all available providers"""
        # OpenAI
        if os.getenv("OPENAI_API_KEY"):
            self.providers[AIProvider.OPENAI] = OpenAIProvider(
                api_key=os.getenv("OPENAI_API_KEY")
            )

        # Anthropic
        if os.getenv("ANTHROPIC_API_KEY"):
            self.providers[AIProvider.ANTHROPIC] = AnthropicProvider(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )

        # Google Gemini
        if os.getenv("GOOGLE_API_KEY"):
            self.providers[AIProvider.GOOGLE_GEMINI] = GoogleGeminiProvider(
                api_key=os.getenv("GOOGLE_API_KEY")
            )

        # Cohere
        if os.getenv("COHERE_API_KEY"):
            self.providers[AIProvider.COHERE] = CohereProvider(
                api_key=os.getenv("COHERE_API_KEY")
            )

    def get_provider(self, provider: AIProvider) -> Optional[BaseAIProvider]:
        """Get provider instance"""
        return self.providers.get(provider)

    def auto_select_model(
        self,
        query_characteristics: Dict[str, Any]
    ) -> Tuple[AIProvider, str]:
        """
        Automatically select best model based on query characteristics

        Args:
            query_characteristics: Dict with keys like:
                - document_length: int
                - needs_citations: bool
                - complexity: str ("simple", "medium", "complex")
                - needs_vision: bool
                - budget: str ("low", "medium", "high")

        Returns:
            Tuple of (provider, model_name)
        """
        doc_length = query_characteristics.get("document_length", 0)
        needs_citations = query_characteristics.get("needs_citations", True)
        complexity = query_characteristics.get("complexity", "medium")
        needs_vision = query_characteristics.get("needs_vision", False)
        budget = query_characteristics.get("budget", "medium")

        # Massive documents (>100K tokens) -> Gemini Pro (1M context)
        if doc_length > 100000:
            if AIProvider.GOOGLE_GEMINI in self.providers:
                return AIProvider.GOOGLE_GEMINI, "gemini-1.5-pro"

        # Citations critical + RAG -> Cohere Command R+
        if needs_citations and AIProvider.COHERE in self.providers:
            return AIProvider.COHERE, "command-r-plus"

        # Complex reasoning -> Claude Opus or GPT-4
        if complexity == "complex":
            if AIProvider.ANTHROPIC in self.providers:
                return AIProvider.ANTHROPIC, "claude-3-opus-20240229"
            if AIProvider.OPENAI in self.providers:
                return AIProvider.OPENAI, "gpt-4-turbo-preview"

        # Balanced performance -> Claude Sonnet
        if complexity == "medium" and AIProvider.ANTHROPIC in self.providers:
            return AIProvider.ANTHROPIC, "claude-3-5-sonnet-20241022"

        # Budget-conscious -> GPT-3.5 or Claude Haiku
        if budget == "low":
            if AIProvider.ANTHROPIC in self.providers:
                return AIProvider.ANTHROPIC, "claude-3-haiku-20240307"
            if AIProvider.OPENAI in self.providers:
                return AIProvider.OPENAI, "gpt-3.5-turbo"

        # Default: OpenAI GPT-4
        if AIProvider.OPENAI in self.providers:
            return AIProvider.OPENAI, "gpt-4-turbo-preview"

        # Fallback to any available provider
        if self.providers:
            provider = list(self.providers.keys())[0]
            return provider, list(AVAILABLE_MODELS.values())[0].model_name

        raise Exception("No AI providers configured")

    async def generate(
        self,
        messages: List[Dict[str, str]],
        provider: Optional[AIProvider] = None,
        model: Optional[str] = None,
        auto_select: bool = False,
        query_characteristics: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> AIResponse:
        """
        Generate response using specified or auto-selected provider

        Args:
            messages: Conversation messages
            provider: Specific provider to use
            model: Specific model to use
            auto_select: Auto-select optimal model
            query_characteristics: Characteristics for auto-selection
            **kwargs: Provider-specific kwargs

        Returns:
            AIResponse
        """
        # Auto-select if requested
        if auto_select or (not provider and not model):
            characteristics = query_characteristics or {}
            provider, model = self.auto_select_model(characteristics)

        # Get provider
        if not provider:
            raise Exception("Provider not specified")

        provider_instance = self.get_provider(provider)
        if not provider_instance:
            raise Exception(f"Provider {provider} not configured")

        # Generate
        return await provider_instance.generate(
            messages=messages,
            model=model,
            **kwargs
        )


# Global orchestrator instance
ai_orchestrator = MultiAIOrchestrator()


async def generate_legal_response(
    query: str,
    system_prompt: Optional[str] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    retrieved_documents: Optional[List[Dict[str, str]]] = None,
    provider: Optional[AIProvider] = None,
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 4000,
) -> AIResponse:
    """
    High-level function to generate legal responses with optimal AI selection

    Args:
        query: User query
        system_prompt: System prompt
        conversation_history: Previous messages
        retrieved_documents: RAG documents
        provider: Optional specific provider
        model: Optional specific model
        temperature: Generation temperature
        max_tokens: Max tokens to generate

    Returns:
        AIResponse
    """
    # Build messages
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": query})

    # Determine query characteristics for auto-selection
    doc_length = sum(len(doc.get("content", "")) for doc in (retrieved_documents or []))
    characteristics = {
        "document_length": doc_length,
        "needs_citations": True,  # Legal queries always need citations
        "complexity": "complex" if len(query) > 200 else "medium",
        "budget": "medium"
    }

    # Generate
    return await ai_orchestrator.generate(
        messages=messages,
        provider=provider,
        model=model,
        auto_select=not provider and not model,
        query_characteristics=characteristics,
        temperature=temperature,
        max_tokens=max_tokens,
        documents=retrieved_documents  # For Cohere grounded generation
    )
