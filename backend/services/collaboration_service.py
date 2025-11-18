"""
Real-time Collaboration Service
Multiple lawyers working on same case simultaneously using WebSockets
"""
import asyncio
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CollaborationSession:
    """Active collaboration session"""
    session_id: str
    document_id: str
    participants: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    lock_holder: Optional[str] = None
    changes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Change:
    """Document change event"""
    change_id: str
    user_id: str
    timestamp: datetime
    change_type: str  # insert, delete, format, comment
    position: int
    content: str
    metadata: Dict[str, Any]


class CollaborationService:
    """
    Real-time collaboration service using WebSockets and CRDT

    Features:
    - Multi-user editing
    - Conflict resolution (CRDT - Conflict-free Replicated Data Types)
    - Presence indicators
    - Document locking
    - Change tracking
    - Real-time cursors
    - Comments and annotations
    """

    def __init__(self):
        self.active_sessions: Dict[str, CollaborationSession] = {}
        self.user_connections: Dict[str, Set[str]] = {}  # user_id -> set of session_ids

    async def create_session(
        self,
        document_id: str,
        user_id: str
    ) -> CollaborationSession:
        """Create new collaboration session"""

        session_id = f"collab_{document_id}_{datetime.utcnow().timestamp()}"

        session = CollaborationSession(
            session_id=session_id,
            document_id=document_id,
            participants={user_id}
        )

        self.active_sessions[session_id] = session

        # Track user connection
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(session_id)

        logger.info(f"Created collaboration session: {session_id}")

        return session

    async def join_session(
        self,
        session_id: str,
        user_id: str
    ) -> CollaborationSession:
        """Join existing collaboration session"""

        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]
        session.participants.add(user_id)
        session.last_activity = datetime.utcnow()

        # Track user connection
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(session_id)

        # Broadcast join event
        await self._broadcast_event(session_id, {
            "type": "user_joined",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        logger.info(f"User {user_id} joined session {session_id}")

        return session

    async def leave_session(
        self,
        session_id: str,
        user_id: str
    ):
        """Leave collaboration session"""

        if session_id not in self.active_sessions:
            return

        session = self.active_sessions[session_id]
        session.participants.discard(user_id)

        # Remove from user connections
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(session_id)

        # Release lock if held
        if session.lock_holder == user_id:
            session.lock_holder = None

        # Broadcast leave event
        await self._broadcast_event(session_id, {
            "type": "user_left",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Clean up empty sessions
        if not session.participants:
            del self.active_sessions[session_id]
            logger.info(f"Closed empty session: {session_id}")
        else:
            logger.info(f"User {user_id} left session {session_id}")

    async def apply_change(
        self,
        session_id: str,
        user_id: str,
        change: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply change to document with conflict resolution"""

        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        session = self.active_sessions[session_id]

        # Create change record
        change_record = Change(
            change_id=f"change_{len(session.changes)}_{datetime.utcnow().timestamp()}",
            user_id=user_id,
            timestamp=datetime.utcnow(),
            change_type=change.get("type", "insert"),
            position=change.get("position", 0),
            content=change.get("content", ""),
            metadata=change.get("metadata", {})
        )

        # Apply CRDT conflict resolution
        resolved_change = await self._resolve_conflicts(
            session,
            change_record
        )

        # Add to changes log
        session.changes.append({
            "change_id": resolved_change.change_id,
            "user_id": resolved_change.user_id,
            "timestamp": resolved_change.timestamp.isoformat(),
            "type": resolved_change.change_type,
            "position": resolved_change.position,
            "content": resolved_change.content
        })

        session.last_activity = datetime.utcnow()

        # Broadcast change to all participants
        await self._broadcast_event(session_id, {
            "type": "document_change",
            "change": {
                "id": resolved_change.change_id,
                "user_id": resolved_change.user_id,
                "timestamp": resolved_change.timestamp.isoformat(),
                "change_type": resolved_change.change_type,
                "position": resolved_change.position,
                "content": resolved_change.content
            }
        }, exclude_user=user_id)

        logger.info(f"Applied change in session {session_id} by user {user_id}")

        return {
            "change_id": resolved_change.change_id,
            "applied": True
        }

    async def _resolve_conflicts(
        self,
        session: CollaborationSession,
        change: Change
    ) -> Change:
        """Resolve conflicts using CRDT (Operational Transformation)"""

        # Simple conflict resolution: Last Write Wins (LWW)
        # In production, use proper CRDT like Yjs or Automerge

        # Adjust position based on recent changes
        position_offset = 0

        for existing_change in reversed(session.changes[-10:]):  # Check last 10 changes
            if existing_change["timestamp"] > (datetime.utcnow().timestamp() - 5):  # Within 5 seconds
                if existing_change["position"] <= change.position:
                    if existing_change["type"] == "insert":
                        position_offset += len(existing_change["content"])
                    elif existing_change["type"] == "delete":
                        position_offset -= len(existing_change["content"])

        # Adjust position
        change.position += position_offset

        return change

    async def request_lock(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """Request exclusive lock on document"""

        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]

        if session.lock_holder is None:
            session.lock_holder = user_id

            await self._broadcast_event(session_id, {
                "type": "lock_acquired",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"User {user_id} acquired lock on session {session_id}")
            return True

        return False

    async def release_lock(
        self,
        session_id: str,
        user_id: str
    ) -> bool:
        """Release document lock"""

        if session_id not in self.active_sessions:
            return False

        session = self.active_sessions[session_id]

        if session.lock_holder == user_id:
            session.lock_holder = None

            await self._broadcast_event(session_id, {
                "type": "lock_released",
                "user_id": user_id,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.info(f"User {user_id} released lock on session {session_id}")
            return True

        return False

    async def add_comment(
        self,
        session_id: str,
        user_id: str,
        position: int,
        comment: str
    ) -> Dict[str, Any]:
        """Add comment/annotation to document"""

        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not found")

        comment_id = f"comment_{datetime.utcnow().timestamp()}"

        comment_data = {
            "comment_id": comment_id,
            "user_id": user_id,
            "position": position,
            "comment": comment,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Broadcast comment
        await self._broadcast_event(session_id, {
            "type": "comment_added",
            "comment": comment_data
        })

        return comment_data

    async def update_cursor(
        self,
        session_id: str,
        user_id: str,
        position: int
    ):
        """Update user's cursor position"""

        if session_id not in self.active_sessions:
            return

        # Broadcast cursor update
        await self._broadcast_event(session_id, {
            "type": "cursor_update",
            "user_id": user_id,
            "position": position,
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user=user_id)

    async def _broadcast_event(
        self,
        session_id: str,
        event: Dict[str, Any],
        exclude_user: Optional[str] = None
    ):
        """Broadcast event to all session participants"""

        if session_id not in self.active_sessions:
            return

        session = self.active_sessions[session_id]

        # In production, use WebSocket connections
        # For now, just log
        for user_id in session.participants:
            if exclude_user and user_id == exclude_user:
                continue

            logger.debug(f"Broadcasting to {user_id}: {event['type']}")

    def get_active_sessions(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of active collaboration sessions"""

        sessions = []

        for session_id, session in self.active_sessions.items():
            if user_id and user_id not in session.participants:
                continue

            sessions.append({
                "session_id": session.session_id,
                "document_id": session.document_id,
                "participants": list(session.participants),
                "participant_count": len(session.participants),
                "created_at": session.created_at.isoformat(),
                "last_activity": session.last_activity.isoformat(),
                "is_locked": session.lock_holder is not None,
                "lock_holder": session.lock_holder
            })

        return sessions


# Global instance
collaboration_service = CollaborationService()
