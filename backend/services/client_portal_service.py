"""
Client Portal Service
Secure client access to case information, documents, and e-signature
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import secrets
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ClientPortalAccess:
    """Client portal access configuration"""
    access_id: str
    client_id: str
    client_email: str
    access_token: str
    case_ids: List[str]
    permissions: List[str]  # view_documents, download, upload, sign, message
    expires_at: datetime
    created_at: datetime
    last_accessed: Optional[datetime] = None


@dataclass
class ClientMessage:
    """Message between lawyer and client"""
    message_id: str
    case_id: str
    sender_id: str
    sender_type: str  # lawyer, client
    recipient_id: str
    subject: str
    body: str
    timestamp: datetime
    read: bool = False
    attachments: List[str] = None


class ClientPortalService:
    """
    Client portal for secure client interaction

    Features:
    - Secure client login with tokens
    - Case status viewing
    - Document access and upload
    - E-signature integration
    - Secure messaging
    - Appointment scheduling
    - Invoice viewing
    - Payment integration
    """

    def __init__(self):
        self.portal_access: List[ClientPortalAccess] = []
        self.messages: List[ClientMessage] = []
        self.document_shares: Dict[str, List[str]] = {}  # document_id -> [client_ids]

    async def create_client_access(
        self,
        client_id: str,
        client_email: str,
        case_ids: List[str],
        permissions: Optional[List[str]] = None,
        validity_days: int = 90
    ) -> ClientPortalAccess:
        """Create portal access for client"""

        if permissions is None:
            permissions = ["view_documents", "download", "message"]

        # Generate secure access token
        access_token = secrets.token_urlsafe(32)

        access = ClientPortalAccess(
            access_id=f"access_{datetime.utcnow().timestamp()}",
            client_id=client_id,
            client_email=client_email,
            access_token=access_token,
            case_ids=case_ids,
            permissions=permissions,
            expires_at=datetime.utcnow() + timedelta(days=validity_days),
            created_at=datetime.utcnow()
        )

        self.portal_access.append(access)

        logger.info(f"Created portal access for client {client_id}")

        return access

    async def verify_access(
        self,
        access_token: str
    ) -> Optional[ClientPortalAccess]:
        """Verify client access token"""

        access = next(
            (a for a in self.portal_access if a.access_token == access_token),
            None
        )

        if not access:
            return None

        # Check expiration
        if access.expires_at < datetime.utcnow():
            logger.warning(f"Expired access token for client {access.client_id}")
            return None

        # Update last accessed
        access.last_accessed = datetime.utcnow()

        return access

    async def get_client_dashboard(
        self,
        client_id: str
    ) -> Dict[str, Any]:
        """Get client portal dashboard data"""

        access = next(
            (a for a in self.portal_access if a.client_id == client_id),
            None
        )

        if not access:
            raise ValueError(f"No portal access for client {client_id}")

        # Get case information
        cases = []
        for case_id in access.case_ids:
            cases.append({
                "case_id": case_id,
                "status": "active",  # Would fetch from database
                "last_updated": datetime.utcnow().isoformat(),
                "next_hearing": None
            })

        # Get recent documents
        documents = self._get_client_documents(client_id)

        # Get unread messages
        unread_messages = sum(
            1 for m in self.messages
            if m.recipient_id == client_id and not m.read
        )

        return {
            "client_id": client_id,
            "access_expires": access.expires_at.isoformat(),
            "cases": cases,
            "documents": documents[:10],  # Latest 10
            "unread_messages": unread_messages,
            "permissions": access.permissions
        }

    def _get_client_documents(
        self,
        client_id: str
    ) -> List[Dict[str, Any]]:
        """Get documents accessible to client"""

        documents = []

        for doc_id, client_ids in self.document_shares.items():
            if client_id in client_ids:
                documents.append({
                    "document_id": doc_id,
                    "filename": f"Document_{doc_id}.pdf",
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "size_bytes": 0,
                    "requires_signature": False
                })

        return documents

    async def share_document(
        self,
        document_id: str,
        client_ids: List[str],
        requires_signature: bool = False
    ) -> Dict[str, Any]:
        """Share document with clients"""

        if document_id not in self.document_shares:
            self.document_shares[document_id] = []

        # Add clients to share list
        for client_id in client_ids:
            if client_id not in self.document_shares[document_id]:
                self.document_shares[document_id].append(client_id)

        logger.info(f"Shared document {document_id} with {len(client_ids)} clients")

        return {
            "document_id": document_id,
            "shared_with": client_ids,
            "requires_signature": requires_signature,
            "shared_at": datetime.utcnow().isoformat()
        }

    async def send_message(
        self,
        case_id: str,
        sender_id: str,
        sender_type: str,
        recipient_id: str,
        subject: str,
        body: str,
        attachments: Optional[List[str]] = None
    ) -> ClientMessage:
        """Send message between lawyer and client"""

        message = ClientMessage(
            message_id=f"msg_{datetime.utcnow().timestamp()}",
            case_id=case_id,
            sender_id=sender_id,
            sender_type=sender_type,
            recipient_id=recipient_id,
            subject=subject,
            body=body,
            timestamp=datetime.utcnow(),
            attachments=attachments or []
        )

        self.messages.append(message)

        logger.info(f"Message sent from {sender_type} {sender_id} to {recipient_id}")

        return message

    async def get_messages(
        self,
        user_id: str,
        case_id: Optional[str] = None,
        unread_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get messages for user"""

        messages = [
            m for m in self.messages
            if m.recipient_id == user_id or m.sender_id == user_id
        ]

        if case_id:
            messages = [m for m in messages if m.case_id == case_id]

        if unread_only:
            messages = [m for m in messages if not m.read and m.recipient_id == user_id]

        # Sort by timestamp (newest first)
        messages.sort(key=lambda m: m.timestamp, reverse=True)

        return [
            {
                "message_id": m.message_id,
                "case_id": m.case_id,
                "sender_id": m.sender_id,
                "sender_type": m.sender_type,
                "recipient_id": m.recipient_id,
                "subject": m.subject,
                "body": m.body,
                "timestamp": m.timestamp.isoformat(),
                "read": m.read,
                "attachments": m.attachments
            }
            for m in messages
        ]

    async def mark_message_read(
        self,
        message_id: str,
        user_id: str
    ) -> bool:
        """Mark message as read"""

        message = next(
            (m for m in self.messages if m.message_id == message_id),
            None
        )

        if not message:
            return False

        if message.recipient_id == user_id:
            message.read = True
            return True

        return False

    async def schedule_appointment(
        self,
        client_id: str,
        lawyer_id: str,
        case_id: str,
        date_time: datetime,
        duration_minutes: int,
        type: str,  # consultation, hearing, meeting
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Schedule appointment with client"""

        appointment = {
            "appointment_id": f"appt_{datetime.utcnow().timestamp()}",
            "client_id": client_id,
            "lawyer_id": lawyer_id,
            "case_id": case_id,
            "date_time": date_time.isoformat(),
            "duration_minutes": duration_minutes,
            "type": type,
            "notes": notes,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat()
        }

        logger.info(f"Scheduled {type} appointment for client {client_id}")

        return appointment

    def get_active_clients(self) -> List[Dict[str, Any]]:
        """Get list of clients with active portal access"""

        now = datetime.utcnow()

        active_access = [
            a for a in self.portal_access
            if a.expires_at > now
        ]

        return [
            {
                "client_id": a.client_id,
                "client_email": a.client_email,
                "case_count": len(a.case_ids),
                "permissions": a.permissions,
                "created_at": a.created_at.isoformat(),
                "expires_at": a.expires_at.isoformat(),
                "last_accessed": a.last_accessed.isoformat() if a.last_accessed else None
            }
            for a in active_access
        ]


# Global instance
client_portal_service = ClientPortalService()
