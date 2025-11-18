"""
Automated Legal Brief Generator with Jurisdiction-Specific Templates
Generates professional legal briefs, pleadings, and motions
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog
from services.azure_openai_service import azure_openai_service

logger = structlog.get_logger(__name__)


@dataclass
class BriefTemplate:
    """Legal brief template"""
    template_id: str
    name: str
    jurisdiction: str
    document_type: str  # brief, pleading, motion, petition, appeal
    sections: List[Dict[str, Any]]
    format_requirements: Dict[str, Any]


@dataclass
class GeneratedBrief:
    """Generated legal brief"""
    title: str
    document_type: str
    jurisdiction: str
    sections: List[Dict[str, str]]
    full_text: str
    word_count: int
    citations: List[str]
    metadata: Dict[str, Any]


class LegalBriefGenerator:
    """
    Generates legal briefs using templates and AI

    Supports:
    - Multiple jurisdictions (India, US, UK, etc.)
    - Various document types (briefs, motions, pleadings)
    - Automatic citation formatting
    - Jurisdiction-specific requirements
    """

    def __init__(self):
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, BriefTemplate]:
        """Load jurisdiction-specific templates"""

        templates = {}

        # Indian Supreme Court Brief Template
        templates["india_sc_brief"] = BriefTemplate(
            template_id="india_sc_brief",
            name="Supreme Court of India Brief",
            jurisdiction="India - Supreme Court",
            document_type="brief",
            sections=[
                {"title": "Cover Page", "required": True, "order": 1},
                {"title": "Table of Contents", "required": True, "order": 2},
                {"title": "Index of Authorities", "required": True, "order": 3},
                {"title": "Statement of Jurisdiction", "required": True, "order": 4},
                {"title": "Statement of Facts", "required": True, "order": 5},
                {"title": "Statement of Issues", "required": True, "order": 6},
                {"title": "Summary of Arguments", "required": True, "order": 7},
                {"title": "Arguments Advanced", "required": True, "order": 8},
                {"title": "Prayer/Relief Sought", "required": True, "order": 9},
                {"title": "List of Documents", "required": False, "order": 10}
            ],
            format_requirements={
                "page_size": "A4",
                "margins": "1 inch all sides",
                "font": "Times New Roman 12pt",
                "line_spacing": "Double",
                "citation_style": "Indian Bluebook"
            }
        )

        # High Court Writ Petition Template
        templates["india_hc_writ"] = BriefTemplate(
            template_id="india_hc_writ",
            name="High Court Writ Petition",
            jurisdiction="India - High Court",
            document_type="petition",
            sections=[
                {"title": "Title", "required": True, "order": 1},
                {"title": "Details of Petitioner", "required": True, "order": 2},
                {"title": "Details of Respondent", "required": True, "order": 3},
                {"title": "Grounds for Writ", "required": True, "order": 4},
                {"title": "Facts of the Case", "required": True, "order": 5},
                {"title": "Legal Provisions", "required": True, "order": 6},
                {"title": "Arguments", "required": True, "order": 7},
                {"title": "Prayer", "required": True, "order": 8},
                {"title": "Affidavit", "required": True, "order": 9},
                {"title": "Annexures", "required": False, "order": 10}
            ],
            format_requirements={
                "page_size": "Legal",
                "margins": "1.5 inch left, 1 inch others",
                "font": "Arial 12pt",
                "line_spacing": "1.5",
                "citation_style": "Indian"
            }
        )

        # Civil Suit Plaint Template
        templates["india_civil_plaint"] = BriefTemplate(
            template_id="india_civil_plaint",
            name="Civil Suit Plaint",
            jurisdiction="India - Civil Court",
            document_type="pleading",
            sections=[
                {"title": "Title of the Suit", "required": True, "order": 1},
                {"title": "Parties to the Suit", "required": True, "order": 2},
                {"title": "Valuation and Jurisdiction", "required": True, "order": 3},
                {"title": "Facts of the Case", "required": True, "order": 4},
                {"title": "Cause of Action", "required": True, "order": 5},
                {"title": "Relief Claimed", "required": True, "order": 6},
                {"title": "Verification", "required": True, "order": 7},
                {"title": "List of Documents", "required": True, "order": 8}
            ],
            format_requirements={
                "page_size": "A4",
                "margins": "1 inch all sides",
                "font": "Times New Roman 12pt",
                "line_spacing": "Double",
                "citation_style": "Indian"
            }
        )

        # Criminal Bail Application Template
        templates["india_bail_application"] = BriefTemplate(
            template_id="india_bail_application",
            name="Bail Application",
            jurisdiction="India - Criminal Court",
            document_type="motion",
            sections=[
                {"title": "Title", "required": True, "order": 1},
                {"title": "Accused Details", "required": True, "order": 2},
                {"title": "Case Details", "required": True, "order": 3},
                {"title": "Grounds for Bail", "required": True, "order": 4},
                {"title": "Legal Provisions", "required": True, "order": 5},
                {"title": "Facts and Circumstances", "required": True, "order": 6},
                {"title": "Prayer", "required": True, "order": 7},
                {"title": "Affidavit", "required": True, "order": 8}
            ],
            format_requirements={
                "page_size": "Legal",
                "margins": "1 inch all sides",
                "font": "Arial 12pt",
                "line_spacing": "1.5",
                "citation_style": "Indian"
            }
        )

        return templates

    async def generate_brief(
        self,
        template_id: str,
        case_details: Dict[str, Any],
        custom_content: Optional[Dict[str, str]] = None,
        style: str = "formal"  # formal, persuasive, analytical
    ) -> GeneratedBrief:
        """
        Generate a legal brief from template

        Args:
            template_id: ID of template to use
            case_details: Details of the case
            custom_content: Optional custom content for sections
            style: Writing style

        Returns:
            Generated brief with all sections
        """
        logger.info(f"Generating brief using template: {template_id}")

        template = self.templates.get(template_id)
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Generate each section
        sections = []
        all_citations = []

        for section_config in sorted(template.sections, key=lambda x: x["order"]):
            section_title = section_config["title"]

            # Use custom content if provided
            if custom_content and section_title in custom_content:
                section_content = custom_content[section_title]
            else:
                # Generate section using AI
                section_content = await self._generate_section(
                    template=template,
                    section_title=section_title,
                    case_details=case_details,
                    style=style
                )

            sections.append({
                "title": section_title,
                "content": section_content
            })

            # Extract citations from content
            citations = self._extract_citations(section_content)
            all_citations.extend(citations)

        # Assemble full document
        full_text = self._assemble_document(
            template=template,
            sections=sections,
            case_details=case_details
        )

        word_count = len(full_text.split())

        logger.info(f"Brief generated: {word_count} words, {len(sections)} sections")

        return GeneratedBrief(
            title=case_details.get("title", "Legal Brief"),
            document_type=template.document_type,
            jurisdiction=template.jurisdiction,
            sections=sections,
            full_text=full_text,
            word_count=word_count,
            citations=list(set(all_citations)),
            metadata={
                "template_id": template_id,
                "generated_at": datetime.utcnow().isoformat(),
                "style": style
            }
        )

    async def _generate_section(
        self,
        template: BriefTemplate,
        section_title: str,
        case_details: Dict[str, Any],
        style: str
    ) -> str:
        """Generate content for a specific section using AI"""

        # Build prompt based on section and style
        prompt = self._build_section_prompt(
            template,
            section_title,
            case_details,
            style
        )

        try:
            # Generate content using AI
            content = await azure_openai_service.generate_completion(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3  # Lower temperature for legal documents
            )

            return content

        except Exception as e:
            logger.error(f"Section generation failed: {str(e)}")
            return f"[{section_title} - To be completed]"

    def _build_section_prompt(
        self,
        template: BriefTemplate,
        section_title: str,
        case_details: Dict[str, Any],
        style: str
    ) -> str:
        """Build prompt for section generation"""

        base_prompt = f"""You are an expert legal brief writer for {template.jurisdiction}.

Generate the "{section_title}" section for a {template.document_type}.

Case Details:
- Title: {case_details.get('title', 'N/A')}
- Case Number: {case_details.get('case_number', 'N/A')}
- Court: {case_details.get('court', 'N/A')}
- Parties: {case_details.get('parties', 'N/A')}
- Facts Summary: {case_details.get('facts_summary', 'N/A')}
- Legal Issues: {case_details.get('legal_issues', 'N/A')}

Style: {style}

Requirements:
- Follow {template.jurisdiction} format and citation style
- Use professional legal language
- Include relevant legal provisions and citations where applicable
- Keep paragraphs concise and well-structured

Generate the {section_title} section:"""

        return base_prompt

    def _extract_citations(self, text: str) -> List[str]:
        """Extract legal citations from text"""

        import re

        citations = []

        # Indian citation patterns
        patterns = [
            r'\b\d{4}\s+\w+\s+\d+\b',  # 2023 SCC 123
            r'\bAIR\s+\d{4}\s+\w+\s+\d+\b',  # AIR 2023 SC 123
            r'\(\d{4}\)\s+\d+\s+\w+\s+\d+\b',  # (2023) 1 SCC 123
            r'\[\d{4}\]\s+\w+\s+\d+\b',  # [2023] SCC 123
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            citations.extend(matches)

        return citations

    def _assemble_document(
        self,
        template: BriefTemplate,
        sections: List[Dict[str, str]],
        case_details: Dict[str, Any]
    ) -> str:
        """Assemble final document from sections"""

        doc_parts = []

        # Header
        doc_parts.append(f"{'=' * 80}")
        doc_parts.append(f"{template.name}")
        doc_parts.append(f"{template.jurisdiction}")
        doc_parts.append(f"{'=' * 80}\n")

        # Case title
        doc_parts.append(f"IN THE MATTER OF:")
        doc_parts.append(f"{case_details.get('title', 'N/A')}\n")

        # Case number
        if case_details.get('case_number'):
            doc_parts.append(f"Case No.: {case_details['case_number']}\n")

        # Sections
        for section in sections:
            doc_parts.append(f"\n{'-' * 80}")
            doc_parts.append(f"{section['title'].upper()}")
            doc_parts.append(f"{'-' * 80}\n")
            doc_parts.append(section['content'])
            doc_parts.append("")

        # Footer
        doc_parts.append(f"\n{'=' * 80}")
        doc_parts.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        doc_parts.append(f"{'=' * 80}")

        return "\n".join(doc_parts)

    def list_templates(
        self,
        jurisdiction: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available templates"""

        templates = []

        for template_id, template in self.templates.items():
            # Filter by jurisdiction
            if jurisdiction and jurisdiction.lower() not in template.jurisdiction.lower():
                continue

            # Filter by document type
            if document_type and template.document_type != document_type:
                continue

            templates.append({
                "template_id": template.template_id,
                "name": template.name,
                "jurisdiction": template.jurisdiction,
                "document_type": template.document_type,
                "sections_count": len(template.sections)
            })

        return templates


# Global instance
legal_brief_generator = LegalBriefGenerator()
