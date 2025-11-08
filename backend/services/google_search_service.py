"""
Google Custom Search Engine (CSE) service for web search capabilities
Enables searching the internet for latest legal information
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = structlog.get_logger(__name__)


class SearchResult:
    """Search result model"""
    def __init__(self, title: str, link: str, snippet: str, source: str = None):
        self.title = title
        self.link = link
        self.snippet = snippet
        self.source = source or self._extract_source(link)
        self.timestamp = datetime.utcnow().isoformat()

    def _extract_source(self, link: str) -> str:
        """Extract domain name from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(link).netloc
            # Remove 'www.' prefix
            return domain.replace('www.', '')
        except:
            return "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "title": self.title,
            "link": self.link,
            "snippet": self.snippet,
            "source": self.source,
            "timestamp": self.timestamp
        }


class GoogleSearchService:
    """Service for Google Custom Search Engine integration"""

    # Pre-configured Indian legal websites for CSE
    INDIAN_LEGAL_SITES = [
        "indiankanoon.org",           # Case law database
        "sci.gov.in",                  # Supreme Court of India
        "egazette.nic.in",            # Official gazette
        "legislative.gov.in",          # Legislative Department
        "lawmin.gov.in",              # Ministry of Law and Justice
        "ncdrc.nic.in",               # National Consumer Disputes Redressal Commission
        "delhihighcourt.nic.in",      # Delhi High Court
        "bombayhighcourt.nic.in",     # Bombay High Court
        "mhc.tn.gov.in",              # Madras High Court
        "highcourtofkerala.nic.in",   # Kerala High Court
        "causelists.nic.in",          # Cause lists portal
        "latestlaws.com",             # Latest legal updates
        "livelaw.in",                 # Legal news
        "barandbench.com",            # Legal news and analysis
        "scconline.com",              # Supreme Court cases online
        "manupatrafast.in",           # Legal research platform
    ]

    def __init__(self, api_key: str = None, search_engine_id: str = None, enabled: bool = True):
        """
        Initialize Google Search service

        Args:
            api_key: Google API key
            search_engine_id: Google CSE ID
            enabled: Whether the service is enabled
        """
        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.enabled = enabled and bool(api_key) and bool(search_engine_id)
        self.service = None

        if self.enabled:
            try:
                self.service = build("customsearch", "v1", developerKey=self.api_key)
                logger.info(
                    "Google Search service initialized",
                    search_engine_id=self.search_engine_id,
                    configured_sites=len(self.INDIAN_LEGAL_SITES)
                )
            except Exception as e:
                logger.error("Failed to initialize Google Search service", error=str(e))
                self.enabled = False
        else:
            logger.info("Google Search service disabled - no API credentials configured")

    async def search(
        self,
        query: str,
        num_results: int = 5,
        restrict_to_legal_sites: bool = True,
        **kwargs
    ) -> List[SearchResult]:
        """
        Perform web search using Google CSE

        Args:
            query: Search query
            num_results: Number of results to return (max 10)
            restrict_to_legal_sites: Whether to restrict search to legal sites
            **kwargs: Additional search parameters

        Returns:
            List of search results
        """
        if not self.enabled:
            logger.warning("Google Search service is disabled - returning empty results")
            return []

        try:
            # Build search query with site restrictions
            search_query = query
            if restrict_to_legal_sites:
                # Add site restrictions to prioritize legal sites
                site_restriction = " OR ".join([f"site:{site}" for site in self.INDIAN_LEGAL_SITES[:5]])
                search_query = f"{query} ({site_restriction})"

            # Execute search
            result = self.service.cse().list(
                q=search_query,
                cx=self.search_engine_id,
                num=min(num_results, 10),  # Google CSE max is 10
                **kwargs
            ).execute()

            # Parse results
            search_results = []
            items = result.get('items', [])

            for item in items:
                search_result = SearchResult(
                    title=item.get('title', ''),
                    link=item.get('link', ''),
                    snippet=item.get('snippet', ''),
                )
                search_results.append(search_result)

            logger.info(
                "Web search completed",
                query=query,
                num_results=len(search_results),
                restricted=restrict_to_legal_sites
            )

            return search_results

        except HttpError as e:
            logger.error(
                "Google Search API error",
                error=str(e),
                query=query
            )
            return []
        except Exception as e:
            logger.error(
                "Unexpected error during web search",
                error=str(e),
                query=query
            )
            return []

    async def search_latest_legal_updates(
        self,
        query: str,
        num_results: int = 5,
        date_range: str = "y"  # y=past year, m=past month, w=past week, d=past day
    ) -> List[SearchResult]:
        """
        Search for latest legal updates with date filtering

        Args:
            query: Search query
            num_results: Number of results
            date_range: Time range (y/m/w/d)

        Returns:
            List of recent search results
        """
        return await self.search(
            query=query,
            num_results=num_results,
            restrict_to_legal_sites=True,
            dateRestrict=date_range
        )

    def should_use_web_search(self, query: str, mode: str = "qa") -> bool:
        """
        Determine if query should use web search

        Criteria:
        - Query contains temporal keywords (latest, recent, current, 2024, 2025)
        - Query asks about recent amendments or notifications
        - Query is in "research" or "current_affairs" mode

        Args:
            query: User query
            mode: Query mode

        Returns:
            True if web search should be used
        """
        if not self.enabled:
            return False

        query_lower = query.lower()

        # Temporal keywords indicating need for latest information
        temporal_keywords = [
            'latest', 'recent', 'current', 'new', 'updated',
            '2024', '2025', 'this year', 'last month',
            'amendment', 'notification', 'gazette',
            'breaking', 'announced', 'passed',
            'today', 'yesterday', 'this week'
        ]

        # Check if query contains temporal keywords
        for keyword in temporal_keywords:
            if keyword in query_lower:
                return True

        # Always use web search for research mode
        if mode in ['research', 'current_affairs', 'news']:
            return True

        return False

    def format_search_context(self, search_results: List[SearchResult], max_length: int = 2000) -> str:
        """
        Format search results as context for LLM

        Args:
            search_results: List of search results
            max_length: Maximum context length

        Returns:
            Formatted context string
        """
        if not search_results:
            return ""

        context_parts = ["**Web Search Results:**\n"]

        for i, result in enumerate(search_results, 1):
            result_text = f"\n{i}. **{result.title}**\n"
            result_text += f"   Source: {result.source}\n"
            result_text += f"   {result.snippet}\n"
            result_text += f"   Link: {result.link}\n"

            # Check if adding this result exceeds max length
            if len("".join(context_parts)) + len(result_text) > max_length:
                break

            context_parts.append(result_text)

        return "".join(context_parts)


# Create singleton instance (will be disabled until configured)
google_search_service = GoogleSearchService(
    api_key=None,  # Will be set from config
    search_engine_id=None,  # Will be set from config
    enabled=False
)
