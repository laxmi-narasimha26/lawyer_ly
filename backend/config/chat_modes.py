"""
Advanced Chat Modes Configuration
5 specialized modes for different use cases and complexity levels
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

class ChatMode(Enum):
    """Advanced chat mode types"""
    QUICK_RESPONSE = "quick_response"
    BALANCED = "balanced"
    DEEP_RESEARCH = "deep_research"
    MULTI_QUERY_ANALYSIS = "multi_query_analysis"
    FULL_CONTEXT_REVIEW = "full_context_review"

@dataclass
class ModeConfig:
    """Configuration for each chat mode"""
    name: str
    mode_type: ChatMode
    description: str
    use_cases: List[str]
    context_strategy: str
    prompt_technique: str
    max_context_messages: int
    enable_web_search: bool
    enable_document_analysis: bool
    enable_multi_model: bool
    token_budget: int
    response_time_target: str
    temperature: float
    features: List[str]
    icon: str
    color_scheme: str

CHAT_MODES: Dict[ChatMode, ModeConfig] = {
    ChatMode.QUICK_RESPONSE: ModeConfig(
        name="⚡ Quick Response",
        mode_type=ChatMode.QUICK_RESPONSE,
        description="Fast answers for straightforward legal questions. Perfect for quick clarifications, definitions, and simple procedural questions.",
        use_cases=[
            "Quick legal definitions",
            "Simple procedural questions",
            "Statute lookups",
            "Basic eligibility checks",
            "Quick citation verification"
        ],
        context_strategy="minimal",  # Only last 2-3 messages
        prompt_technique="zero_shot_cot",  # Simple chain of thought
        max_context_messages=3,
        enable_web_search=False,
        enable_document_analysis=False,
        enable_multi_model=False,
        token_budget=1500,
        response_time_target="< 5 seconds",
        temperature=0.3,  # More deterministic
        features=[
            "Minimal context for speed",
            "Single AI model (fastest)",
            "No web search",
            "Direct answers with basic citations",
            "Optimized for latency"
        ],
        icon="⚡",
        color_scheme="cyan"
    ),

    ChatMode.BALANCED: ModeConfig(
        name="⚖️ Balanced",
        mode_type=ChatMode.BALANCED,
        description="Default mode balancing speed, accuracy, and depth. Best for most legal queries requiring moderate research and context.",
        use_cases=[
            "Contract analysis",
            "Legal strategy discussions",
            "Case law research",
            "Compliance questions",
            "Standard legal drafting"
        ],
        context_strategy="sliding_window",  # Last 5-10 messages
        prompt_technique="chain_of_thought",
        max_context_messages=10,
        enable_web_search=True,  # Limited web search
        enable_document_analysis=True,
        enable_multi_model=False,
        token_budget=3000,
        response_time_target="< 15 seconds",
        temperature=0.5,  # Balanced creativity/accuracy
        features=[
            "Moderate conversation context",
            "Smart web search when needed",
            "Document analysis included",
            "Structured responses with citations",
            "Good balance of speed and depth"
        ],
        icon="⚖️",
        color_scheme="blue"
    ),

    ChatMode.DEEP_RESEARCH: ModeConfig(
        name="🔬 Deep Research",
        mode_type=ChatMode.DEEP_RESEARCH,
        description="Comprehensive legal research mode with extensive web search, multiple sources, and thorough analysis. For complex matters requiring in-depth investigation.",
        use_cases=[
            "Complex litigation strategy",
            "Novel legal issues",
            "Comprehensive precedent research",
            "Multi-jurisdictional analysis",
            "Academic legal research"
        ],
        context_strategy="hierarchical_memory",  # Full context with importance weighting
        prompt_technique="tree_of_thoughts",  # Multiple reasoning paths
        max_context_messages=20,
        enable_web_search=True,  # Extensive web search
        enable_document_analysis=True,
        enable_multi_model=True,  # Multiple AI models for verification
        token_budget=6000,
        response_time_target="< 45 seconds",
        temperature=0.6,  # More creative for novel issues
        features=[
            "Extensive legal database search",
            "Multiple web sources verification",
            "Cross-reference case law",
            "Multi-model consensus (GPT-4 + Claude)",
            "Comprehensive citation analysis",
            "Alternative argument exploration",
            "Academic and practitioner perspectives"
        ],
        icon="🔬",
        color_scheme="purple"
    ),

    ChatMode.MULTI_QUERY_ANALYSIS: ModeConfig(
        name="🎯 Multi-Query Analysis",
        mode_type=ChatMode.MULTI_QUERY_ANALYSIS,
        description="Analyzes current query in context of past 5-10 queries/responses. Perfect for iterative analysis and building on previous discussions.",
        use_cases=[
            "Iterative contract negotiation",
            "Evolving case strategy",
            "Progressive legal research",
            "Multi-issue case analysis",
            "Comparative analysis across queries"
        ],
        context_strategy="episodic_memory",  # Remember key episodes
        prompt_technique="multi_perspective",
        max_context_messages=10,
        enable_web_search=True,
        enable_document_analysis=True,
        enable_multi_model=False,
        token_budget=4000,
        response_time_target="< 25 seconds",
        temperature=0.5,
        features=[
            "Analyzes patterns across queries",
            "Tracks evolving positions",
            "Identifies contradictions",
            "Builds comprehensive timeline",
            "Connects related issues",
            "Synthesizes multi-query insights"
        ],
        icon="🎯",
        color_scheme="orange"
    ),

    ChatMode.FULL_CONTEXT_REVIEW: ModeConfig(
        name="📚 Full Context Review",
        mode_type=ChatMode.FULL_CONTEXT_REVIEW,
        description="Comprehensive mode using entire conversation history, all uploaded documents, and extensive research. For final reviews, comprehensive opinions, and complete case analysis.",
        use_cases=[
            "Final legal opinion drafting",
            "Comprehensive case review",
            "Due diligence summaries",
            "Complete contract analysis",
            "Full regulatory compliance review"
        ],
        context_strategy="full_context",  # Everything
        prompt_technique="self_consistency",  # Multiple reasoning paths for accuracy
        max_context_messages=50,  # Entire conversation
        enable_web_search=True,
        enable_document_analysis=True,
        enable_multi_model=True,
        token_budget=8000,
        response_time_target="< 60 seconds",
        temperature=0.4,  # More conservative for final opinions
        features=[
            "Entire conversation context",
            "All document analysis",
            "Comprehensive web research",
            "Multi-model verification",
            "Cross-reference all prior discussions",
            "Identify inconsistencies",
            "Generate comprehensive report",
            "Quality assurance checks",
            "Final opinion formatting"
        ],
        icon="📚",
        color_scheme="green"
    ),
}

def get_mode_config(mode: ChatMode) -> ModeConfig:
    """Get configuration for a specific chat mode"""
    return CHAT_MODES.get(mode, CHAT_MODES[ChatMode.BALANCED])

def get_all_modes() -> List[ModeConfig]:
    """Get all available chat modes"""
    return list(CHAT_MODES.values())

def select_optimal_mode(
    query_complexity: str,
    has_documents: bool,
    conversation_length: int,
    time_sensitive: bool
) -> ChatMode:
    """
    Automatically select optimal mode based on context

    Args:
        query_complexity: "simple", "moderate", "complex", "very_complex"
        has_documents: Whether user has uploaded documents
        conversation_length: Number of messages in conversation
        time_sensitive: Whether user needs quick response

    Returns:
        Recommended chat mode
    """
    # Time-sensitive queries
    if time_sensitive:
        return ChatMode.QUICK_RESPONSE

    # Long conversations benefit from multi-query analysis
    if conversation_length > 15:
        return ChatMode.MULTI_QUERY_ANALYSIS

    # Complex queries need deep research
    if query_complexity == "very_complex":
        return ChatMode.DEEP_RESEARCH

    # Simple queries
    if query_complexity == "simple" and not has_documents:
        return ChatMode.QUICK_RESPONSE

    # Default balanced mode
    return ChatMode.BALANCED

def get_mode_description_for_ui(mode: ChatMode) -> Dict[str, Any]:
    """Get user-friendly mode description for frontend"""
    config = get_mode_config(mode)

    return {
        "id": mode.value,
        "name": config.name,
        "description": config.description,
        "icon": config.icon,
        "color": config.color_scheme,
        "features": config.features,
        "use_cases": config.use_cases,
        "estimated_time": config.response_time_target,
        "best_for": ", ".join(config.use_cases[:3])
    }
