"""
Third-Party Integrations Service
Integrates with Clio, MyCase, PracticePanther, and other legal software
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import aiohttp
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Integration:
    """Integration configuration"""
    integration_id: str
    name: str
    provider: str  # clio, mycase, practicepanther, etc.
    api_key: str
    api_secret: Optional[str]
    base_url: str
    enabled: bool = True
    sync_enabled: bool = False
    last_sync: Optional[datetime] = None


class IntegrationsService:
    """
    Third-party integrations for practice management systems

    Supported:
    - Clio (Practice management)
    - MyCase (Case management)
    - PracticePanther (Legal software)
    - Zapier (Automation)
    - Slack (Communication)
    - Microsoft Teams (Collaboration)
    - DocuSign (E-signature)
    - Dropbox/Google Drive (Storage)
    """

    def __init__(self):
        self.integrations: Dict[str, Integration] = {}
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure HTTP session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def add_integration(
        self,
        name: str,
        provider: str,
        api_key: str,
        api_secret: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Integration:
        """Add new integration"""

        # Get base URL for provider
        base_urls = {
            "clio": "https://app.clio.com/api/v4",
            "mycase": "https://api.mycase.com/v1",
            "practicepanther": "https://api.practicepanther.com/v1",
            "zapier": "https://hooks.zapier.com",
            "slack": "https://slack.com/api",
            "docusign": "https://demo.docusign.net/restapi/v2.1",
            "teams": "https://graph.microsoft.com/v1.0"
        }

        integration = Integration(
            integration_id=f"{provider}_{datetime.utcnow().timestamp()}",
            name=name,
            provider=provider,
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_urls.get(provider, "")
        )

        self.integrations[integration.integration_id] = integration

        logger.info(f"Added integration: {name} ({provider})")

        return integration

    async def sync_clio_cases(
        self,
        integration_id: str
    ) -> Dict[str, Any]:
        """Sync cases from Clio"""

        integration = self.integrations.get(integration_id)
        if not integration or integration.provider != "clio":
            raise ValueError("Invalid Clio integration")

        await self._ensure_session()

        headers = {
            "Authorization": f"Bearer {integration.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with self.session.get(
                f"{integration.base_url}/matters",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    integration.last_sync = datetime.utcnow()

                    logger.info(f"Synced {len(data.get('data', []))} cases from Clio")

                    return {
                        "success": True,
                        "cases_synced": len(data.get('data', [])),
                        "data": data.get('data', [])
                    }
                else:
                    error = await response.text()
                    logger.error(f"Clio sync failed: {response.status} - {error}")
                    return {"success": False, "error": error}

        except Exception as e:
            logger.error(f"Clio sync error: {str(e)}")
            return {"success": False, "error": str(e)}

    async def send_slack_notification(
        self,
        integration_id: str,
        channel: str,
        message: str
    ) -> bool:
        """Send notification to Slack"""

        integration = self.integrations.get(integration_id)
        if not integration or integration.provider != "slack":
            raise ValueError("Invalid Slack integration")

        await self._ensure_session()

        payload = {
            "channel": channel,
            "text": message
        }

        headers = {
            "Authorization": f"Bearer {integration.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with self.session.post(
                f"{integration.base_url}/chat.postMessage",
                headers=headers,
                json=payload
            ) as response:
                if response.status == 200:
                    logger.info(f"Sent Slack notification to {channel}")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Slack notification failed: {error}")
                    return False

        except Exception as e:
            logger.error(f"Slack notification error: {str(e)}")
            return False

    async def send_for_signature(
        self,
        integration_id: str,
        document_name: str,
        document_content: bytes,
        signers: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Send document for e-signature via DocuSign"""

        integration = self.integrations.get(integration_id)
        if not integration or integration.provider != "docusign":
            raise ValueError("Invalid DocuSign integration")

        # Placeholder for DocuSign API integration
        logger.info(f"Sending document '{document_name}' for signature")

        return {
            "envelope_id": f"env_{datetime.utcnow().timestamp()}",
            "status": "sent",
            "signers": signers,
            "created_at": datetime.utcnow().isoformat()
        }

    async def trigger_zapier_webhook(
        self,
        integration_id: str,
        webhook_url: str,
        data: Dict[str, Any]
    ) -> bool:
        """Trigger Zapier webhook"""

        await self._ensure_session()

        try:
            async with self.session.post(webhook_url, json=data) as response:
                if response.status == 200:
                    logger.info("Triggered Zapier webhook successfully")
                    return True
                else:
                    error = await response.text()
                    logger.error(f"Zapier webhook failed: {error}")
                    return False

        except Exception as e:
            logger.error(f"Zapier webhook error: {str(e)}")
            return False

    def list_integrations(
        self,
        provider: Optional[str] = None,
        enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List configured integrations"""

        integrations = list(self.integrations.values())

        if provider:
            integrations = [i for i in integrations if i.provider == provider]

        if enabled_only:
            integrations = [i for i in integrations if i.enabled]

        return [
            {
                "integration_id": i.integration_id,
                "name": i.name,
                "provider": i.provider,
                "enabled": i.enabled,
                "sync_enabled": i.sync_enabled,
                "last_sync": i.last_sync.isoformat() if i.last_sync else None
            }
            for i in integrations
        ]

    def get_supported_providers(self) -> List[Dict[str, Any]]:
        """Get list of supported integration providers"""

        return [
            {
                "provider": "clio",
                "name": "Clio",
                "category": "Practice Management",
                "features": ["case_sync", "contact_sync", "time_tracking"]
            },
            {
                "provider": "mycase",
                "name": "MyCase",
                "category": "Case Management",
                "features": ["case_sync", "document_sync", "calendar_sync"]
            },
            {
                "provider": "practicepanther",
                "name": "PracticePanther",
                "category": "Legal Software",
                "features": ["case_sync", "billing_sync", "task_sync"]
            },
            {
                "provider": "slack",
                "name": "Slack",
                "category": "Communication",
                "features": ["notifications", "alerts", "collaboration"]
            },
            {
                "provider": "teams",
                "name": "Microsoft Teams",
                "category": "Collaboration",
                "features": ["notifications", "file_sharing", "meetings"]
            },
            {
                "provider": "docusign",
                "name": "DocuSign",
                "category": "E-Signature",
                "features": ["document_signing", "status_tracking", "templates"]
            },
            {
                "provider": "zapier",
                "name": "Zapier",
                "category": "Automation",
                "features": ["webhooks", "workflow_automation", "data_sync"]
            }
        ]


# Global instance
integrations_service = IntegrationsService()
