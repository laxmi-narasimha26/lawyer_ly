"""
Multi-Document Analysis and Cross-Reference System
Analyzes multiple legal documents simultaneously and finds cross-references
"""
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime
import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
import re

from database.models import Document, DocumentChunk
from services.azure_openai_service import azure_openai_service

logger = structlog.get_logger(__name__)


@dataclass
class CrossReference:
    """Cross-reference between documents"""
    source_doc_id: str
    target_doc_id: str
    source_section: str
    target_section: str
    reference_type: str  # citation, quote, related_topic, contradiction
    confidence: float
    explanation: str


@dataclass
class DocumentComparison:
    """Comparison result between two documents"""
    doc1_id: str
    doc2_id: str
    similarity_score: float
    common_topics: List[str]
    contradictions: List[Dict[str, Any]]
    citations_between: List[CrossReference]
    summary: str


@dataclass
class MultiDocAnalysisResult:
    """Result of multi-document analysis"""
    documents: List[str]
    cross_references: List[CrossReference]
    comparisons: List[DocumentComparison]
    common_themes: List[str]
    timeline: List[Dict[str, Any]]
    summary: str
    recommendations: List[str]


class MultiDocumentAnalyzer:
    """
    Analyzes multiple documents simultaneously to find:
    - Cross-references and citations
    - Common themes and topics
    - Contradictions and inconsistencies
    - Timeline of events
    - Document relationships
    """

    def __init__(self):
        self.citation_pattern = re.compile(
            r'\b(?:'
            r'\d{4}\s+\w+\s+\d+|'  # 2023 SCC 123
            r'\[\d{4}\]\s+\w+\s+\d+|'  # [2023] SCC 123
            r'AIR\s+\d{4}\s+\w+\s+\d+|'  # AIR 2023 SC 123
            r'\(\d{4}\)\s+\d+\s+\w+\s+\d+'  # (2023) 1 SCC 123
            r')\b'
        )

        self.section_pattern = re.compile(
            r'\b(?:'
            r'Section\s+\d+[A-Z]?|'
            r'Article\s+\d+[A-Z]?|'
            r'Clause\s+\d+[A-Z]?|'
            r'Para(?:graph)?\s+\d+|'
            r'Rule\s+\d+'
            r')\b',
            re.IGNORECASE
        )

    async def analyze_multiple_documents(
        self,
        document_ids: List[str],
        session: AsyncSession,
        analysis_depth: str = "standard"  # quick, standard, deep
    ) -> MultiDocAnalysisResult:
        """
        Analyze multiple documents together

        Args:
            document_ids: List of document IDs to analyze
            session: Database session
            analysis_depth: Level of analysis (quick, standard, deep)

        Returns:
            Comprehensive multi-document analysis result
        """
        start_time = datetime.utcnow()

        logger.info(f"Starting multi-document analysis for {len(document_ids)} documents")

        # Load documents
        documents = await self._load_documents(document_ids, session)

        if len(documents) < 2:
            raise ValueError("At least 2 documents required for multi-document analysis")

        # Perform analysis tasks in parallel
        tasks = [
            self._find_cross_references(documents, session),
            self._compare_documents(documents, session),
            self._extract_common_themes(documents),
            self._build_timeline(documents, session)
        ]

        if analysis_depth == "deep":
            tasks.append(self._deep_semantic_analysis(documents))

        results = await asyncio.gather(*tasks)

        cross_references = results[0]
        comparisons = results[1]
        common_themes = results[2]
        timeline = results[3]

        # Generate overall summary
        summary = await self._generate_summary(
            documents=documents,
            cross_references=cross_references,
            comparisons=comparisons,
            common_themes=common_themes
        )

        # Generate recommendations
        recommendations = await self._generate_recommendations(
            documents=documents,
            comparisons=comparisons,
            cross_references=cross_references
        )

        analysis_time = (datetime.utcnow() - start_time).total_seconds()

        logger.info(f"Multi-document analysis completed in {analysis_time:.2f}s")

        return MultiDocAnalysisResult(
            documents=[doc["id"] for doc in documents],
            cross_references=cross_references,
            comparisons=comparisons,
            common_themes=common_themes,
            timeline=timeline,
            summary=summary,
            recommendations=recommendations
        )

    async def _load_documents(
        self,
        document_ids: List[str],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Load document metadata and chunks"""

        documents = []

        for doc_id in document_ids:
            # Load document metadata
            result = await session.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()

            if not doc:
                logger.warning(f"Document {doc_id} not found")
                continue

            # Load chunks
            chunks_result = await session.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc_id)
                .order_by(DocumentChunk.chunk_index)
            )
            chunks = chunks_result.scalars().all()

            documents.append({
                "id": str(doc.id),
                "filename": doc.filename,
                "document_type": doc.document_type,
                "uploaded_at": doc.uploaded_at,
                "metadata": doc.metadata or {},
                "chunks": [
                    {
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        "metadata": chunk.metadata or {}
                    }
                    for chunk in chunks
                ]
            })

        return documents

    async def _find_cross_references(
        self,
        documents: List[Dict[str, Any]],
        session: AsyncSession
    ) -> List[CrossReference]:
        """Find cross-references between documents"""

        cross_refs = []

        # Check each document against others
        for i, doc1 in enumerate(documents):
            for doc2 in documents[i + 1:]:
                refs = await self._find_refs_between_documents(doc1, doc2)
                cross_refs.extend(refs)

        logger.info(f"Found {len(cross_refs)} cross-references")

        return cross_refs

    async def _find_refs_between_documents(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any]
    ) -> List[CrossReference]:
        """Find references between two specific documents"""

        refs = []

        # Extract all citations from doc1
        doc1_citations = set()
        for chunk in doc1["chunks"]:
            citations = self.citation_pattern.findall(chunk["content"])
            doc1_citations.update(citations)

        # Extract all citations from doc2
        doc2_citations = set()
        for chunk in doc2["chunks"]:
            citations = self.citation_pattern.findall(chunk["content"])
            doc2_citations.update(citations)

        # Find common citations
        common_citations = doc1_citations & doc2_citations

        for citation in common_citations:
            refs.append(CrossReference(
                source_doc_id=doc1["id"],
                target_doc_id=doc2["id"],
                source_section=citation,
                target_section=citation,
                reference_type="citation",
                confidence=0.9,
                explanation=f"Both documents cite {citation}"
            ))

        # Find section references
        for chunk1 in doc1["chunks"]:
            sections = self.section_pattern.findall(chunk1["content"])
            for section in sections:
                # Check if this section appears in doc2
                for chunk2 in doc2["chunks"]:
                    if section.lower() in chunk2["content"].lower():
                        refs.append(CrossReference(
                            source_doc_id=doc1["id"],
                            target_doc_id=doc2["id"],
                            source_section=section,
                            target_section=section,
                            reference_type="related_topic",
                            confidence=0.7,
                            explanation=f"Both documents reference {section}"
                        ))
                        break

        return refs

    async def _compare_documents(
        self,
        documents: List[Dict[str, Any]],
        session: AsyncSession
    ) -> List[DocumentComparison]:
        """Compare documents pairwise"""

        comparisons = []

        for i, doc1 in enumerate(documents):
            for doc2 in documents[i + 1:]:
                comparison = await self._compare_two_documents(doc1, doc2)
                comparisons.append(comparison)

        logger.info(f"Generated {len(comparisons)} document comparisons")

        return comparisons

    async def _compare_two_documents(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any]
    ) -> DocumentComparison:
        """Compare two documents in detail"""

        # Extract key terms from both documents
        doc1_text = " ".join([chunk["content"] for chunk in doc1["chunks"]])
        doc2_text = " ".join([chunk["content"] for chunk in doc2["chunks"]])

        # Calculate similarity (simple word overlap for now)
        doc1_words = set(doc1_text.lower().split())
        doc2_words = set(doc2_text.lower().split())

        overlap = len(doc1_words & doc2_words)
        total = len(doc1_words | doc2_words)

        similarity_score = overlap / total if total > 0 else 0.0

        # Extract common topics (most frequent overlapping words)
        common_words = doc1_words & doc2_words
        # Filter out common words
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'but'}
        common_topics = [word for word in common_words if word not in stopwords and len(word) > 3][:10]

        # Generate summary using AI
        summary = await self._generate_comparison_summary(doc1, doc2, similarity_score, common_topics)

        return DocumentComparison(
            doc1_id=doc1["id"],
            doc2_id=doc2["id"],
            similarity_score=similarity_score,
            common_topics=common_topics,
            contradictions=[],  # Would require deeper semantic analysis
            citations_between=[],
            summary=summary
        )

    async def _generate_comparison_summary(
        self,
        doc1: Dict[str, Any],
        doc2: Dict[str, Any],
        similarity: float,
        common_topics: List[str]
    ) -> str:
        """Generate AI summary of document comparison"""

        prompt = f"""Compare these two legal documents:

Document 1: {doc1['filename']}
Document 2: {doc2['filename']}

Similarity Score: {similarity:.2%}
Common Topics: {', '.join(common_topics[:5])}

Provide a brief 2-3 sentence comparison highlighting key similarities and differences."""

        try:
            summary = await azure_openai_service.generate_completion(
                prompt=prompt,
                max_tokens=150,
                temperature=0.3
            )
            return summary
        except Exception as e:
            logger.error(f"Failed to generate comparison summary: {str(e)}")
            return f"Similarity: {similarity:.2%}. Common topics: {', '.join(common_topics[:3])}"

    async def _extract_common_themes(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract common themes across all documents"""

        # Collect all text
        all_text = []
        for doc in documents:
            for chunk in doc["chunks"]:
                all_text.append(chunk["content"])

        combined_text = " ".join(all_text)

        # Extract themes using AI
        prompt = f"""Analyze this collection of legal documents and extract the 5-10 main themes or topics:

{combined_text[:4000]}...

List the main themes as a comma-separated list."""

        try:
            themes_text = await azure_openai_service.generate_completion(
                prompt=prompt,
                max_tokens=100,
                temperature=0.3
            )

            themes = [theme.strip() for theme in themes_text.split(',')]
            return themes[:10]

        except Exception as e:
            logger.error(f"Failed to extract themes: {str(e)}")
            return []

    async def _build_timeline(
        self,
        documents: List[Dict[str, Any]],
        session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Build timeline of events from documents"""

        timeline_events = []

        # Extract dates from documents
        date_pattern = re.compile(
            r'\b(?:'
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|'  # DD/MM/YYYY or DD-MM-YYYY
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}|'  # YYYY-MM-DD
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}'  # DD Month YYYY
            r')\b'
        )

        for doc in documents:
            for chunk in doc["chunks"]:
                dates = date_pattern.findall(chunk["content"])
                for date in dates:
                    # Extract context around date
                    date_pos = chunk["content"].find(date)
                    context_start = max(0, date_pos - 100)
                    context_end = min(len(chunk["content"]), date_pos + 100)
                    context = chunk["content"][context_start:context_end]

                    timeline_events.append({
                        "date": date,
                        "document": doc["filename"],
                        "context": context,
                        "doc_id": doc["id"]
                    })

        # Sort by date (rough sorting by string)
        timeline_events.sort(key=lambda x: x["date"])

        logger.info(f"Built timeline with {len(timeline_events)} events")

        return timeline_events[:50]  # Limit to 50 events

    async def _deep_semantic_analysis(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Perform deep semantic analysis (for deep mode)"""

        logger.info("Performing deep semantic analysis")

        # This would involve more sophisticated NLP techniques
        # For now, placeholder
        return {
            "semantic_clusters": [],
            "argument_chains": [],
            "legal_reasoning_patterns": []
        }

    async def _generate_summary(
        self,
        documents: List[Dict[str, Any]],
        cross_references: List[CrossReference],
        comparisons: List[DocumentComparison],
        common_themes: List[str]
    ) -> str:
        """Generate overall summary of multi-document analysis"""

        doc_names = [doc["filename"] for doc in documents]

        prompt = f"""Provide a comprehensive summary of analysis across these legal documents:

Documents ({len(documents)}):
{', '.join(doc_names)}

Found {len(cross_references)} cross-references between documents
Common themes: {', '.join(common_themes[:5])}

Generate a 3-4 sentence summary of key findings."""

        try:
            summary = await azure_openai_service.generate_completion(
                prompt=prompt,
                max_tokens=200,
                temperature=0.3
            )
            return summary
        except Exception as e:
            logger.error(f"Failed to generate summary: {str(e)}")
            return f"Analyzed {len(documents)} documents with {len(cross_references)} cross-references found."

    async def _generate_recommendations(
        self,
        documents: List[Dict[str, Any]],
        comparisons: List[DocumentComparison],
        cross_references: List[CrossReference]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis"""

        recommendations = []

        # Check for high similarity between documents
        for comp in comparisons:
            if comp.similarity_score > 0.7:
                recommendations.append(
                    f"Documents {comp.doc1_id[:8]} and {comp.doc2_id[:8]} have high similarity "
                    f"({comp.similarity_score:.1%}) - consider consolidating"
                )

        # Check for missing cross-references
        if len(cross_references) < len(documents):
            recommendations.append(
                "Limited cross-referencing found between documents - consider adding explicit citations"
            )

        # Add general recommendations
        recommendations.append(
            "Review timeline events for chronological consistency"
        )

        return recommendations[:5]


# Global instance
multi_doc_analyzer = MultiDocumentAnalyzer()
