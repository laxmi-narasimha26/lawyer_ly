"""
Real-time Web Search Service for Legal Research
Integrates with multiple search APIs and legal databases
"""
import asyncio
import aiohttp
from typing import List, Dict, Any, Optional
from datetime import datetime
import structlog
from config import settings

logger = structlog.get_logger(__name__)


class WebSearchService:
    """
    Multi-provider web search service for legal research
    Supports: Google Custom Search, Tavily AI, SerpAPI, Indian legal databases
    """

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def _ensure_session(self):
        """Ensure aiohttp session is created"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def close(self):
        """Close aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def search_web(
        self,
        query: str,
        num_results: int = 10,
        region: str = "in",
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Search the web using available providers

        Args:
            query: Search query
            num_results: Number of results to return
            region: Region code (default: India)
            language: Language code (default: English)

        Returns:
            List of search results with title, url, snippet, source
        """
        await self._ensure_session()

        try:
            # Try providers in order of preference
            results = await self._google_custom_search(query, num_results, region, language)

            if not results:
                logger.warning("Primary search failed, trying fallback")
                results = await self._duckduckgo_search(query, num_results)

            logger.info(f"Web search completed: {len(results)} results for '{query[:50]}...'")
            return results

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            return []

    async def _google_custom_search(
        self,
        query: str,
        num_results: int,
        region: str,
        language: str
    ) -> List[Dict[str, Any]]:
        """Google Custom Search API"""
        try:
            # Simulated response structure (replace with actual API call)
            # In production, use: api_key = settings.GOOGLE_SEARCH_API_KEY
            # cx = settings.GOOGLE_SEARCH_CX

            api_key = getattr(settings, 'GOOGLE_SEARCH_API_KEY', None)
            cx = getattr(settings, 'GOOGLE_SEARCH_CX', None)

            if not api_key or not cx:
                logger.info("Google Custom Search not configured, skipping")
                return []

            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": api_key,
                "cx": cx,
                "q": query,
                "num": min(num_results, 10),
                "gl": region,
                "lr": f"lang_{language}"
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        {
                            "title": item.get("title", ""),
                            "url": item.get("link", ""),
                            "snippet": item.get("snippet", ""),
                            "source": "Google",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        for item in data.get("items", [])
                    ]
                else:
                    logger.warning(f"Google search failed with status {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Google Custom Search error: {str(e)}")
            return []

    async def _duckduckgo_search(
        self,
        query: str,
        num_results: int
    ) -> List[Dict[str, Any]]:
        """DuckDuckGo search (fallback, free alternative)"""
        try:
            # Using DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []

                    # Extract from related topics
                    for topic in data.get("RelatedTopics", [])[:num_results]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "")[:100],
                                "url": topic.get("FirstURL", ""),
                                "snippet": topic.get("Text", ""),
                                "source": "DuckDuckGo",
                                "timestamp": datetime.utcnow().isoformat()
                            })

                    return results
                else:
                    return []

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {str(e)}")
            return []

    async def search_legal_databases(
        self,
        query: str,
        databases: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search multiple Indian legal databases

        Args:
            query: Legal search query
            databases: List of databases to search (default: all)

        Returns:
            Dictionary mapping database name to results
        """
        if databases is None:
            databases = ["indiankanoon", "scconline", "manupatra", "casemine"]

        tasks = []
        for db in databases:
            if db == "indiankanoon":
                tasks.append(self._search_indian_kanoon(query))
            elif db == "scconline":
                tasks.append(self._search_scc_online(query))
            elif db == "manupatra":
                tasks.append(self._search_manupatra(query))
            elif db == "casemine":
                tasks.append(self._search_casemine(query))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            db: res if not isinstance(res, Exception) else []
            for db, res in zip(databases, results)
        }

    async def _search_indian_kanoon(self, query: str) -> List[Dict[str, Any]]:
        """Search IndianKanoon.org (public legal database)"""
        try:
            await self._ensure_session()

            # IndianKanoon search endpoint
            url = "https://api.indiankanoon.org/search/"
            params = {
                "formInput": query,
                "pagenum": 0
            }

            # Note: IndianKanoon requires API key for production use
            # This is a simplified implementation
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        {
                            "title": doc.get("title", ""),
                            "url": f"https://indiankanoon.org/doc/{doc.get('tid', '')}/",
                            "snippet": doc.get("headline", ""),
                            "court": doc.get("court", ""),
                            "date": doc.get("docdatestring", ""),
                            "citation": doc.get("citation", ""),
                            "source": "IndianKanoon",
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        for doc in data.get("docs", [])[:10]
                    ]
                else:
                    logger.warning(f"IndianKanoon search failed: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"IndianKanoon search error: {str(e)}")
            return []

    async def _search_scc_online(self, query: str) -> List[Dict[str, Any]]:
        """Search SCC Online (requires subscription)"""
        try:
            # Placeholder for SCC Online API integration
            # Requires institutional subscription
            logger.info("SCC Online search placeholder - requires subscription")
            return []

        except Exception as e:
            logger.error(f"SCC Online search error: {str(e)}")
            return []

    async def _search_manupatra(self, query: str) -> List[Dict[str, Any]]:
        """Search Manupatra (requires subscription)"""
        try:
            # Placeholder for Manupatra API integration
            # Requires institutional subscription
            logger.info("Manupatra search placeholder - requires subscription")
            return []

        except Exception as e:
            logger.error(f"Manupatra search error: {str(e)}")
            return []

    async def _search_casemine(self, query: str) -> List[Dict[str, Any]]:
        """Search CaseMine (AI-powered legal research)"""
        try:
            # Placeholder for CaseMine API integration
            logger.info("CaseMine search placeholder - requires API key")
            return []

        except Exception as e:
            logger.error(f"CaseMine search error: {str(e)}")
            return []

    async def search_international_legal(
        self,
        query: str,
        sources: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search international legal databases

        Sources: EUR-Lex, WorldLII, HUDOC, etc.
        """
        if sources is None:
            sources = ["eur-lex", "worldlii"]

        tasks = []
        for source in sources:
            if source == "eur-lex":
                tasks.append(self._search_eur_lex(query))
            elif source == "worldlii":
                tasks.append(self._search_worldlii(query))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            source: res if not isinstance(res, Exception) else []
            for source, res in zip(sources, results)
        }

    async def _search_eur_lex(self, query: str) -> List[Dict[str, Any]]:
        """Search EUR-Lex (EU legal documents)"""
        try:
            # EUR-Lex SPARQL endpoint
            url = "http://publications.europa.eu/webapi/rdf/sparql"

            # Simplified query - production would use proper SPARQL
            logger.info("EUR-Lex search placeholder - requires SPARQL query")
            return []

        except Exception as e:
            logger.error(f"EUR-Lex search error: {str(e)}")
            return []

    async def _search_worldlii(self, query: str) -> List[Dict[str, Any]]:
        """Search WorldLII (World Legal Information Institute)"""
        try:
            # WorldLII search endpoint
            url = "http://www.worldlii.org/cgi-bin/sinosrch.cgi"
            params = {
                "query": query,
                "results": 10
            }

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    # Would need to parse HTML response
                    logger.info("WorldLII search - HTML parsing required")
                    return []
                else:
                    return []

        except Exception as e:
            logger.error(f"WorldLII search error: {str(e)}")
            return []

    async def deep_research(
        self,
        query: str,
        include_web: bool = True,
        include_indian_legal: bool = True,
        include_international: bool = False
    ) -> Dict[str, Any]:
        """
        Perform comprehensive deep research across all sources

        Returns aggregated results from web search and legal databases
        """
        results = {
            "query": query,
            "timestamp": datetime.utcnow().isoformat(),
            "sources": {}
        }

        tasks = []

        if include_web:
            tasks.append(self.search_web(query))

        if include_indian_legal:
            tasks.append(self.search_legal_databases(query))

        if include_international:
            tasks.append(self.search_international_legal(query))

        completed_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate results
        if include_web and len(completed_results) > 0:
            results["sources"]["web"] = completed_results[0] if not isinstance(completed_results[0], Exception) else []

        if include_indian_legal and len(completed_results) > 1:
            results["sources"]["indian_legal"] = completed_results[1] if not isinstance(completed_results[1], Exception) else {}

        if include_international and len(completed_results) > 2:
            results["sources"]["international"] = completed_results[2] if not isinstance(completed_results[2], Exception) else {}

        # Count total results
        total_results = 0
        if "web" in results["sources"]:
            total_results += len(results["sources"]["web"])
        if "indian_legal" in results["sources"]:
            for db_results in results["sources"]["indian_legal"].values():
                total_results += len(db_results)
        if "international" in results["sources"]:
            for source_results in results["sources"]["international"].values():
                total_results += len(source_results)

        results["total_results"] = total_results

        logger.info(f"Deep research completed: {total_results} total results from {len(results['sources'])} source types")

        return results


# Global instance
web_search_service = WebSearchService()
