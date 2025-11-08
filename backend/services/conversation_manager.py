"""
Conversation Manager Service
Handles chat history, context retention, and conversation persistence like ChatGPT and Harvey AI
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import redis
from dataclasses import dataclass, asdict
from enum import Enum

from config.local_settings import DATABASE_CONFIG, REDIS_CONFIG

class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class ConversationStatus(Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"

@dataclass
class Message:
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    citations: List[Dict] = None
    processing_time: float = None
    token_usage: Dict[str, int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
            "citations": self.citations or [],
            "processing_time": self.processing_time,
            "token_usage": self.token_usage or {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        return cls(
            id=data["id"],
            conversation_id=data["conversation_id"],
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            citations=data.get("citations", []),
            processing_time=data.get("processing_time"),
            token_usage=data.get("token_usage", {})
        )

@dataclass
class Conversation:
    id: str
    user_id: str
    title: str
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_tokens: int = 0
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
            "total_tokens": self.total_tokens,
            "metadata": self.metadata or {}
        }

class ConversationManager:
    """
    Manages conversations and chat history with features like:
    - Persistent conversation storage
    - Context window management
    - Conversation summarization
    - Message search and retrieval
    - Real-time context retention
    """
    
    def __init__(self):
        # Database setup
        self.engine = create_engine(DATABASE_CONFIG["url"])
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
        
        # Redis for real-time context caching with decode_responses to avoid JSON serialization issues
        self.redis_client = redis.Redis.from_url(
            REDIS_CONFIG["url"],
            decode_responses=True  # Auto-decode bytes to strings
        )
        
        # Configuration
        self.max_context_messages = 20  # Maximum messages to keep in context
        self.context_token_limit = 8000  # Maximum tokens in context window
        self.conversation_cache_ttl = 3600  # 1 hour cache TTL
        
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Create conversation and message tables if they don't exist"""
        create_tables_sql = """
        -- Conversations table
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id VARCHAR(255) NOT NULL,
            title VARCHAR(500) NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            message_count INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            metadata JSONB DEFAULT '{}'::jsonb
        );
        
        -- Messages table
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT NOW(),
            metadata JSONB DEFAULT '{}'::jsonb,
            citations JSONB DEFAULT '[]'::jsonb,
            processing_time FLOAT,
            token_usage JSONB DEFAULT '{}'::jsonb
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
        """

        with self.engine.begin() as conn:
            conn.execute(text(create_tables_sql))
    
    async def create_conversation(self, user_id: str, title: str = None) -> Conversation:
        """Create a new conversation"""
        conversation_id = str(uuid.uuid4())
        
        if not title:
            title = f"Legal Consultation - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        conversation = Conversation(
            id=conversation_id,
            user_id=user_id,
            title=title,
            status=ConversationStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Insert into database
        insert_sql = """
        INSERT INTO conversations (id, user_id, title, status, created_at, updated_at)
        VALUES (:id, :user_id, :title, :status, :created_at, :updated_at)
        """

        with self.engine.begin() as conn:
            conn.execute(text(insert_sql), {
                "id": conversation.id,
                "user_id": conversation.user_id,
                "title": conversation.title,
                "status": conversation.status.value,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at
            })
        
        # Cache the conversation
        await self._cache_conversation(conversation)
        
        return conversation
    
    async def add_message(self, conversation_id: str, role: MessageRole, content: str, 
                         citations: List[Dict] = None, processing_time: float = None,
                         token_usage: Dict[str, int] = None, metadata: Dict[str, Any] = None) -> Message:
        """Add a message to a conversation"""
        message_id = str(uuid.uuid4())
        
        message = Message(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            timestamp=datetime.now(),
            citations=citations or [],
            processing_time=processing_time,
            token_usage=token_usage or {},
            metadata=metadata or {}
        )
        
        # Insert into database
        insert_sql = """
        INSERT INTO messages (id, conversation_id, role, content, timestamp, metadata, citations, processing_time, token_usage)
        VALUES (:id, :conversation_id, :role, :content, :timestamp, :metadata, :citations, :processing_time, :token_usage)
        """

        with self.engine.begin() as conn:
            conn.execute(text(insert_sql), {
                "id": message.id,
                "conversation_id": message.conversation_id,
                "role": message.role.value,
                "content": message.content,
                "timestamp": message.timestamp,
                "metadata": json.dumps(message.metadata),
                "citations": json.dumps(message.citations),
                "processing_time": message.processing_time,
                "token_usage": json.dumps(message.token_usage)
            })
        
        # Update conversation stats
        await self._update_conversation_stats(conversation_id, token_usage)
        
        # Update cache
        await self._cache_message(message)
        await self._update_conversation_context(conversation_id)
        
        return message
    
    async def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Message]:
        """Get conversation history with optional limit"""
        
        # Try cache first
        cached_messages = await self._get_cached_messages(conversation_id, limit)
        if cached_messages:
            return cached_messages
        
        # Query database
        query_sql = """
        SELECT id, conversation_id, role, content, timestamp, metadata, citations, processing_time, token_usage
        FROM messages 
        WHERE conversation_id = :conversation_id 
        ORDER BY timestamp ASC
        LIMIT :limit
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(query_sql), {
                "conversation_id": conversation_id,
                "limit": limit
            })
            
            messages = []
            for row in result:
                # PostgreSQL JSONB columns are automatically parsed to dicts by psycopg2
                metadata = row[5] if isinstance(row[5], dict) else (json.loads(row[5]) if row[5] else {})
                citations = row[6] if isinstance(row[6], list) else (json.loads(row[6]) if row[6] else [])
                token_usage = row[8] if isinstance(row[8], dict) else (json.loads(row[8]) if row[8] else {})

                message = Message(
                    id=str(row[0]),
                    conversation_id=str(row[1]),
                    role=MessageRole(row[2]),
                    content=row[3],
                    timestamp=row[4],
                    metadata=metadata,
                    citations=citations,
                    processing_time=row[7],
                    token_usage=token_usage
                )
                messages.append(message)
        
        # Cache the messages
        await self._cache_messages(conversation_id, messages)
        
        return messages
    
    async def get_conversation_context(self, conversation_id: str) -> List[Dict[str, str]]:
        """
        Get conversation context for LLM (optimized for token usage)
        Returns messages in OpenAI chat format with intelligent truncation
        """
        
        # Try to get from cache first
        cache_key = f"context:{conversation_id}"
        cached_context = self.redis_client.get(cache_key)

        if cached_context:
            # Handle both string and dict cases defensively
            if isinstance(cached_context, dict):
                return cached_context
            elif isinstance(cached_context, str):
                return json.loads(cached_context)
            else:
                # Fallback: try to decode if it's bytes
                return json.loads(cached_context.decode('utf-8') if isinstance(cached_context, bytes) else cached_context)
        
        # Get recent messages
        messages = await self.get_conversation_history(conversation_id, self.max_context_messages)
        
        # Convert to OpenAI format and manage token limits
        context = []
        total_tokens = 0
        
        # Add messages in reverse order (most recent first) until token limit
        for message in reversed(messages):
            # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
            message_tokens = len(message.content) // 4
            
            if total_tokens + message_tokens > self.context_token_limit:
                break
            
            context.insert(0, {
                "role": message.role.value,
                "content": message.content
            })
            total_tokens += message_tokens
        
        # Cache the context
        self.redis_client.setex(cache_key, 300, json.dumps(context))  # 5 minute cache
        
        return context
    
    async def get_user_conversations(self, user_id: str, limit: int = 20, offset: int = 0) -> List[Conversation]:
        """Get user's conversations with pagination"""
        query_sql = """
        SELECT id, user_id, title, status, created_at, updated_at, message_count, total_tokens, metadata
        FROM conversations 
        WHERE user_id = :user_id AND status != 'deleted'
        ORDER BY updated_at DESC
        LIMIT :limit OFFSET :offset
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(query_sql), {
                "user_id": user_id,
                "limit": limit,
                "offset": offset
            })
            
            conversations = []
            for row in result:
                # PostgreSQL JSONB columns are automatically parsed to dicts by psycopg2
                metadata = row[8] if isinstance(row[8], dict) else (json.loads(row[8]) if row[8] else {})

                conversation = Conversation(
                    id=str(row[0]),
                    user_id=row[1],
                    title=row[2],
                    status=ConversationStatus(row[3]),
                    created_at=row[4],
                    updated_at=row[5],
                    message_count=row[6] or 0,
                    total_tokens=row[7] or 0,
                    metadata=metadata
                )
                conversations.append(conversation)
        
        return conversations
    
    async def update_conversation_title(self, conversation_id: str, title: str) -> bool:
        """Update conversation title"""
        update_sql = """
        UPDATE conversations 
        SET title = :title, updated_at = :updated_at
        WHERE id = :conversation_id
        """

        with self.engine.begin() as conn:
            result = conn.execute(text(update_sql), {
                "title": title,
                "updated_at": datetime.now(),
                "conversation_id": conversation_id
            })

            # Clear cache
            await self._clear_conversation_cache(conversation_id)

            return result.rowcount > 0
    
    async def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation"""
        return await self._update_conversation_status(conversation_id, ConversationStatus.ARCHIVED)
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Soft delete a conversation"""
        return await self._update_conversation_status(conversation_id, ConversationStatus.DELETED)
    
    async def search_conversations(self, user_id: str, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversations by content"""
        search_sql = """
        SELECT DISTINCT c.id, c.title, c.updated_at, 
               ts_headline(m.content, plainto_tsquery(:query)) as highlight
        FROM conversations c
        JOIN messages m ON c.id = m.conversation_id
        WHERE c.user_id = :user_id 
          AND c.status = 'active'
          AND to_tsvector('english', m.content) @@ plainto_tsquery(:query)
        ORDER BY c.updated_at DESC
        LIMIT :limit
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(search_sql), {
                "user_id": user_id,
                "query": query,
                "limit": limit
            })
            
            results = []
            for row in result:
                results.append({
                    "conversation_id": str(row[0]),
                    "title": row[1],
                    "updated_at": row[2].isoformat(),
                    "highlight": row[3]
                })
        
        return results
    
    async def get_conversation_summary(self, conversation_id: str) -> Dict[str, Any]:
        """Get conversation summary and statistics"""
        summary_sql = """
        SELECT 
            c.title,
            c.created_at,
            c.updated_at,
            c.message_count,
            c.total_tokens,
            COUNT(m.id) as actual_message_count,
            MIN(m.timestamp) as first_message,
            MAX(m.timestamp) as last_message,
            SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) as user_messages,
            SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages
        FROM conversations c
        LEFT JOIN messages m ON c.id = m.conversation_id
        WHERE c.id = :conversation_id
        GROUP BY c.id, c.title, c.created_at, c.updated_at, c.message_count, c.total_tokens
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(summary_sql), {
                "conversation_id": conversation_id
            }).fetchone()
            
            if not result:
                return None
            
            return {
                "title": result[0],
                "created_at": result[1].isoformat(),
                "updated_at": result[2].isoformat(),
                "stored_message_count": result[3],
                "total_tokens": result[4],
                "actual_message_count": result[5],
                "first_message": result[6].isoformat() if result[6] else None,
                "last_message": result[7].isoformat() if result[7] else None,
                "user_messages": result[8],
                "assistant_messages": result[9],
                "duration_minutes": (result[7] - result[6]).total_seconds() / 60 if result[6] and result[7] else 0
            }
    
    async def auto_generate_title(self, conversation_id: str) -> str:
        """Auto-generate conversation title based on first few messages"""
        messages = await self.get_conversation_history(conversation_id, 3)
        
        if not messages:
            return "New Legal Consultation"
        
        # Get first user message
        first_user_message = None
        for msg in messages:
            if msg.role == MessageRole.USER:
                first_user_message = msg.content
                break
        
        if not first_user_message:
            return "New Legal Consultation"
        
        # Extract key legal terms and create title
        legal_keywords = [
            "contract", "agreement", "liability", "damages", "breach", "tort",
            "criminal", "civil", "constitutional", "property", "divorce", "marriage",
            "employment", "labor", "intellectual property", "patent", "trademark",
            "company", "corporate", "tax", "GST", "limitation", "procedure"
        ]
        
        content_lower = first_user_message.lower()
        found_keywords = [kw for kw in legal_keywords if kw in content_lower]
        
        if found_keywords:
            primary_keyword = found_keywords[0].title()
            return f"{primary_keyword} Legal Query - {datetime.now().strftime('%b %d')}"
        else:
            # Fallback: use first few words
            words = first_user_message.split()[:5]
            title = " ".join(words)
            if len(title) > 50:
                title = title[:47] + "..."
            return title
    
    # Private helper methods
    
    async def _update_conversation_stats(self, conversation_id: str, token_usage: Dict[str, int]):
        """Update conversation statistics"""
        tokens_used = sum(token_usage.values()) if token_usage else 0
        
        update_sql = """
        UPDATE conversations 
        SET message_count = message_count + 1,
            total_tokens = total_tokens + :tokens,
            updated_at = :updated_at
        WHERE id = :conversation_id
        """
        
        with self.engine.begin() as conn:
            conn.execute(text(update_sql), {
                "tokens": tokens_used,
                "updated_at": datetime.now(),
                "conversation_id": conversation_id
            })
    
    async def _update_conversation_status(self, conversation_id: str, status: ConversationStatus) -> bool:
        """Update conversation status"""
        update_sql = """
        UPDATE conversations
        SET status = :status, updated_at = :updated_at
        WHERE id = :conversation_id
        """

        with self.engine.begin() as conn:
            result = conn.execute(text(update_sql), {
                "status": status.value,
                "updated_at": datetime.now(),
                "conversation_id": conversation_id
            })

            # Clear cache
            await self._clear_conversation_cache(conversation_id)

            return result.rowcount > 0
    
    async def _cache_conversation(self, conversation: Conversation):
        """Cache conversation data"""
        cache_key = f"conversation:{conversation.id}"
        self.redis_client.setex(
            cache_key, 
            self.conversation_cache_ttl, 
            json.dumps(conversation.to_dict())
        )
    
    async def _cache_message(self, message: Message):
        """Cache individual message"""
        cache_key = f"message:{message.id}"
        self.redis_client.setex(cache_key, 3600, json.dumps(message.to_dict()))
    
    async def _cache_messages(self, conversation_id: str, messages: List[Message]):
        """Cache conversation messages"""
        cache_key = f"messages:{conversation_id}"
        messages_data = [msg.to_dict() for msg in messages]
        self.redis_client.setex(cache_key, 1800, json.dumps(messages_data))  # 30 minutes
    
    async def _get_cached_messages(self, conversation_id: str, limit: int) -> Optional[List[Message]]:
        """Get cached messages"""
        cache_key = f"messages:{conversation_id}"
        cached_data = self.redis_client.get(cache_key)

        if cached_data:
            # Handle both string and dict/list cases defensively
            if isinstance(cached_data, list):
                messages_data = cached_data
            elif isinstance(cached_data, str):
                messages_data = json.loads(cached_data)
            elif isinstance(cached_data, bytes):
                messages_data = json.loads(cached_data.decode('utf-8'))
            else:
                # If it's already a dict or other type, try to use it
                messages_data = cached_data

            messages = [Message.from_dict(data) for data in messages_data]
            return messages[-limit:] if len(messages) > limit else messages

        return None
    
    async def _update_conversation_context(self, conversation_id: str):
        """Update conversation context cache"""
        # Clear existing context cache to force refresh
        cache_key = f"context:{conversation_id}"
        self.redis_client.delete(cache_key)
    
    async def _clear_conversation_cache(self, conversation_id: str):
        """Clear all cache entries for a conversation"""
        keys_to_delete = [
            f"conversation:{conversation_id}",
            f"messages:{conversation_id}",
            f"context:{conversation_id}"
        ]
        
        for key in keys_to_delete:
            self.redis_client.delete(key)

# Global instance
conversation_manager = ConversationManager()