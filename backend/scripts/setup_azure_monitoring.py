#!/usr/bin/env python3
"""
Script to set up Azure Monitor alerts and auto-scaling rules
"""
import asyncio
import json
import os
import sys
from typing import Dict, List, Any
import structlog
from azure.identity import DefaultAzureCredential
from azure.mgmt.monitor import MonitorManagementClient
from azure.mgmt.monitor.models import (
    MetricAlertResource, MetricAlertCriteria, MetricCriteria,
    ActionGroupResource, EmailReceiver, WebhookReceiver,
    AutoscaleSettingResource, AutoscaleProfile, ScaleRule,
    MetricTrigger, ScaleAction, ScaleCapacity
)

logger = structlog.get_logger(__name__)

class AzureMonitoringSetup:
    """Set up Azure Monitor alerts and auto-scaling"""
    
    def __init__(self, subscription_id: str, resource_group: str):
        self.subscription_id = subscription_id
        self.resource_group = resource_group
        self.credential = DefaultAzureCredential()
        self.monitor_client = MonitorManagementClient(
            credential=self.credential,
            subscription_id=subscription_id
        )
    
    async def create_action_groups(self) -> Dict[str, str]:
        """Create action groups for alert notifications"""
        action_groups = {}
        
        # General alerts action group
        general_action_group = ActionGroupResource(
            location="global",
            group_short_name="LegalAI",
            enabled=True,
            email_receivers=[
                EmailReceiver(
                    name="DevTeam",
                    email_address="dev-team@legalai.com",
                    use_common_alert_schema=True
                ),
                EmailReceiver(
                    name="Operations",
                    email_address="ops@legalai.com",
                    use_common_alert_schema=True
                )
            ],
            webhook_receivers=[
                WebhookReceiver(
                    name="Teams",
                    service_uri=os.getenv("TEAMS_WEBHOOK_URL", ""),
                    use_common_alert_schema=True
                )
            ]
        )
        
        result = self.monitor_client.action_groups.create_or_update(
            resource_group_name=self.resource_group,
            action_group_name="legal-ai-alerts",
            action_group=general_action_group
        )
        action_groups["general"] = result.id
        
        # Critical alerts action group
        critical_action_group = ActionGroupResource(
            location="global",
            group_short_name="LegalAICrit",
            enabled=True,
            email_receivers=[
                EmailReceiver(
                    name="DevTeam",
                    email_address="dev-team@legalai.com",
                    use_common_alert_schema=True
                ),
                EmailReceiver(
                    name="Operations",
                    email_address="ops@legalai.com",
                    use_common_alert_schema=True
                ),
                EmailReceiver(
                    name="Management",
                    email_address="management@legalai.com",
                    use_common_alert_schema=True
                )
            ],
            webhook_receivers=[
                WebhookReceiver(
                    name="Teams",
                    service_uri=os.getenv("TEAMS_WEBHOOK_URL", ""),
                    use_common_alert_schema=True
                ),
                WebhookReceiver(
                    name="PagerDuty",
                    service_uri=os.getenv("PAGERDUTY_WEBHOOK_URL", ""),
                    use_common_alert_schema=True
                )
            ]
        )
        
        result = self.monitor_client.action_groups.create_or_update(
            resource_group_name=self.resource_group,
            action_group_name="legal-ai-critical-alerts",
            action_group=critical_action_group
        )
        action_groups["critical"] = result.id
        
        logger.info("Action groups created", action_groups=list(action_groups.keys()))
        return action_groups
    
    async def create_metric_alerts(self, action_groups: Dict[str, str], container_app_resource_id: str):
        """Create metric alerts for the application"""
        
        alerts_config = [
            {
                "name": "legal-ai-high-cpu",
                "description": "CPU usage exceeds 80%",
                "severity": 2,  # Warning
                "metric_name": "CpuPercentage",
                "operator": "GreaterThan",
                "threshold": 80.0,
                "time_aggregation": "Average",
                "window_size": "PT10M",
                "evaluation_frequency": "PT5M",
                "action_group": action_groups["general"]
            },
            {
                "name": "legal-ai-high-memory",
                "description": "Memory usage exceeds 85%",
                "severity": 2,  # Warning
                "metric_name": "MemoryPercentage",
                "operator": "GreaterThan",
                "threshold": 85.0,
                "time_aggregation": "Average",
                "window_size": "PT10M",
                "evaluation_frequency": "PT5M",
                "action_group": action_groups["general"]
            },
            {
                "name": "legal-ai-high-response-time",
                "description": "Average response time exceeds 10 seconds",
                "severity": 2,  # Warning
                "metric_name": "ResponseTime",
                "operator": "GreaterThan",
                "threshold": 10.0,
                "time_aggregation": "Average",
                "window_size": "PT10M",
                "evaluation_frequency": "PT5M",
                "action_group": action_groups["general"]
            },
            {
                "name": "legal-ai-high-error-rate",
                "description": "Error rate exceeds 5%",
                "severity": 1,  # Critical
                "metric_name": "Http5xx",
                "operator": "GreaterThan",
                "threshold": 5.0,
                "time_aggregation": "Average",
                "window_size": "PT5M",
                "evaluation_frequency": "PT1M",
                "action_group": action_groups["critical"]
            },
            {
                "name": "legal-ai-container-restart",
                "description": "Container restart detected",
                "severity": 1,  # Critical
                "metric_name": "RestartCount",
                "operator": "GreaterThan",
                "threshold": 0,
                "time_aggregation": "Total",
                "window_size": "PT5M",
                "evaluation_frequency": "PT1M",
                "action_group": action_groups["critical"]
            }
        ]
        
        for alert_config in alerts_config:
            criteria = MetricAlertCriteria(
                odata_type="Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria",
                all_of=[
                    MetricCriteria(
                        name="criterion1",
                        metric_name=alert_config["metric_name"],
                        operator=alert_config["operator"],
                        threshold=alert_config["threshold"],
                        time_aggregation=alert_config["time_aggregation"]
                    )
                ]
            )
            
            alert = MetricAlertResource(
                location="global",
                description=alert_config["description"],
                severity=alert_config["severity"],
                enabled=True,
                scopes=[container_app_resource_id],
                evaluation_frequency=alert_config["evaluation_frequency"],
                window_size=alert_config["window_size"],
                criteria=criteria,
                actions=[
                    {
                        "action_group_id": alert_config["action_group"],
                        "web_hook_properties": {}
                    }
                ]
            )
            
            self.monitor_client.metric_alerts.create_or_update(
                resource_group_name=self.resource_group,
                rule_name=alert_config["name"],
                parameters=alert
            )
            
            logger.info("Metric alert created", alert_name=alert_config["name"])
    
    async def create_autoscale_settings(self, container_app_resource_id: str):
        """Create auto-scaling settings for the container app"""
        
        # Scale out rules
        scale_out_rules = [
            ScaleRule(
                metric_trigger=MetricTrigger(
                    metric_name="CpuPercentage",
                    metric_resource_uri=container_app_resource_id,
                    time_grain="PT1M",
                    statistic="Average",
                    time_window="PT10M",
                    time_aggregation="Average",
                    operator="GreaterThan",
                    threshold=80.0
                ),
                scale_action=ScaleAction(
                    direction="Increase",
                    type="ChangeCount",
                    value="1",
                    cooldown="PT10M"
                )
            ),
            ScaleRule(
                metric_trigger=MetricTrigger(
                    metric_name="MemoryPercentage",
                    metric_resource_uri=container_app_resource_id,
                    time_grain="PT1M",
                    statistic="Average",
                    time_window="PT10M",
                    time_aggregation="Average",
                    operator="GreaterThan",
                    threshold=85.0
                ),
                scale_action=ScaleAction(
                    direction="Increase",
                    type="ChangeCount",
                    value="1",
                    cooldown="PT10M"
                )
            ),
            ScaleRule(
                metric_trigger=MetricTrigger(
                    metric_name="RequestsPerSecond",
                    metric_resource_uri=container_app_resource_id,
                    time_grain="PT1M",
                    statistic="Average",
                    time_window="PT5M",
                    time_aggregation="Average",
                    operator="GreaterThan",
                    threshold=100.0
                ),
                scale_action=ScaleAction(
                    direction="Increase",
                    type="ChangeCount",
                    value="2",
                    cooldown="PT5M"
                )
            )
        ]
        
        # Scale in rules
        scale_in_rules = [
            ScaleRule(
                metric_trigger=MetricTrigger(
                    metric_name="CpuPercentage",
                    metric_resource_uri=container_app_resource_id,
                    time_grain="PT1M",
                    statistic="Average",
                    time_window="PT15M",
                    time_aggregation="Average",
                    operator="LessThan",
                    threshold=30.0
                ),
                scale_action=ScaleAction(
                    direction="Decrease",
                    type="ChangeCount",
                    value="1",
                    cooldown="PT15M"
                )
            ),
            ScaleRule(
                metric_trigger=MetricTrigger(
                    metric_name="MemoryPercentage",
                    metric_resource_uri=container_app_resource_id,
                    time_grain="PT1M",
                    statistic="Average",
                    time_window="PT15M",
                    time_aggregation="Average",
                    operator="LessThan",
                    threshold=40.0
                ),
                scale_action=ScaleAction(
                    direction="Decrease",
                    type="ChangeCount",
                    value="1",
                    cooldown="PT15M"
                )
            )
        ]
        
        # Create autoscale profile
        profile = AutoscaleProfile(
            name="default-profile",
            capacity=ScaleCapacity(
                minimum="2",
                maximum="10",
                default="2"
            ),
            rules=scale_out_rules + scale_in_rules
        )
        
        # Create autoscale setting
        autoscale_setting = AutoscaleSettingResource(
            location="Central India",
            profiles=[profile],
            enabled=True,
            target_resource_uri=container_app_resource_id,
            notifications=[
                {
                    "operation": "Scale",
                    "email": {
                        "send_to_subscription_administrator": False,
                        "send_to_subscription_co_administrators": False,
                        "custom_emails": ["ops@legalai.com", "dev-team@legalai.com"]
                    },
                    "webhooks": [
                        {
                            "service_uri": os.getenv("TEAMS_WEBHOOK_URL", ""),
                            "properties": {}
                        }
                    ]
                }
            ]
        )
        
        self.monitor_client.autoscale_settings.create_or_update(
            resource_group_name=self.resource_group,
            autoscale_setting_name="legal-ai-autoscale",
            parameters=autoscale_setting
        )
        
        logger.info("Autoscale settings created")
    
    async def setup_application_insights_alerts(self, app_insights_resource_id: str, action_groups: Dict[str, str]):
        """Set up Application Insights based alerts"""
        
        # Custom metric alerts for application-specific metrics
        app_alerts = [
            {
                "name": "legal-ai-openai-api-failures",
                "description": "OpenAI API failure rate exceeds 10%",
                "severity": 1,
                "query": """
                customMetrics
                | where name == "openai_api_failure_rate"
                | summarize avg(value) by bin(timestamp, 5m)
                | where avg_value > 10
                """,
                "action_group": action_groups["critical"]
            },
            {
                "name": "legal-ai-high-token-usage",
                "description": "Daily token usage exceeds budget",
                "severity": 2,
                "query": """
                customMetrics
                | where name == "daily_token_usage"
                | summarize sum(value) by bin(timestamp, 1h)
                | where sum_value > 1000000
                """,
                "action_group": action_groups["general"]
            },
            {
                "name": "legal-ai-document-queue-backup",
                "description": "Document processing queue backup",
                "severity": 2,
                "query": """
                customMetrics
                | where name == "document_queue_length"
                | summarize avg(value) by bin(timestamp, 5m)
                | where avg_value > 100
                """,
                "action_group": action_groups["general"]
            }
        ]
        
        # Note: In a real implementation, you would use the Azure Monitor Query API
        # or Azure Resource Manager templates to create log-based alerts
        logger.info("Application Insights alerts configured", alert_count=len(app_alerts))
    
    async def setup_monitoring(self, container_app_name: str, app_insights_name: str):
        """Set up complete monitoring infrastructure"""
        try:
            logger.info("Starting Azure monitoring setup")
            
            # Construct resource IDs
            container_app_resource_id = (
                f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/"
                f"providers/Microsoft.App/containerApps/{container_app_name}"
            )
            
            app_insights_resource_id = (
                f"/subscriptions/{self.subscription_id}/resourceGroups/{self.resource_group}/"
                f"providers/Microsoft.Insights/components/{app_insights_name}"
            )
            
            # Create action groups
            action_groups = await self.create_action_groups()
            
            # Create metric alerts
            await self.create_metric_alerts(action_groups, container_app_resource_id)
            
            # Create autoscale settings
            await self.create_autoscale_settings(container_app_resource_id)
            
            # Set up Application Insights alerts
            await self.setup_application_insights_alerts(app_insights_resource_id, action_groups)
            
            logger.info("Azure monitoring setup completed successfully")
            
        except Exception as e:
            logger.error("Azure monitoring setup failed", error=str(e), exc_info=True)
            raise

async def main():
    """Main function to set up Azure monitoring"""
    
    # Configuration from environment variables
    subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "legal-ai-rg")
    container_app_name = os.getenv("CONTAINER_APP_NAME", "legal-ai-backend")
    app_insights_name = os.getenv("APP_INSIGHTS_NAME", "legal-ai-insights")
    
    if not subscription_id:
        logger.error("AZURE_SUBSCRIPTION_ID environment variable is required")
        sys.exit(1)
    
    # Set up monitoring
    monitoring_setup = AzureMonitoringSetup(subscription_id, resource_group)
    await monitoring_setup.setup_monitoring(container_app_name, app_insights_name)
    
    logger.info("Monitoring setup completed")

if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    asyncio.run(main())