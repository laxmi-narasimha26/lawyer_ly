"""
Advanced Prompt Engineering System
Implements state-of-the-art prompt engineering techniques used by GPT-4, Claude, and other leading AI models
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import json

class PromptTechnique(Enum):
    """Advanced prompt engineering techniques"""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    TREE_OF_THOUGHTS = "tree_of_thoughts"
    SELF_CONSISTENCY = "self_consistency"
    CONSTITUTIONAL_AI = "constitutional_ai"
    FEW_SHOT_LEARNING = "few_shot_learning"
    ZERO_SHOT_COT = "zero_shot_cot"
    ROLE_PROMPTING = "role_prompting"
    XML_STRUCTURED = "xml_structured"
    INSTRUCTION_FOLLOWING = "instruction_following"
    RETRIEVAL_AUGMENTED = "retrieval_augmented"
    SELF_CRITIQUE = "self_critique"
    MULTI_PERSPECTIVE = "multi_perspective"

@dataclass
class PromptTemplate:
    """Template for constructing advanced prompts"""
    name: str
    technique: PromptTechnique
    template: str
    variables: List[str]
    examples: List[Dict[str, str]]
    metadata: Dict[str, Any]

class AdvancedPromptEngineer:
    """
    Advanced Prompt Engineering System
    Applies cutting-edge techniques for optimal AI responses
    """

    def __init__(self):
        self.templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[PromptTechnique, PromptTemplate]:
        """Initialize prompt templates for each technique"""
        return {
            PromptTechnique.CHAIN_OF_THOUGHT: PromptTemplate(
                name="Chain of Thought Reasoning",
                technique=PromptTechnique.CHAIN_OF_THOUGHT,
                template="""<role>{role}</role>

<task>
{task_description}
</task>

<thinking_process>
Let's approach this step-by-step:
1. First, identify the key legal issues and relevant laws
2. Then, analyze how these laws apply to the specific facts
3. Next, consider any exceptions, defenses, or counterarguments
4. Finally, provide a reasoned conclusion with supporting precedents

Please show your reasoning process explicitly before providing your final answer.
</thinking_process>

<user_query>
{user_query}
</user_query>

<response_format>
Structure your response as:
1. **Initial Analysis**: What are the key issues?
2. **Step-by-Step Reasoning**: Show your thought process
3. **Legal Application**: Apply law to facts
4. **Conclusion**: Final answer with citations
</response_format>""",
                variables=["role", "task_description", "user_query"],
                examples=[],
                metadata={"complexity": "medium", "token_cost": "high"}
            ),

            PromptTechnique.TREE_OF_THOUGHTS: PromptTemplate(
                name="Tree of Thoughts (Advanced Reasoning)",
                technique=PromptTechnique.TREE_OF_THOUGHTS,
                template="""<role>{role}</role>

<advanced_reasoning_instructions>
For this complex legal question, explore multiple reasoning paths:

1. **Branch 1 - Plaintiff/Petitioner Perspective**:
   - What arguments support this side?
   - What are the strengths of this position?

2. **Branch 2 - Defendant/Respondent Perspective**:
   - What counterarguments exist?
   - What are the weaknesses in the opposing position?

3. **Branch 3 - Neutral Judge Perspective**:
   - How would a court likely balance these arguments?
   - What precedents are most relevant?

4. **Synthesis**:
   - Evaluate which reasoning path is most persuasive
   - Provide balanced analysis considering all perspectives
</advanced_reasoning_instructions>

<user_query>
{user_query}
</user_query>

Think through each branch carefully, then synthesize your analysis into a comprehensive response.""",
                variables=["role", "user_query"],
                examples=[],
                metadata={"complexity": "very_high", "token_cost": "very_high"}
            ),

            PromptTechnique.CONSTITUTIONAL_AI: PromptTemplate(
                name="Constitutional AI (Harmlessness + Helpfulness)",
                technique=PromptTechnique.CONSTITUTIONAL_AI,
                template="""<constitutional_principles>
You are bound by these principles:
1. **Accuracy**: Provide legally accurate information citing proper sources
2. **Ethics**: Maintain attorney-client privilege and professional ethics
3. **Disclaimer**: Always note that AI advice doesn't replace qualified legal counsel
4. **Harm Prevention**: Refuse to assist with illegal activities or unethical practices
5. **Transparency**: Acknowledge limitations and uncertainties
6. **Helpfulness**: Strive to provide maximum value while respecting boundaries
</constitutional_principles>

<role>{role}</role>

<self_critique>
Before answering, ask yourself:
- Is this response legally accurate?
- Does it maintain ethical standards?
- Have I provided appropriate disclaimers?
- Am I being maximally helpful within proper boundaries?
</self_critique>

<user_query>
{user_query}
</user_query>

Provide your response following constitutional AI principles, with self-critique if needed.""",
                variables=["role", "user_query"],
                examples=[],
                metadata={"complexity": "medium", "focus": "ethics"}
            ),

            PromptTechnique.FEW_SHOT_LEARNING: PromptTemplate(
                name="Few-Shot Learning with Examples",
                technique=PromptTechnique.FEW_SHOT_LEARNING,
                template="""<role>{role}</role>

<task_description>
{task_description}
</task_description>

<examples>
{examples}
</examples>

<pattern_recognition>
Notice the pattern in the examples above:
- Clear identification of legal issues
- Systematic analysis with citations
- Practical recommendations
- Professional tone and structure
</pattern_recognition>

<user_query>
Now, apply the same approach to this query:
{user_query}
</user_query>""",
                variables=["role", "task_description", "examples", "user_query"],
                examples=[],
                metadata={"complexity": "low", "best_for": "structured_tasks"}
            ),

            PromptTechnique.SELF_CONSISTENCY: PromptTemplate(
                name="Self-Consistency (Multiple Reasoning Paths)",
                technique=PromptTechnique.SELF_CONSISTENCY,
                template="""<role>{role}</role>

<self_consistency_instruction>
Approach this question through multiple independent reasoning paths:

**Path 1 - Statutory Analysis**:
Start from the applicable statutes and work forward

**Path 2 - Case Law Analysis**:
Start from relevant precedents and apply to facts

**Path 3 - First Principles**:
Reason from fundamental legal principles

**Consistency Check**:
Do all three paths lead to the same conclusion? If not, explain why and identify the most persuasive path.
</self_consistency_instruction>

<user_query>
{user_query}
</user_query>

Provide your analysis showing multiple reasoning paths and synthesizing the most consistent answer.""",
                variables=["role", "user_query"],
                examples=[],
                metadata={"complexity": "high", "reliability": "very_high"}
            ),

            PromptTechnique.XML_STRUCTURED: PromptTemplate(
                name="XML-Structured Response (Claude-optimized)",
                technique=PromptTechnique.XML_STRUCTURED,
                template="""<role>{role}</role>

<instructions>
Analyze the following legal query and provide a structured XML response.
</instructions>

<user_query>
{user_query}
</user_query>

<response_schema>
Provide your response in this XML structure:

<analysis>
  <issues>
    <issue priority="high|medium|low">
      <description>...</description>
      <applicable_law>...</applicable_law>
      <analysis>...</analysis>
    </issue>
  </issues>

  <reasoning>
    <step number="1">...</step>
    <step number="2">...</step>
  </reasoning>

  <conclusion>
    <summary>...</summary>
    <recommendations>
      <recommendation priority="1">...</recommendation>
    </recommendations>
  </conclusion>

  <citations>
    <citation>...</citation>
  </citations>
</analysis>
</response_schema>""",
                variables=["role", "user_query"],
                examples=[],
                metadata={"complexity": "medium", "structured": True}
            ),

            PromptTechnique.MULTI_PERSPECTIVE: PromptTemplate(
                name="Multi-Perspective Analysis",
                technique=PromptTechnique.MULTI_PERSPECTIVE,
                template="""<role>{role}</role>

<multi_perspective_analysis>
Analyze this legal matter from multiple professional perspectives:

1. **As a Litigator**: What's the trial strategy and likelihood of success?
2. **As a Transactional Lawyer**: How could this be structured to avoid disputes?
3. **As a Judge**: How would the court likely rule and why?
4. **As an In-House Counsel**: What business considerations matter?
5. **As a Law Professor**: What are the theoretical and doctrinal issues?

Synthesize these perspectives into comprehensive practical advice.
</multi_perspective_analysis>

<user_query>
{user_query}
</user_query>

Provide your multi-perspective analysis with final integrated recommendations.""",
                variables=["role", "user_query"],
                examples=[],
                metadata={"complexity": "very_high", "comprehensive": True}
            ),

            PromptTechnique.SELF_CRITIQUE: PromptTemplate(
                name="Self-Critique and Refinement",
                technique=PromptTechnique.SELF_CRITIQUE,
                template="""<role>{role}</role>

<self_critique_process>
Use this iterative process:
1. **Initial Answer**: Provide your first analysis
2. **Self-Critique**: Identify weaknesses, gaps, or errors
3. **Refinement**: Improve the answer addressing the critique
4. **Final Verification**: Ensure accuracy and completeness
</self_critique_process>

<user_query>
{user_query}
</user_query>

<output_format>
Present your response showing:
- Initial analysis
- Self-critique (what could be improved?)
- Refined analysis (incorporating improvements)
- Final answer with confidence level
</output_format>""",
                variables=["role", "user_query"],
                examples=[],
                metadata={"complexity": "high", "quality": "very_high"}
            ),
        }

    def apply_technique(
        self,
        technique: PromptTechnique,
        user_query: str,
        role: str,
        context: Optional[Dict[str, Any]] = None,
        persona_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Apply a specific prompt engineering technique

        Args:
            technique: The technique to apply
            user_query: The user's question
            role: The AI's role/persona
            context: Additional context (case history, documents, etc.)
            persona_config: Persona-specific configuration

        Returns:
            Engineered prompt ready for AI model
        """
        template = self.templates.get(technique)
        if not template:
            # Fallback to simple prompt
            return f"{role}\n\n{user_query}"

        # Populate template variables
        prompt = template.template
        prompt = prompt.replace("{role}", role)
        prompt = prompt.replace("{user_query}", user_query)

        # Add persona-specific enhancements if available
        if persona_config:
            task_description = persona_config.get("task_description", "")
            prompt = prompt.replace("{task_description}", task_description)

            # Add few-shot examples if persona provides them
            if technique == PromptTechnique.FEW_SHOT_LEARNING:
                examples_text = self._format_examples(persona_config.get("examples", []))
                prompt = prompt.replace("{examples}", examples_text)

        # Add contextual information if available
        if context:
            prompt = self._inject_context(prompt, context)

        return prompt

    def _format_examples(self, examples: List[Dict[str, str]]) -> str:
        """Format few-shot examples for the prompt"""
        if not examples:
            return ""

        formatted = []
        for i, example in enumerate(examples, 1):
            formatted.append(f"""
**Example {i}:**

**Query**: {example.get('query', '')}

**Response**: {example.get('response', '')}
""")

        return "\n".join(formatted)

    def _inject_context(self, prompt: str, context: Dict[str, Any]) -> str:
        """Inject contextual information into the prompt"""
        context_section = "\n<context>\n"

        if context.get("conversation_history"):
            context_section += "<conversation_history>\n"
            for msg in context["conversation_history"][-5:]:  # Last 5 messages
                context_section += f"{msg['role']}: {msg['content']}\n"
            context_section += "</conversation_history>\n"

        if context.get("documents"):
            context_section += f"<documents_uploaded>\n"
            context_section += f"User has uploaded {len(context['documents'])} document(s) for analysis.\n"
            context_section += "</documents_uploaded>\n"

        if context.get("case_context"):
            context_section += f"<case_context>\n{context['case_context']}\n</case_context>\n"

        context_section += "</context>\n\n"

        # Insert context before user_query
        return prompt.replace("<user_query>", context_section + "<user_query>")

    def get_optimal_technique(
        self,
        query_complexity: str,
        response_type: str,
        token_budget: int
    ) -> PromptTechnique:
        """
        Recommend optimal technique based on query characteristics

        Args:
            query_complexity: "low", "medium", "high", "very_high"
            response_type: "quick", "balanced", "comprehensive"
            token_budget: Maximum tokens available

        Returns:
            Recommended prompt technique
        """
        # Token-constrained scenarios
        if token_budget < 2000:
            return PromptTechnique.ZERO_SHOT_COT

        # Quick responses
        if response_type == "quick":
            return PromptTechnique.INSTRUCTION_FOLLOWING

        # Complex queries
        if query_complexity in ["very_high"]:
            if token_budget > 5000:
                return PromptTechnique.TREE_OF_THOUGHTS
            else:
                return PromptTechnique.CHAIN_OF_THOUGHT

        # High-reliability scenarios
        if response_type == "comprehensive":
            return PromptTechnique.SELF_CONSISTENCY

        # Balanced approach
        return PromptTechnique.CHAIN_OF_THOUGHT

    def create_meta_prompt(
        self,
        base_prompt: str,
        techniques: List[PromptTechnique],
        persona_name: str
    ) -> str:
        """
        Create a meta-prompt combining multiple techniques

        This advanced approach layers multiple prompt engineering techniques
        for maximum quality and reliability.
        """
        meta_prompt = f"""<system>
You are {persona_name}, engaging in advanced reasoning to provide the highest quality legal analysis.
</system>

<meta_instructions>
Apply these advanced techniques in sequence:
"""

        for i, technique in enumerate(techniques, 1):
            template = self.templates.get(technique)
            if template:
                meta_prompt += f"{i}. **{template.name}**: {template.metadata.get('description', 'Apply this technique')}\n"

        meta_prompt += "</meta_instructions>\n\n"
        meta_prompt += base_prompt

        return meta_prompt


class ContextManager:
    """
    Advanced Context Management System
    Implements sliding window, hierarchical memory, and episodic memory
    """

    def __init__(self, max_context_tokens: int = 8000):
        self.max_context_tokens = max_context_tokens
        self.sliding_window_size = 10  # Number of recent messages

    def build_context_window(
        self,
        conversation_history: List[Dict[str, str]],
        documents: List[Dict[str, Any]],
        case_summary: Optional[str] = None,
        mode: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Build an optimized context window using advanced memory techniques

        Args:
            conversation_history: Full conversation history
            documents: Uploaded documents with embeddings
            case_summary: Optional high-level case summary
            mode: "quick" (minimal context), "balanced", "deep" (maximum context)

        Returns:
            Optimized context dictionary
        """
        context = {
            "recent_messages": [],
            "relevant_history": [],
            "document_context": [],
            "case_summary": case_summary,
            "metadata": {}
        }

        # 1. Sliding Window - Most recent messages (always included)
        context["recent_messages"] = conversation_history[-self.sliding_window_size:]

        # 2. Hierarchical Memory - Important past messages
        if mode in ["balanced", "deep"]:
            context["relevant_history"] = self._extract_relevant_history(
                conversation_history[:-self.sliding_window_size]
            )

        # 3. Document Context
        if documents and mode != "quick":
            context["document_context"] = self._summarize_documents(documents)

        # 4. Episodic Memory - Key moments in the conversation
        if mode == "deep":
            context["key_episodes"] = self._extract_key_episodes(conversation_history)

        return context

    def _extract_relevant_history(
        self,
        history: List[Dict[str, str]],
        max_messages: int = 5
    ) -> List[Dict[str, str]]:
        """Extract most relevant historical messages using importance scoring"""
        # Simple heuristic: messages with citations, long responses, or user confirmations
        scored = []
        for msg in history:
            score = 0
            content = msg.get("content", "")

            # Higher score for messages with citations
            if "citations" in msg or "Section" in content or "v." in content:
                score += 3

            # Higher score for longer, detailed messages
            if len(content) > 500:
                score += 2

            # Higher score for user feedback
            if msg.get("role") == "user" and any(word in content.lower() for word in ["good", "perfect", "thanks", "correct"]):
                score += 2

            scored.append((score, msg))

        # Sort by score and take top N
        scored.sort(key=lambda x: x[0], reverse=True)
        return [msg for score, msg in scored[:max_messages]]

    def _summarize_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """Create concise document summaries for context"""
        summaries = []
        for doc in documents:
            summaries.append({
                "filename": doc.get("filename", "Unknown"),
                "type": doc.get("type", "Unknown"),
                "summary": doc.get("summary", "Document uploaded for analysis")[:200]
            })
        return summaries

    def _extract_key_episodes(
        self,
        conversation: List[Dict[str, str]],
        max_episodes: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Extract key conversational episodes (turning points, decisions, important facts)

        This implements episodic memory - remembering specific important moments
        """
        episodes = []

        # Look for patterns indicating important moments
        for i, msg in enumerate(conversation):
            content = msg.get("content", "").lower()

            # Decision points
            if any(phrase in content for phrase in ["decided to", "agreed that", "conclusion is", "recommend"]):
                episodes.append({
                    "type": "decision",
                    "position": i,
                    "message": msg,
                    "importance": "high"
                })

            # Key facts
            if any(phrase in content for phrase in ["important to note", "key fact", "critical", "must understand"]):
                episodes.append({
                    "type": "key_fact",
                    "position": i,
                    "message": msg,
                    "importance": "high"
                })

        # Sort by importance and position, take top N
        episodes.sort(key=lambda x: (x["importance"], -x["position"]), reverse=True)
        return episodes[:max_episodes]


# Singleton instance
prompt_engineer = AdvancedPromptEngineer()
context_manager = ContextManager()
