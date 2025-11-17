"""
Advanced Prompt Engineering System
Implements Chain-of-Thought, Constitutional AI, and Multi-Shot Learning
"""
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
import json


class PromptTechnique(str, Enum):
    """Advanced prompting techniques"""
    CHAIN_OF_THOUGHT = "chain_of_thought"
    CONSTITUTIONAL_AI = "constitutional_ai"
    MULTI_SHOT = "multi_shot"
    TREE_OF_THOUGHT = "tree_of_thought"
    SELF_CONSISTENCY = "self_consistency"
    LEGAL_REASONING = "legal_reasoning"


class Example(BaseModel):
    """Few-shot learning example"""
    query: str
    context: Optional[str] = None
    reasoning: Optional[str] = None
    answer: str
    citations: Optional[List[str]] = None


class ConstitutionalPrinciple(BaseModel):
    """Constitutional AI principle"""
    name: str
    critique_prompt: str
    revision_prompt: str
    weight: float = 1.0


class ChainOfThoughtStep(BaseModel):
    """Chain of thought reasoning step"""
    step_number: int
    description: str
    reasoning: str
    conclusion: str


class AdvancedPromptConfig(BaseModel):
    """Configuration for advanced prompt engineering"""
    technique: PromptTechnique
    enable_cot: bool = True
    enable_constitutional_ai: bool = True
    num_examples: int = 3
    temperature: float = 0.3
    max_reasoning_steps: int = 5


# Constitutional AI Principles for Legal Domain
LEGAL_CONSTITUTIONAL_PRINCIPLES: List[ConstitutionalPrinciple] = [
    ConstitutionalPrinciple(
        name="Legal Accuracy",
        critique_prompt="""Review the response for legal accuracy. Identify any statements that:
1. Misstate legal principles or precedents
2. Confuse different legal concepts
3. Make claims without proper legal authority
4. Cite cases or statutes incorrectly

Critique: Is the response legally accurate and well-grounded in law?""",
        revision_prompt="""Revise the response to ensure complete legal accuracy:
1. Correct any misstatements of law
2. Add proper citations for all legal claims
3. Clarify any ambiguous legal concepts
4. Ensure all case law and statutory references are accurate

Provide the revised response with improved legal accuracy.""",
        weight=2.0  # Highest priority
    ),

    ConstitutionalPrinciple(
        name="Source Attribution",
        critique_prompt="""Examine the response for proper source attribution. Check if:
1. All factual legal claims have citations
2. Case law is properly attributed with case names and citations
3. Statutory references include act names and section numbers
4. Any legal principle is traceable to a source

Critique: Does the response properly attribute all legal sources?""",
        revision_prompt="""Revise the response to include complete source attribution:
1. Add citations for every legal claim
2. Include full case names and citations for case law
3. Specify act names and section numbers for statutes
4. Ensure no legal statement is unsupported

Provide the revised response with complete citations.""",
        weight=1.8
    ),

    ConstitutionalPrinciple(
        name="No Hallucination",
        critique_prompt="""Critically examine the response for potential hallucinations. Look for:
1. Legal rules or principles not provided in the context
2. Case names or citations that may be invented
3. Statutory provisions not referenced in sources
4. Procedural rules stated without authority

Critique: Does the response contain any unsupported or fabricated information?""",
        revision_prompt="""Revise the response to eliminate all hallucinations:
1. Remove any legal claims not supported by the provided context
2. Verify all case names and citations against the sources
3. Only state statutory provisions explicitly mentioned in sources
4. Replace unsupported statements with "information not available in sources"

Provide the revised response with only verified, source-backed information.""",
        weight=2.0  # Highest priority
    ),

    ConstitutionalPrinciple(
        name="Jurisdictional Clarity",
        critique_prompt="""Review the response for jurisdictional clarity. Ensure:
1. The jurisdiction (Indian law) is clearly indicated
2. Any jurisdiction-specific rules are clearly marked
3. Differences between central and state law are noted
4. Court hierarchy is correctly represented

Critique: Is the jurisdictional context clear and accurate?""",
        revision_prompt="""Revise the response to clarify jurisdictional context:
1. Explicitly state when referring to Indian law
2. Distinguish between central and state law where relevant
3. Clarify which courts have jurisdiction
4. Note any jurisdictional limitations

Provide the revised response with clear jurisdictional context.""",
        weight=1.5
    ),

    ConstitutionalPrinciple(
        name="Completeness",
        critique_prompt="""Assess whether the response fully addresses the query. Check if:
1. All parts of the question are answered
2. Important legal nuances are addressed
3. Relevant exceptions or qualifications are mentioned
4. Practical implications are considered

Critique: Is the response complete and comprehensive?""",
        revision_prompt="""Revise the response to be more complete:
1. Address any unanswered parts of the query
2. Add important legal nuances and qualifications
3. Mention relevant exceptions or special cases
4. Include practical implications where appropriate

Provide a more comprehensive revised response.""",
        weight=1.3
    ),

    ConstitutionalPrinciple(
        name="Professional Tone",
        critique_prompt="""Evaluate the professional quality of the response. Consider:
1. Is the language appropriately formal for legal context?
2. Are technical legal terms used correctly?
3. Is the tone objective and balanced?
4. Does it maintain professional standards?

Critique: Does the response maintain appropriate professional tone?""",
        revision_prompt="""Revise the response to improve professional tone:
1. Use appropriate legal terminology
2. Maintain formal, objective language
3. Avoid colloquialisms or casual phrasing
4. Ensure the tone is balanced and professional

Provide the revised response with improved professional tone.""",
        weight=1.2
    ),

    ConstitutionalPrinciple(
        name="Ethical Considerations",
        critique_prompt="""Review the response for ethical legal considerations. Check:
1. Does it avoid providing advice that could be misused?
2. Are ethical limitations properly noted?
3. Are potential conflicts of interest mentioned?
4. Is there appropriate disclaimer language?

Critique: Are ethical considerations properly addressed?""",
        revision_prompt="""Revise the response to address ethical considerations:
1. Add appropriate disclaimers where needed
2. Note potential ethical limitations
3. Warn about potential misuse
4. Include standard legal advisory language

Provide the ethically improved revised response.""",
        weight=1.4
    ),
]


# Multi-Shot Learning Examples for Different Legal Domains
LEGAL_FEW_SHOT_EXAMPLES: Dict[str, List[Example]] = {
    "litigation": [
        Example(
            query="What is the limitation period for filing a civil suit for recovery of money under a contract?",
            context="Limitation Act, 1963, Article 113: Three years from the date when the contract is broken.",
            reasoning="""Step 1: Identify the type of suit - This is a civil suit for recovery of money under a contract.
Step 2: Find applicable article - Article 113 of the Limitation Act, 1963 applies to suits for money payable under contract.
Step 3: Determine limitation period - The period is three years.
Step 4: Identify starting point - Limitation starts from the date when the contract is broken.""",
            answer="""Under the Limitation Act, 1963, the limitation period for filing a civil suit for recovery of money under a contract is **three years**.

**Legal Basis:** Article 113 of the Limitation Act, 1963

**Starting Point:** The limitation period begins from the date when the contract is broken or breached.

**Citation:** Limitation Act, 1963, Article 113""",
            citations=["Limitation Act, 1963, Article 113"]
        ),
        Example(
            query="Can a court grant an ex-parte injunction without hearing the defendant?",
            context="Code of Civil Procedure, Order XXXIX, Rule 3: Where in any suit it is proved by affidavit that the defendant threatens to dispose of his property with a view to defrauding creditors, the Court may grant temporary injunction.",
            reasoning="""Step 1: Understand the concept - Ex-parte injunction means injunction granted without hearing the other party.
Step 2: Find legal provision - Order XXXIX of CPC deals with temporary injunctions.
Step 3: Check requirements - Court can grant ex-parte injunction in urgent cases.
Step 4: Note safeguards - Affidavit evidence required, notice to be given soon after.""",
            answer="""Yes, a court can grant an ex-parte injunction without hearing the defendant in certain urgent circumstances.

**Legal Provision:** Order XXXIX, Rules 1, 2, and 3 of the Code of Civil Procedure, 1908

**Conditions:**
1. There must be an urgent need requiring immediate action
2. Applicant must file an affidavit stating facts
3. Prima facie case must be established
4. Balance of convenience must favor the applicant
5. Irreparable injury may occur if injunction not granted

**Safeguards:** The defendant must be given notice at the earliest, and the court will hear them before confirming the injunction.

**Citation:** Code of Civil Procedure, 1908, Order XXXIX""",
            citations=["Code of Civil Procedure, 1908, Order XXXIX"]
        ),
        Example(
            query="What is the consequence of non-appearance of plaintiff on the date of hearing?",
            context="Order IX, Rule 8 CPC: Where the plaintiff fails to appear when the suit is called for hearing, the Court may dismiss the suit or proceed ex-parte against the defendant.",
            reasoning="""Step 1: Identify the situation - Plaintiff not appearing on hearing date.
Step 2: Find applicable provision - Order IX, Rule 8 of CPC applies.
Step 3: Determine court's options - Court has discretion to either dismiss suit or proceed ex-parte.
Step 4: Note practical consequence - Usually courts dismiss for default of appearance.""",
            answer="""If the plaintiff does not appear on the date of hearing, the court has two options under Order IX, Rule 8 of the Code of Civil Procedure:

**Option 1: Dismiss the suit** - The court may dismiss the suit for default of appearance.

**Option 2: Proceed ex-parte against defendant** - The court may decide to proceed with the case in plaintiff's absence and decide the suit ex-parte against the defendant (though this is less common).

**Remedy for Plaintiff:** If the suit is dismissed, the plaintiff can file an application under Order IX, Rule 9 CPC to restore the suit by showing sufficient cause for non-appearance.

**Citation:** Code of Civil Procedure, 1908, Order IX, Rules 8 and 9""",
            citations=["Code of Civil Procedure, 1908, Order IX, Rule 8", "Code of Civil Procedure, 1908, Order IX, Rule 9"]
        ),
    ],

    "corporate": [
        Example(
            query="What is the minimum number of directors required for a private company?",
            context="Companies Act, 2013, Section 149(1): Every company shall have a minimum of two directors in case of a private company and three directors in case of a public company.",
            reasoning="""Step 1: Identify company type - Question asks about private company.
Step 2: Find applicable provision - Section 149(1) of Companies Act, 2013.
Step 3: Extract requirement - Minimum two directors for private company.
Step 4: Note distinction - Public companies require minimum three directors.""",
            answer="""A private company must have a **minimum of two directors**.

**Legal Provision:** Section 149(1) of the Companies Act, 2013

**Key Points:**
- Private company: Minimum 2 directors
- Public company: Minimum 3 directors
- Maximum: 15 directors (can be increased by special resolution)

**One Person Company:** An exception exists for One Person Companies (OPC) which can have just one director.

**Citation:** Companies Act, 2013, Section 149(1)""",
            citations=["Companies Act, 2013, Section 149(1)"]
        ),
    ],

    "criminal": [
        Example(
            query="Is bail a right or discretion of the court in non-bailable offenses?",
            context="Bharatiya Nagarik Suraksha Sanhita, Section 479: In non-bailable cases, bail is a matter of judicial discretion, but the court must consider factors like nature of accusation, severity of punishment, character of evidence, and likelihood of accused fleeing justice.",
            reasoning="""Step 1: Classify offense type - Question asks about non-bailable offenses.
Step 2: Understand bail nature - Bail in non-bailable cases is discretionary, not a right.
Step 3: Identify guiding factors - Court considers nature of offense, evidence, flight risk.
Step 4: Note constitutional protection - Right to life under Article 21 guides bail jurisprudence.""",
            answer="""In non-bailable offenses, bail is **not a right but a matter of judicial discretion**.

**Legal Framework:** Section 479 of the Bharatiya Nagarik Suraksha Sanhita, 2023 (erstwhile Section 437 CrPC)

**Factors Court Considers:**
1. Nature and gravity of accusation
2. Severity of punishment upon conviction
3. Character of evidence
4. Reasonable apprehension of tampering with evidence/witnesses
5. Likelihood of accused fleeing from justice
6. Criminal antecedents

**Important Principle:** While discretionary, the Supreme Court has held that bail should be the rule and jail the exception, considering the constitutional right to liberty under Article 21.

**Citation:** Bharatiya Nagarik Suraksha Sanhita, 2023, Section 479; Constitution of India, Article 21""",
            citations=["Bharatiya Nagarik Suraksha Sanhita, 2023, Section 479", "Constitution of India, Article 21"]
        ),
    ],
}


class AdvancedPromptEngineer:
    """Advanced prompt engineering with CoT, Constitutional AI, and Multi-Shot"""

    def __init__(self, config: Optional[AdvancedPromptConfig] = None):
        self.config = config or AdvancedPromptConfig(
            technique=PromptTechnique.CHAIN_OF_THOUGHT,
            enable_cot=True,
            enable_constitutional_ai=True,
            num_examples=3
        )
        self.principles = LEGAL_CONSTITUTIONAL_PRINCIPLES
        self.examples = LEGAL_FEW_SHOT_EXAMPLES

    def build_chain_of_thought_prompt(
        self,
        query: str,
        context: str,
        persona_instructions: Optional[str] = None
    ) -> str:
        """Build Chain-of-Thought reasoning prompt"""

        cot_instruction = """
Before providing your answer, think through the problem step-by-step:

**Reasoning Steps:**
1. **Understand the Question:** What exactly is being asked?
2. **Identify Relevant Law:** Which laws, sections, or cases apply?
3. **Analyze the Context:** What do the provided sources tell us?
4. **Apply Legal Principles:** How does the law apply to this situation?
5. **Draw Conclusion:** What is the answer based on this analysis?

Think carefully through each step, then provide your answer.
"""

        prompt = f"""You are an expert Indian legal AI assistant. {persona_instructions or ''}

{cot_instruction}

**Context/Legal Sources:**
{context}

**Question:**
{query}

**Your Response:**
[Show your step-by-step reasoning, then provide a clear answer with proper citations]
"""
        return prompt

    def build_multi_shot_prompt(
        self,
        query: str,
        context: str,
        domain: str = "litigation",
        persona_instructions: Optional[str] = None
    ) -> str:
        """Build multi-shot learning prompt with examples"""

        # Get relevant examples for the domain
        examples = self.examples.get(domain, self.examples.get("litigation", []))
        examples = examples[:self.config.num_examples]

        # Build examples section
        examples_text = "**Examples of Proper Legal Reasoning:**\n\n"
        for i, example in enumerate(examples, 1):
            examples_text += f"""
**Example {i}:**
Question: {example.query}

Context: {example.context}

Reasoning:
{example.reasoning}

Answer: {example.answer}

---
"""

        prompt = f"""You are an expert Indian legal AI assistant. {persona_instructions or ''}

{examples_text}

Now, apply the same careful reasoning to this question:

**Context/Legal Sources:**
{context}

**Question:**
{query}

**Your Response:**
[Follow the same pattern: show reasoning steps, then provide a clear answer with citations]
"""
        return prompt

    def build_constitutional_critique_prompt(
        self,
        original_response: str,
        principles: Optional[List[ConstitutionalPrinciple]] = None
    ) -> List[Dict[str, str]]:
        """Build constitutional AI critique prompts"""

        principles = principles or self.principles
        critique_prompts = []

        for principle in principles:
            critique_prompts.append({
                "principle": principle.name,
                "prompt": f"""**Original Response:**
{original_response}

**Critique Task:**
{principle.critique_prompt}

Provide your critique:""",
                "revision_prompt": principle.revision_prompt,
                "weight": principle.weight
            })

        return critique_prompts

    def build_tree_of_thought_prompt(
        self,
        query: str,
        context: str,
        num_paths: int = 3
    ) -> str:
        """Build Tree-of-Thought reasoning prompt"""

        prompt = f"""You are an expert Indian legal AI assistant using Tree-of-Thought reasoning.

**Context/Legal Sources:**
{context}

**Question:**
{query}

**Tree-of-Thought Analysis:**

Generate {num_paths} different reasoning paths to answer this question:

**Path 1: [Primary Legal Framework]**
1. Identify the primary legal framework applicable
2. Analyze how it directly addresses the question
3. Consider the straightforward application
4. Conclusion from this path

**Path 2: [Alternative Interpretation]**
1. Consider alternative legal interpretations
2. Examine if there are different applicable provisions
3. Analyze any exceptions or special cases
4. Conclusion from this path

**Path 3: [Practical Considerations]**
1. Consider practical implications and case law
2. Examine how courts have applied these principles
3. Consider any procedural aspects
4. Conclusion from this path

**Synthesis:**
Evaluate all paths, identify the strongest reasoning, and provide the best answer with proper citations.
"""
        return prompt

    def build_self_consistency_prompt(
        self,
        query: str,
        context: str,
        num_samples: int = 5
    ) -> str:
        """Build self-consistency prompt (generates multiple answers)"""

        prompt = f"""You are an expert Indian legal AI assistant.

**Context/Legal Sources:**
{context}

**Question:**
{query}

Generate {num_samples} independent answers to this question, each using different reasoning approaches:

**Answer 1 (Statute-Based):**
[Focus on statutory provisions and their direct application]

**Answer 2 (Precedent-Based):**
[Focus on case law and how courts have interpreted this]

**Answer 3 (Principle-Based):**
[Focus on underlying legal principles]

**Answer 4 (Procedural):**
[Focus on procedural aspects and practical application]

**Answer 5 (Comprehensive):**
[Integrate all aspects for a complete answer]

**Final Answer:**
[Synthesize the most consistent and accurate elements from all approaches]
"""
        return prompt

    def apply_constitutional_ai(
        self,
        original_response: str,
        critique_responses: List[Dict[str, Any]]
    ) -> str:
        """Apply constitutional AI revision based on critiques"""

        # This would integrate with LLM to generate revised response
        # For now, return structure for revision
        revision_prompt = f"""**Original Response:**
{original_response}

**Critiques Received:**
"""
        for critique in critique_responses:
            revision_prompt += f"\n**{critique['principle']}:**\n{critique['critique']}\n"

        revision_prompt += """
**Revision Task:**
Based on the above critiques, provide a revised response that:
1. Maintains legal accuracy
2. Includes proper source attribution
3. Eliminates any hallucinations
4. Clarifies jurisdictional context
5. Ensures completeness
6. Uses professional tone
7. Addresses ethical considerations

**Revised Response:**
"""
        return revision_prompt

    def select_best_technique(
        self,
        query: str,
        query_complexity: str = "medium"
    ) -> PromptTechnique:
        """Automatically select best prompting technique based on query"""

        query_lower = query.lower()

        # Complex analytical queries -> Tree of Thought
        if any(word in query_lower for word in ["compare", "contrast", "analyze", "evaluate", "assess"]):
            return PromptTechnique.TREE_OF_THOUGHT

        # Queries requiring high confidence -> Self Consistency
        if any(word in query_lower for word in ["criminal", "constitutional", "fundamental right"]):
            return PromptTechnique.SELF_CONSISTENCY

        # Standard legal queries -> Chain of Thought
        if query_complexity in ["low", "medium"]:
            return PromptTechnique.CHAIN_OF_THOUGHT

        # Complex queries -> Multi-shot
        return PromptTechnique.MULTI_SHOT


# Global instance
advanced_prompt_engineer = AdvancedPromptEngineer()
