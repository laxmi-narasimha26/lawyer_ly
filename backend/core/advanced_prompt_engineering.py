"""
Advanced Prompt Engineering Framework
Implements state-of-the-art prompt techniques: CoT, ReAct, Self-Consistency, Tree-of-Thought, etc.
"""

from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field
import json
from datetime import datetime


class PromptTechnique(str, Enum):
    """Advanced prompt engineering techniques"""
    CHAIN_OF_THOUGHT = "chain_of_thought"  # Step-by-step reasoning
    REACT = "react"  # Reasoning + Acting
    SELF_CONSISTENCY = "self_consistency"  # Multiple reasoning paths
    TREE_OF_THOUGHT = "tree_of_thought"  # Explore multiple reasoning trees
    LEAST_TO_MOST = "least_to_most"  # Break down complex problems
    ZERO_SHOT_COT = "zero_shot_cot"  # "Let's think step by step"
    FEW_SHOT = "few_shot"  # Examples-based learning
    ROLE_PROMPTING = "role_prompting"  # Act as an expert
    CONSTITUTIONAL_AI = "constitutional_ai"  # Self-critique and improvement
    PROMPT_CHAINING = "prompt_chaining"  # Multi-step prompts
    META_PROMPTING = "meta_prompting"  # Prompt about prompting
    ANALOGICAL_REASONING = "analogical_reasoning"  # Use analogies


class LegalQueryType(str, Enum):
    """Types of legal queries"""
    CASE_ANALYSIS = "case_analysis"
    LEGAL_RESEARCH = "legal_research"
    CONTRACT_REVIEW = "contract_review"
    DOCUMENT_DRAFTING = "document_drafting"
    LITIGATION_STRATEGY = "litigation_strategy"
    COMPLIANCE_CHECK = "compliance_check"
    LEGAL_OPINION = "legal_opinion"
    PRECEDENT_SEARCH = "precedent_search"
    STATUTORY_INTERPRETATION = "statutory_interpretation"


class PromptTemplate(BaseModel):
    """Structured prompt template"""
    technique: PromptTechnique
    system_prompt: str
    user_prompt_template: str
    examples: List[Dict[str, str]] = []
    metadata: Dict[str, Any] = {}


class AdvancedPromptEngineer:
    """
    Advanced Prompt Engineering System
    Implements cutting-edge techniques for optimal LLM performance
    """

    def __init__(self):
        self.techniques = self._initialize_techniques()

    def _initialize_techniques(self) -> Dict[PromptTechnique, PromptTemplate]:
        """Initialize all prompt engineering techniques"""
        return {
            PromptTechnique.CHAIN_OF_THOUGHT: self._cot_template(),
            PromptTechnique.REACT: self._react_template(),
            PromptTechnique.SELF_CONSISTENCY: self._self_consistency_template(),
            PromptTechnique.TREE_OF_THOUGHT: self._tot_template(),
            PromptTechnique.CONSTITUTIONAL_AI: self._constitutional_ai_template(),
            PromptTechnique.FEW_SHOT: self._few_shot_template(),
        }

    def _cot_template(self) -> PromptTemplate:
        """Chain-of-Thought prompting for legal reasoning"""
        return PromptTemplate(
            technique=PromptTechnique.CHAIN_OF_THOUGHT,
            system_prompt="""You are an expert Indian legal AI assistant. When answering legal questions:

1. **Think Step-by-Step**: Break down complex legal issues into logical steps
2. **Show Your Reasoning**: Explain each step of your legal analysis
3. **Cite Authority**: Reference specific laws, sections, and precedents
4. **Consider Multiple Angles**: Examine issue from different legal perspectives
5. **Reach Conclusion**: Provide clear, reasoned conclusion

Format your response as:
**Legal Issue**: [Identify the core legal question]
**Applicable Law**: [Relevant statutes, sections, and precedents]
**Analysis**: [Step-by-step legal reasoning]
**Conclusion**: [Clear answer with citations]
**Advisory**: [Practical next steps]""",
            user_prompt_template="""Legal Query: {query}

Let's analyze this step-by-step:

Step 1: Identify the legal issue and relevant area of law
Step 2: Determine applicable statutes, regulations, and precedents
Step 3: Analyze how the law applies to the given facts
Step 4: Consider exceptions, defenses, or counter-arguments
Step 5: Reach a reasoned legal conclusion

Please provide a detailed chain-of-thought analysis:""",
            examples=[
                {
                    "query": "Is a contract signed by a minor valid under Indian law?",
                    "response": """**Legal Issue**: Contractual capacity of a minor under Indian Contract Act

**Applicable Law**:
- Indian Contract Act, 1872, Section 11 (Competency to contract)
- Section 68 (Necessaries supplied to minor)
- Leading case: Mohori Bibee v. Dharmodas Ghose (1903)

**Analysis**:
Step 1: Section 11 states that a person is competent to contract if they are of the age of majority according to the law to which they are subject.

Step 2: In India, the age of majority is 18 years (Indian Majority Act, 1875).

Step 3: A minor (person under 18) lacks contractual capacity. Any agreement with a minor is void ab initio (from the beginning), not merely voidable.

Step 4: Limited exception exists under Section 68 for "necessaries" (food, clothing, education) supplied to a minor. The supplier can claim reimbursement from the minor's property.

Step 5: In Mohori Bibee case, Privy Council held that a minor's agreement is absolutely void and cannot be ratified even after attaining majority.

**Conclusion**: A contract signed by a minor is VOID and unenforceable under Indian law, except for necessaries supplied under Section 68.

**Advisory**: Do not enter into contracts with minors. If already executed, the contract cannot be enforced. The minor can seek refund of any consideration paid."""
                }
            ],
            metadata={"best_for": "complex_legal_reasoning"}
        )

    def _react_template(self) -> PromptTemplate:
        """Reasoning + Acting template for legal research"""
        return PromptTemplate(
            technique=PromptTechnique.REACT,
            system_prompt="""You are a legal research AI using ReAct (Reasoning + Acting) methodology.

For each query:
1. **Thought**: Reason about what information you need
2. **Action**: Specify what action to take (search case law, review statute, check precedent)
3. **Observation**: Note findings from the action
4. **Repeat**: Continue Thought-Action-Observation until complete
5. **Final Answer**: Provide comprehensive response

Use this format:
Thought 1: [What do I need to find out?]
Action 1: [What action should I take?]
Observation 1: [What did I find?]
Thought 2: [What's next?]
Action 2: [Next action]
Observation 2: [Next finding]
...
Final Answer: [Complete legal analysis with citations]""",
            user_prompt_template="""Legal Research Query: {query}

Using ReAct methodology, let's systematically research this legal issue:

Thought 1: What is the core legal question and what information do I need to answer it comprehensively?""",
            examples=[],
            metadata={"best_for": "legal_research_complex_queries"}
        )

    def _self_consistency_template(self) -> PromptTemplate:
        """Self-consistency: Generate multiple reasoning paths"""
        return PromptTemplate(
            technique=PromptTechnique.SELF_CONSISTENCY,
            system_prompt="""You will analyze this legal question through MULTIPLE independent reasoning paths, then synthesize the most consistent answer.

Generate 3 different legal analyses:
1. **Analysis Path 1**: Focus on statutory interpretation
2. **Analysis Path 2**: Focus on case law and precedents
3. **Analysis Path 3**: Focus on practical and policy considerations

Then synthesize the most legally sound answer that is consistent across all paths.""",
            user_prompt_template="""Legal Question: {query}

Please provide three independent legal analyses from different perspectives, then synthesize them:

**Analysis Path 1 - Statutory Approach**:
[Analyze based on bare text of statutes]

**Analysis Path 2 - Precedent Approach**:
[Analyze based on case law and judicial interpretation]

**Analysis Path 3 - Practical/Policy Approach**:
[Analyze based on practical application and policy considerations]

**Synthesized Answer**:
[Most consistent and legally sound conclusion across all three paths]""",
            examples=[],
            metadata={"best_for": "ambiguous_legal_questions"}
        )

    def _tot_template(self) -> PromptTemplate:
        """Tree-of-Thought: Explore multiple reasoning branches"""
        return PromptTemplate(
            technique=PromptTechnique.TREE_OF_THOUGHT,
            system_prompt="""You will use Tree-of-Thought reasoning to explore multiple legal arguments and counter-arguments.

Structure:
1. **Trunk**: Core legal issue
2. **Branch A**: First legal argument/interpretation
   - Sub-branch A1: Supporting precedents
   - Sub-branch A2: Potential weaknesses
3. **Branch B**: Alternative legal argument
   - Sub-branch B1: Supporting precedents
   - Sub-branch B2: Potential weaknesses
4. **Branch C**: Third perspective
5. **Evaluation**: Which branch/argument is strongest and why?
6. **Conclusion**: Best legal position""",
            user_prompt_template="""Legal Issue: {query}

Let's explore this issue using Tree-of-Thought reasoning with multiple argumentative branches:""",
            examples=[],
            metadata={"best_for": "litigation_strategy"}
        )

    def _constitutional_ai_template(self) -> PromptTemplate:
        """Constitutional AI: Self-critique and improvement"""
        return PromptTemplate(
            technique=PromptTechnique.CONSTITUTIONAL_AI,
            system_prompt="""You will provide a legal answer, then critique it for accuracy, completeness, and potential issues, then provide an improved version.

Process:
1. **Initial Response**: Provide your first legal analysis
2. **Self-Critique**: Identify potential errors, missing issues, or weaknesses in your analysis
   - Are all relevant statutes cited?
   - Are precedents correctly applied?
   - Are there counter-arguments not addressed?
   - Is the advice practical and ethical?
3. **Improved Response**: Provide enhanced analysis addressing the critique points""",
            user_prompt_template="""Legal Query: {query}

**Initial Response**:
[Provide initial legal analysis]

**Self-Critique**:
[Critique your own response - what's missing? What could be improved? What assumptions did you make?]

**Improved Response**:
[Provide improved legal analysis incorporating the critique]""",
            examples=[],
            metadata={"best_for": "high_stakes_legal_opinions"}
        )

    def _few_shot_template(self) -> PromptTemplate:
        """Few-shot learning with examples"""
        return PromptTemplate(
            technique=PromptTechnique.FEW_SHOT,
            system_prompt="""You are provided with examples of high-quality legal analysis. Study these examples and provide similar analysis for the new query.""",
            user_prompt_template="""Here are examples of excellent legal analysis:

{examples}

Now, provide a similar analysis for this new query:

Query: {query}""",
            examples=[
                {
                    "query": "What is the limitation period for filing a civil suit for recovery of money?",
                    "response": """**Legal Framework**: Limitation Act, 1963, Article 113

**Applicable Period**: 3 years from the date when the money becomes due and payable

**Key Points**:
1. **Starting Point**: Date when the debt becomes due
2. **Extension**: Can be extended if payment is acknowledged in writing (Section 18)
3. **Effect of Expiry**: Suit becomes time-barred but debt not extinguished
4. **Court's Role**: Courts cannot condone delay under Article 113

**Relevant Cases**:
- State of Kerala v. Aluminium Industries Ltd. (1965)
- Baldev Singh v. Manohar Singh (2006)

**Practical Advisory**: File suit well before 3-year period expires. Obtain written acknowledgments to extend limitation."""
                }
            ],
            metadata={"best_for": "consistent_response_format"}
        )

    def construct_prompt(
        self,
        query: str,
        technique: PromptTechnique,
        persona_system_prompt: Optional[str] = None,
        context: Optional[List[Dict[str, str]]] = None,
        retrieved_docs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, str]:
        """
        Construct advanced engineered prompt

        Args:
            query: User's legal query
            technique: Prompt engineering technique to use
            persona_system_prompt: Optional persona-specific system prompt
            context: Conversation context
            retrieved_docs: RAG-retrieved documents
            metadata: Additional metadata

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        template = self.techniques.get(technique)
        if not template:
            technique = PromptTechnique.CHAIN_OF_THOUGHT  # Default
            template = self.techniques[technique]

        # Build system prompt
        system_parts = []

        if persona_system_prompt:
            system_parts.append(persona_system_prompt)

        system_parts.append(template.system_prompt)

        # Add current date context
        system_parts.append(f"\n**Current Date**: {datetime.now().strftime('%B %d, %Y')}")

        # Add RAG context if available
        if retrieved_docs:
            system_parts.append("\n**Retrieved Legal Sources**:")
            for i, doc in enumerate(retrieved_docs[:5], 1):
                system_parts.append(f"\n[Source {i}]: {doc[:500]}...")

        system_prompt = "\n\n".join(system_parts)

        # Build user prompt
        user_prompt = template.user_prompt_template.format(
            query=query,
            examples=self._format_examples(template.examples)
        )

        # Add conversation context if available
        if context:
            context_str = self._format_context(context)
            user_prompt = f"**Previous Conversation Context**:\n{context_str}\n\n{user_prompt}"

        return system_prompt, user_prompt

    def _format_examples(self, examples: List[Dict[str, str]]) -> str:
        """Format few-shot examples"""
        if not examples:
            return ""

        formatted = []
        for i, ex in enumerate(examples, 1):
            formatted.append(f"**Example {i}**:\nQuery: {ex['query']}\nResponse: {ex['response']}\n")

        return "\n".join(formatted)

    def _format_context(self, context: List[Dict[str, str]]) -> str:
        """Format conversation context"""
        formatted = []
        for msg in context[-5:]:  # Last 5 messages
            role = msg.get('role', 'user')
            content = msg.get('content', '')[:200]  # Truncate
            formatted.append(f"{role.title()}: {content}")

        return "\n".join(formatted)

    def construct_legal_reasoning_prompt(
        self,
        query: str,
        query_type: LegalQueryType,
        persona_prompt: Optional[str] = None,
        retrieved_context: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Specialized method for legal reasoning with optimal technique selection

        Args:
            query: Legal query
            query_type: Type of legal query
            persona_prompt: Persona-specific prompts
            retrieved_context: RAG context

        Returns:
            Optimized system and user prompts
        """
        # Auto-select best technique based on query type
        technique_map = {
            LegalQueryType.CASE_ANALYSIS: PromptTechnique.CHAIN_OF_THOUGHT,
            LegalQueryType.LEGAL_RESEARCH: PromptTechnique.REACT,
            LegalQueryType.CONTRACT_REVIEW: PromptTechnique.TREE_OF_THOUGHT,
            LegalQueryType.LITIGATION_STRATEGY: PromptTechnique.TREE_OF_THOUGHT,
            LegalQueryType.LEGAL_OPINION: PromptTechnique.CONSTITUTIONAL_AI,
            LegalQueryType.STATUTORY_INTERPRETATION: PromptTechnique.SELF_CONSISTENCY,
        }

        technique = technique_map.get(query_type, PromptTechnique.CHAIN_OF_THOUGHT)

        return self.construct_prompt(
            query=query,
            technique=technique,
            persona_system_prompt=persona_prompt,
            retrieved_docs=retrieved_context
        )

    def construct_multi_turn_prompt(
        self,
        current_query: str,
        conversation_history: List[Dict[str, str]],
        persona_prompt: str,
        retrieved_docs: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Construct prompt for multi-turn conversations with memory

        Args:
            current_query: Current user query
            conversation_history: Previous conversation turns
            persona_prompt: Active persona system prompt
            retrieved_docs: RAG retrieved documents

        Returns:
            System and user prompts optimized for multi-turn
        """
        system_prompt = f"""{persona_prompt}

**Conversation Mode**: You are engaged in a multi-turn legal consultation. Remember the context of previous questions and maintain consistency in your advice.

**Memory Instructions**:
- Recall relevant information from previous exchanges
- Build upon previous explanations
- Maintain consistent legal positions
- Reference earlier discussion points when relevant
- If user asks follow-up questions, connect to previous context

**Conversation Continuity**: Treat this as an ongoing attorney-client consultation, not isolated questions."""

        # Add retrieved context
        if retrieved_docs:
            system_prompt += "\n\n**Retrieved Legal Sources**:\n"
            for i, doc in enumerate(retrieved_docs[:5], 1):
                system_prompt += f"\n[Source {i}]: {doc[:400]}...\n"

        # Format conversation history
        history_str = self._format_detailed_context(conversation_history)

        user_prompt = f"""**Consultation History**:
{history_str}

**Current Question**: {current_query}

Please respond considering the full context of our consultation:"""

        return system_prompt, user_prompt

    def _format_detailed_context(self, history: List[Dict[str, str]]) -> str:
        """Format detailed conversation history"""
        formatted = []
        for i, msg in enumerate(history[-10:], 1):  # Last 10 messages
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            formatted.append(f"\n**Turn {i}** ({role}):\n{content}\n")

        return "\n".join(formatted)


# Global instance
advanced_prompt_engineer = AdvancedPromptEngineer()


def get_optimized_prompt(
    query: str,
    persona_id: str,
    query_type: Optional[LegalQueryType] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    retrieved_context: Optional[List[str]] = None
) -> Tuple[str, str]:
    """
    Main entry point for getting optimized prompts

    Args:
        query: User query
        persona_id: Active persona ID
        query_type: Optional query type for technique selection
        conversation_history: Optional conversation history
        retrieved_context: Optional RAG context

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    from core.lawyer_personas import get_persona

    persona = get_persona(persona_id)
    if not persona:
        persona_prompt = "You are an expert Indian legal AI assistant."
    else:
        persona_prompt = persona.system_prompt

    # Multi-turn conversation
    if conversation_history and len(conversation_history) > 0:
        return advanced_prompt_engineer.construct_multi_turn_prompt(
            current_query=query,
            conversation_history=conversation_history,
            persona_prompt=persona_prompt,
            retrieved_docs=retrieved_context
        )

    # Single turn with type-specific optimization
    if query_type:
        return advanced_prompt_engineer.construct_legal_reasoning_prompt(
            query=query,
            query_type=query_type,
            persona_prompt=persona_prompt,
            retrieved_context=retrieved_context
        )

    # Default: Chain-of-thought
    return advanced_prompt_engineer.construct_prompt(
        query=query,
        technique=PromptTechnique.CHAIN_OF_THOUGHT,
        persona_system_prompt=persona_prompt,
        retrieved_docs=retrieved_context
    )
