"""
Advanced Memory System for Legal AI
Implements hierarchical and episodic memory alongside existing sliding window
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import structlog
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np

from database.models import Query, Conversation, DocumentChunk
from services.azure_openai_service import azure_openai_service

logger = structlog.get_logger(__name__)


@dataclass
class MemoryNode:
    """Node in hierarchical memory structure"""
    id: str
    content: str
    summary: str
    timestamp: datetime
    importance: float  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodicMemory:
    """Episodic memory representing a specific event or interaction"""
    id: str
    query: str
    response: str
    context: List[str]
    timestamp: datetime
    emotional_valence: float  # -1.0 (negative) to 1.0 (positive)
    importance: float
    tags: List[str]
    related_documents: List[str]
    metadata: Dict[str, Any]


class HierarchicalMemory:
    """
    Hierarchical memory system for organizing information at multiple levels

    Levels:
    1. Short-term (current conversation) - Sliding window
    2. Working memory (recent important items) - Last N high-importance items
    3. Long-term (summarized historical data) - Hierarchical summaries
    """

    def __init__(self, max_short_term: int = 10, max_working: int = 50):
        self.max_short_term = max_short_term
        self.max_working = max_working
        self.nodes: Dict[str, MemoryNode] = {}
        self.root_nodes: List[str] = []

    async def add_memory(
        self,
        content: str,
        timestamp: datetime,
        importance: float,
        parent_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryNode:
        """Add new memory node to hierarchy"""

        # Generate unique ID
        node_id = f"mem_{timestamp.timestamp()}_{len(self.nodes)}"

        # Create summary for this memory
        summary = await self._generate_summary(content)

        # Create node
        node = MemoryNode(
            id=node_id,
            content=content,
            summary=summary,
            timestamp=timestamp,
            importance=importance,
            metadata=metadata or {}
        )

        # Link to parent if specified
        if parent_id and parent_id in self.nodes:
            node.parent_id = parent_id
            self.nodes[parent_id].children.append(node_id)
        else:
            self.root_nodes.append(node_id)

        self.nodes[node_id] = node

        logger.info(f"Added hierarchical memory node: {node_id}, importance: {importance:.2f}")

        return node

    async def _generate_summary(self, content: str, max_length: int = 100) -> str:
        """Generate concise summary of content"""
        if len(content) <= max_length:
            return content

        try:
            # Use AI to generate summary
            prompt = f"Summarize the following in {max_length} characters or less:\n\n{content}"

            summary = await azure_openai_service.generate_completion(
                prompt=prompt,
                max_tokens=50,
                temperature=0.3
            )

            return summary[:max_length]

        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}")
            return content[:max_length] + "..."

    async def retrieve_relevant_memories(
        self,
        query: str,
        max_results: int = 10,
        min_importance: float = 0.3
    ) -> List[MemoryNode]:
        """Retrieve most relevant memories based on query"""

        relevant_nodes = []

        for node in self.nodes.values():
            if node.importance >= min_importance:
                # Calculate relevance score
                relevance = await self._calculate_relevance(query, node)

                if relevance > 0.5:
                    node.access_count += 1
                    node.last_accessed = datetime.utcnow()
                    relevant_nodes.append((relevance, node))

        # Sort by relevance and return top results
        relevant_nodes.sort(key=lambda x: x[0], reverse=True)

        result = [node for _, node in relevant_nodes[:max_results]]

        logger.info(f"Retrieved {len(result)} relevant memories for query")

        return result

    async def _calculate_relevance(self, query: str, node: MemoryNode) -> float:
        """Calculate relevance score between query and memory node"""

        # Simple keyword overlap (in production, use embeddings)
        query_words = set(query.lower().split())
        content_words = set(node.summary.lower().split())

        overlap = len(query_words & content_words)
        total = len(query_words | content_words)

        if total == 0:
            return 0.0

        keyword_score = overlap / total

        # Factor in importance and recency
        recency_score = 1.0
        if node.last_accessed:
            hours_ago = (datetime.utcnow() - node.last_accessed).total_seconds() / 3600
            recency_score = 1.0 / (1.0 + hours_ago / 24.0)  # Decay over days

        combined_score = (
            keyword_score * 0.5 +
            node.importance * 0.3 +
            recency_score * 0.2
        )

        return combined_score

    async def consolidate_memories(self, threshold: int = 100):
        """Consolidate old memories into higher-level summaries"""

        if len(self.nodes) < threshold:
            return

        # Group old, low-importance memories
        old_cutoff = datetime.utcnow() - timedelta(days=7)
        to_consolidate = [
            node for node in self.nodes.values()
            if node.timestamp < old_cutoff and node.importance < 0.5
        ]

        if len(to_consolidate) < 5:
            return

        # Create consolidated summary
        combined_content = "\n".join([node.summary for node in to_consolidate])
        consolidated_summary = await self._generate_summary(combined_content, max_length=500)

        # Create new consolidated node
        consolidated_node = await self.add_memory(
            content=consolidated_summary,
            timestamp=datetime.utcnow(),
            importance=0.6,
            metadata={"consolidated_count": len(to_consolidate)}
        )

        # Remove old nodes
        for node in to_consolidate:
            if node.id in self.nodes:
                del self.nodes[node.id]
            if node.id in self.root_nodes:
                self.root_nodes.remove(node.id)

        logger.info(f"Consolidated {len(to_consolidate)} memories into {consolidated_node.id}")


class EpisodicMemorySystem:
    """
    Episodic memory system for storing and retrieving specific interaction episodes
    Similar to human episodic memory - remembers specific events and their context
    """

    def __init__(self, max_episodes: int = 1000):
        self.max_episodes = max_episodes
        self.episodes: List[EpisodicMemory] = []
        self.episode_index: Dict[str, List[int]] = defaultdict(list)

    async def add_episode(
        self,
        query: str,
        response: str,
        context: List[str],
        tags: Optional[List[str]] = None,
        related_documents: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EpisodicMemory:
        """Add new episodic memory"""

        # Calculate importance based on various factors
        importance = await self._calculate_importance(query, response, context)

        # Estimate emotional valence (positive/negative)
        emotional_valence = await self._estimate_emotional_valence(response)

        # Create episode
        episode = EpisodicMemory(
            id=f"ep_{len(self.episodes)}_{datetime.utcnow().timestamp()}",
            query=query,
            response=response,
            context=context,
            timestamp=datetime.utcnow(),
            emotional_valence=emotional_valence,
            importance=importance,
            tags=tags or [],
            related_documents=related_documents or [],
            metadata=metadata or {}
        )

        self.episodes.append(episode)

        # Index by tags
        for tag in episode.tags:
            self.episode_index[tag].append(len(self.episodes) - 1)

        # Prune if exceeds max
        if len(self.episodes) > self.max_episodes:
            await self._prune_episodes()

        logger.info(f"Added episodic memory: {episode.id}, importance: {importance:.2f}")

        return episode

    async def _calculate_importance(
        self,
        query: str,
        response: str,
        context: List[str]
    ) -> float:
        """Calculate importance score for episode"""

        # Factors:
        # 1. Query complexity (longer, more complex = more important)
        # 2. Response length (detailed responses = more important)
        # 3. Context richness (more context = more important)

        query_score = min(len(query.split()) / 50.0, 1.0)
        response_score = min(len(response.split()) / 200.0, 1.0)
        context_score = min(len(context) / 10.0, 1.0)

        importance = (query_score * 0.3 + response_score * 0.5 + context_score * 0.2)

        return importance

    async def _estimate_emotional_valence(self, response: str) -> float:
        """Estimate emotional tone of response (-1.0 to 1.0)"""

        # Simple keyword-based sentiment (in production, use proper sentiment analysis)
        positive_words = ["successfully", "excellent", "correct", "helpful", "positive", "resolved"]
        negative_words = ["error", "failed", "incorrect", "unfortunately", "cannot", "denied"]

        response_lower = response.lower()

        positive_count = sum(1 for word in positive_words if word in response_lower)
        negative_count = sum(1 for word in negative_words if word in response_lower)

        if positive_count + negative_count == 0:
            return 0.0

        valence = (positive_count - negative_count) / (positive_count + negative_count)

        return valence

    async def retrieve_similar_episodes(
        self,
        query: str,
        max_results: int = 5,
        min_importance: float = 0.3,
        time_window_days: Optional[int] = None
    ) -> List[EpisodicMemory]:
        """Retrieve episodes similar to current query"""

        relevant_episodes = []

        time_cutoff = None
        if time_window_days:
            time_cutoff = datetime.utcnow() - timedelta(days=time_window_days)

        for episode in self.episodes:
            # Filter by time window if specified
            if time_cutoff and episode.timestamp < time_cutoff:
                continue

            # Filter by importance
            if episode.importance < min_importance:
                continue

            # Calculate similarity
            similarity = await self._calculate_similarity(query, episode)

            if similarity > 0.4:
                relevant_episodes.append((similarity, episode))

        # Sort by similarity
        relevant_episodes.sort(key=lambda x: x[0], reverse=True)

        result = [ep for _, ep in relevant_episodes[:max_results]]

        logger.info(f"Retrieved {len(result)} similar episodes")

        return result

    async def _calculate_similarity(self, query: str, episode: EpisodicMemory) -> float:
        """Calculate similarity between query and episode"""

        # Simple keyword overlap
        query_words = set(query.lower().split())
        episode_words = set(episode.query.lower().split())

        overlap = len(query_words & episode_words)
        total = len(query_words | episode_words)

        if total == 0:
            return 0.0

        return overlap / total

    async def _prune_episodes(self):
        """Remove least important old episodes"""

        # Sort by importance and recency
        scored_episodes = [
            (
                ep.importance * 0.7 +
                (1.0 - (datetime.utcnow() - ep.timestamp).days / 365.0) * 0.3,
                i,
                ep
            )
            for i, ep in enumerate(self.episodes)
        ]

        scored_episodes.sort(key=lambda x: x[0], reverse=True)

        # Keep top episodes
        keep_indices = set(idx for _, idx, _ in scored_episodes[:self.max_episodes])

        self.episodes = [ep for i, ep in enumerate(self.episodes) if i in keep_indices]

        # Rebuild index
        self.episode_index.clear()
        for i, episode in enumerate(self.episodes):
            for tag in episode.tags:
                self.episode_index[tag].append(i)

        logger.info(f"Pruned episodes to {len(self.episodes)}")


class UnifiedMemorySystem:
    """
    Unified memory system combining all memory types:
    - Sliding window (short-term)
    - Hierarchical memory (structured long-term)
    - Episodic memory (event-based)
    """

    def __init__(self):
        self.hierarchical = HierarchicalMemory()
        self.episodic = EpisodicMemorySystem()
        self.sliding_window: List[Dict[str, Any]] = []
        self.window_size = 10

    async def add_interaction(
        self,
        query: str,
        response: str,
        context: List[str],
        importance: float,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add interaction to all applicable memory systems"""

        timestamp = datetime.utcnow()

        # 1. Add to sliding window (short-term)
        self.sliding_window.append({
            "query": query,
            "response": response,
            "timestamp": timestamp
        })

        if len(self.sliding_window) > self.window_size:
            self.sliding_window.pop(0)

        # 2. Add to hierarchical memory (if important enough)
        if importance >= 0.4:
            await self.hierarchical.add_memory(
                content=f"Q: {query}\nA: {response}",
                timestamp=timestamp,
                importance=importance,
                metadata=metadata
            )

        # 3. Add to episodic memory
        await self.episodic.add_episode(
            query=query,
            response=response,
            context=context,
            tags=tags,
            metadata=metadata
        )

        logger.info(f"Added interaction to unified memory system")

    async def retrieve_context(
        self,
        query: str,
        max_items: int = 20
    ) -> Dict[str, Any]:
        """Retrieve relevant context from all memory systems"""

        # Get from sliding window
        recent = self.sliding_window[-5:]

        # Get from hierarchical memory
        hierarchical_memories = await self.hierarchical.retrieve_relevant_memories(
            query=query,
            max_results=10
        )

        # Get from episodic memory
        similar_episodes = await self.episodic.retrieve_similar_episodes(
            query=query,
            max_results=5
        )

        return {
            "recent_context": recent,
            "hierarchical_memories": [
                {
                    "summary": mem.summary,
                    "importance": mem.importance,
                    "timestamp": mem.timestamp.isoformat()
                }
                for mem in hierarchical_memories
            ],
            "similar_episodes": [
                {
                    "query": ep.query,
                    "response": ep.response[:200],
                    "importance": ep.importance,
                    "timestamp": ep.timestamp.isoformat()
                }
                for ep in similar_episodes
            ]
        }


# Global instance
unified_memory = UnifiedMemorySystem()
