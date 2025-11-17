"""
Real-time Web Search Service (like Perplexity)
Provides up-to-date legal information through web search integration
"""

from typing import List, Dict, Any, Optional
import os
import aiohttp
import asyncio
from datetime import datetime
import json

class WebSearchService:
    """
    Web search service for real-time legal information
    Integrates with Google Custom Search, Serp API, and other search engines
    """

    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID")
        self.serp_api_key = os.getenv("SERP_API_KEY")
        self.enabled = bool(self.google_api_key and self.google_cse_id)

    async def search_legal_web(
        self,
        query: str,
        max_results: int = 10,
        focus_domains: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform web search focused on legal sources

        Args:
            query: Search query
            max_results: Maximum number of results
            focus_domains: Preferred domains (e.g., 'indiankanoon.org', 'sci.gov.in')

        Returns:
            Search results with titles, snippets, URLs, and metadata
        """
        if not self.enabled:
            return {
                "enabled": False,
                "message": "Web search not configured",
                "results": []
            }

        # Build search query with legal focus
        legal_query = self._enhance_legal_query(query, focus_domains)

        # Search using Google Custom Search
        results = await self._google_custom_search(legal_query, max_results)

        return {
            "enabled": True,
            "query": query,
            "enhanced_query": legal_query,
            "results": results,
            "count": len(results),
            "timestamp": datetime.utcnow().isoformat()
        }

    def _enhance_legal_query(self, query: str, focus_domains: Optional[List[str]] = None) -> str:
        """Enhance query for better legal search results"""
        enhanced = query

        # Add legal context keywords if not present
        legal_keywords = ["law", "legal", "case", "statute", "court", "judgment"]
        if not any(keyword in query.lower() for keyword in legal_keywords):
            enhanced = f"{query} law legal"

        # Add domain restrictions if specified
        if focus_domains:
            domain_str = " OR ".join([f"site:{domain}" for domain in focus_domains])
            enhanced = f"{enhanced} ({domain_str})"

        return enhanced

    async def _google_custom_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """Perform Google Custom Search"""
        if not self.google_api_key or not self.google_cse_id:
            return []

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.google_api_key,
            "cx": self.google_cse_id,
            "q": query,
            "num": min(max_results, 10),  # Google CSE max is 10 per request
            "dateRestrict": "y5",  # Last 5 years
            "sort": "date"  # Most recent first
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return []

                    data = await response.json()
                    items = data.get("items", [])

                    results = []
                    for item in items:
                        results.append({
                            "title": item.get("title"),
                            "snippet": item.get("snippet"),
                            "url": item.get("link"),
                            "display_url": item.get("displayLink"),
                            "source": self._identify_source_type(item.get("link", "")),
                            "date": self._extract_date(item.get("snippet", ""))
                        })

                    return results

        except Exception as e:
            print(f"Google search error: {e}")
            return []

    def _identify_source_type(self, url: str) -> str:
        """Identify the type of legal source"""
        url_lower = url.lower()

        if "indiankanoon.org" in url_lower:
            return "Case Law Database"
        elif "sci.gov.in" in url_lower:
            return "Supreme Court of India"
        elif "legislative.gov.in" in url_lower or "indiacode.nic.in" in url_lower:
            return "Legislation"
        elif "barandbench.com" in url_lower or "livelaw.in" in url_lower:
            return "Legal News"
        elif "manupatra.com" in url_lower or "scconline.com" in url_lower:
            return "Legal Research Platform"
        elif ".gov.in" in url_lower:
            return "Government Source"
        else:
            return "Web Source"

    def _extract_date(self, snippet: str) -> Optional[str]:
        """Extract date from snippet if present"""
        # Simple date extraction (can be enhanced)
        import re
        date_patterns = [
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
            r'\d{4}-\d{2}-\d{2}'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, snippet)
            if match:
                return match.group(0)

        return None

    async def search_case_law(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        year_from: Optional[int] = None,
        year_to: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Specialized search for case law

        Args:
            query: Search query
            jurisdiction: e.g., 'Supreme Court', 'High Court'
            year_from: Start year for cases
            year_to: End year for cases
        """
        # Build specialized case law query
        case_query = query

        if jurisdiction:
            case_query += f" {jurisdiction}"

        if year_from and year_to:
            case_query += f" {year_from}..{year_to}"

        # Focus on case law databases
        focus_domains = [
            "indiankanoon.org",
            "sci.gov.in",
            "judis.nic.in"
        ]

        result = await self.search_legal_web(case_query, max_results=15, focus_domains=focus_domains)
        return result.get("results", [])

    async def search_legislation(
        self,
        query: str,
        act_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Specialized search for legislation and statutes"""
        leg_query = query

        if act_name:
            leg_query = f"{act_name} {query}"

        # Focus on legislation sources
        focus_domains = [
            "indiacode.nic.in",
            "legislative.gov.in",
            "lawmin.gov.in"
        ]

        result = await self.search_legal_web(leg_query, max_results=10, focus_domains=focus_domains)
        return result.get("results", [])

    async def search_legal_news(
        self,
        query: str,
        recent_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Search for recent legal news and updates"""
        news_query = f"{query} news updates"

        # Focus on legal news sites
        focus_domains = [
            "barandbench.com",
            "livelaw.in",
            "scobserver.in",
            "legallyindia.com"
        ]

        result = await self.search_legal_web(news_query, max_results=10, focus_domains=focus_domains)
        return result.get("results", [])


# Singleton instance
web_search_service = WebSearchService()
