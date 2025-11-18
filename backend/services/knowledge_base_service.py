"""
Firm-Specific Knowledge Base Service
Manages firm precedents, templates, and internal knowledge
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class KnowledgeEntry:
    """Knowledge base entry"""
    entry_id: str
    title: str
    category: str  # precedent, template, memo, research, best_practice
    jurisdiction: str
    practice_area: str
    content: str
    tags: List[str]
    author_id: str
    created_at: datetime
    updated_at: datetime
    version: int = 1
    access_level: str = "firm"  # public, firm, department, private
    citations: List[str] = None
    related_entries: List[str] = None


class KnowledgeBaseService:
    """
    Firm-specific knowledge base management

    Features:
    - Store firm precedents and successful arguments
    - Legal research templates
    - Internal memos and research
    - Best practices documentation
    - Jurisdiction-specific templates
    - Versioning and change tracking
    - Search and retrieval
    """

    def __init__(self):
        self.entries: List[KnowledgeEntry] = []
        self._initialize_sample_entries()

    def _initialize_sample_entries(self):
        """Initialize sample knowledge base entries"""

        # Sample precedent entry
        self.entries.append(KnowledgeEntry(
            entry_id="kb_001",
            title="Successful Section 138 NI Act Defense Strategy",
            category="precedent",
            jurisdiction="India",
            practice_area="Commercial Law",
            content="Detailed strategy for defending Section 138 NI Act cases...",
            tags=["negotiable instruments", "cheque bounce", "criminal", "defense"],
            author_id="lawyer_001",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            citations=["2023 SCC 145", "AIR 2022 SC 234"]
        ))

    async def add_entry(
        self,
        title: str,
        category: str,
        jurisdiction: str,
        practice_area: str,
        content: str,
        tags: List[str],
        author_id: str,
        access_level: str = "firm",
        citations: Optional[List[str]] = None,
        related_entries: Optional[List[str]] = None
    ) -> KnowledgeEntry:
        """Add new knowledge base entry"""

        entry = KnowledgeEntry(
            entry_id=f"kb_{len(self.entries) + 1:04d}",
            title=title,
            category=category,
            jurisdiction=jurisdiction,
            practice_area=practice_area,
            content=content,
            tags=tags,
            author_id=author_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            access_level=access_level,
            citations=citations or [],
            related_entries=related_entries or []
        )

        self.entries.append(entry)

        logger.info(f"Added knowledge base entry: {title}")

        return entry

    async def update_entry(
        self,
        entry_id: str,
        updates: Dict[str, Any]
    ) -> KnowledgeEntry:
        """Update knowledge base entry"""

        entry = next(
            (e for e in self.entries if e.entry_id == entry_id),
            None
        )

        if not entry:
            raise ValueError(f"Entry {entry_id} not found")

        # Update fields
        for key, value in updates.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        # Increment version and update timestamp
        entry.version += 1
        entry.updated_at = datetime.utcnow()

        logger.info(f"Updated knowledge base entry: {entry_id} (v{entry.version})")

        return entry

    async def search_entries(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        jurisdiction: Optional[str] = None,
        practice_area: Optional[str] = None,
        tags: Optional[List[str]] = None,
        access_level: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search knowledge base entries"""

        entries = self.entries

        # Filter by category
        if category:
            entries = [e for e in entries if e.category == category]

        # Filter by jurisdiction
        if jurisdiction:
            entries = [e for e in entries if e.jurisdiction == jurisdiction]

        # Filter by practice area
        if practice_area:
            entries = [e for e in entries if e.practice_area == practice_area]

        # Filter by tags
        if tags:
            entries = [
                e for e in entries
                if any(tag in e.tags for tag in tags)
            ]

        # Filter by access level
        if access_level:
            entries = [e for e in entries if e.access_level == access_level]

        # Text search in title and content
        if query:
            query_lower = query.lower()
            entries = [
                e for e in entries
                if query_lower in e.title.lower() or query_lower in e.content.lower()
            ]

        # Sort by relevance and date
        entries.sort(key=lambda e: e.updated_at, reverse=True)

        return [
            {
                "entry_id": e.entry_id,
                "title": e.title,
                "category": e.category,
                "jurisdiction": e.jurisdiction,
                "practice_area": e.practice_area,
                "content_preview": e.content[:200] + "..." if len(e.content) > 200 else e.content,
                "tags": e.tags,
                "author_id": e.author_id,
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat(),
                "version": e.version,
                "citations_count": len(e.citations or [])
            }
            for e in entries
        ]

    async def get_entry(
        self,
        entry_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get full knowledge base entry"""

        entry = next(
            (e for e in self.entries if e.entry_id == entry_id),
            None
        )

        if not entry:
            return None

        return {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "category": entry.category,
            "jurisdiction": entry.jurisdiction,
            "practice_area": entry.practice_area,
            "content": entry.content,
            "tags": entry.tags,
            "author_id": entry.author_id,
            "created_at": entry.created_at.isoformat(),
            "updated_at": entry.updated_at.isoformat(),
            "version": entry.version,
            "access_level": entry.access_level,
            "citations": entry.citations or [],
            "related_entries": entry.related_entries or []
        }

    def get_categories(self) -> List[Dict[str, int]]:
        """Get all categories with entry counts"""

        from collections import Counter

        category_counts = Counter(e.category for e in self.entries)

        return [
            {"category": cat, "count": count}
            for cat, count in category_counts.items()
        ]

    def get_practice_areas(self) -> List[Dict[str, int]]:
        """Get all practice areas with entry counts"""

        from collections import Counter

        area_counts = Counter(e.practice_area for e in self.entries)

        return [
            {"practice_area": area, "count": count}
            for area, count in area_counts.items()
        ]

    def get_popular_tags(self, limit: int = 20) -> List[Dict[str, int]]:
        """Get most popular tags"""

        from collections import Counter

        all_tags = []
        for entry in self.entries:
            all_tags.extend(entry.tags)

        tag_counts = Counter(all_tags)

        return [
            {"tag": tag, "count": count}
            for tag, count in tag_counts.most_common(limit)
        ]


# Global instance
knowledge_base_service = KnowledgeBaseService()
