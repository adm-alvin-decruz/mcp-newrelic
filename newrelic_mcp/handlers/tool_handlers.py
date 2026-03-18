"""
Tool handlers for New Relic MCP Server.

Handles execution of all New Relic tools using Strategy pattern.
"""

import logging
from typing import Any

from mcp.types import TextContent

from ..client import NewRelicClient
from ..config import NewRelicConfig
from .strategies.alerts import (
    CreateAlertPolicyHandler,
    CreateNotificationChannelHandler,
    CreateNotificationDestinationHandler,
    CreateNRQLConditionHandler,
    CreateWorkflowHandler,
    ListAlertConditionsHandler,
    ListAlertPoliciesHandler,
    ListNotificationChannelsHandler,
    ListNotificationDestinationsHandler,
    ListWorkflowsHandler,
)
from .strategies.dashboard import (
    AddWidgetHandler,
    CreateDashboardHandler,
    DeleteWidgetHandler,
    GetDashboardsHandler,
    GetWidgetsHandler,
    SearchDashboardsHandler,
    UpdateWidgetHandler,
)
from .strategies.entities import (
    AddTagsHandler,
    DeleteTagsHandler,
    EntitySearchHandler,
    GetEntityTagsHandler,
    GetSyntheticResultsHandler,
    ListServiceLevelsHandler,
    ListSyntheticMonitorsHandler,
)
from .strategies.monitoring import (
    AlertViolationsHandler,
    AppErrorsHandler,
    AppPerformanceHandler,
    DeploymentsHandler,
    IncidentsHandler,
    InfrastructureHandler,
    QueryNRQLHandler,
)

logger = logging.getLogger(__name__)


class ToolHandlers:
    """Handles MCP tool operations using Strategy pattern"""

    def __init__(self, client: NewRelicClient, config: NewRelicConfig):
        self.client = client
        self.config = config

        # Initialize strategy handlers
        self._strategies = {
            # Monitoring tools
            "query_nrql": QueryNRQLHandler(client, config),
            "get_app_performance": AppPerformanceHandler(client, config),
            "get_app_errors": AppErrorsHandler(client, config),
            "get_incidents": IncidentsHandler(client, config),
            "get_infrastructure_hosts": InfrastructureHandler(client, config),
            "get_alert_violations": AlertViolationsHandler(client, config),
            "get_deployments": DeploymentsHandler(client, config),
            # Dashboard tools
            "get_dashboards": GetDashboardsHandler(client, config),
            "create_dashboard": CreateDashboardHandler(client, config),
            "add_widget_to_dashboard": AddWidgetHandler(client, config),
            "search_all_dashboards": SearchDashboardsHandler(client, config),
            "get_dashboard_widgets": GetWidgetsHandler(client, config),
            "update_widget": UpdateWidgetHandler(client, config),
            "delete_widget": DeleteWidgetHandler(client, config),
            # Alert tools
            "create_alert_policy": CreateAlertPolicyHandler(client, config),
            "create_nrql_condition": CreateNRQLConditionHandler(client, config),
            "create_notification_destination": CreateNotificationDestinationHandler(client, config),
            "create_notification_channel": CreateNotificationChannelHandler(client, config),
            "create_workflow": CreateWorkflowHandler(client, config),
            "list_alert_policies": ListAlertPoliciesHandler(client, config),
            "list_alert_conditions": ListAlertConditionsHandler(client, config),
            "list_notification_destinations": ListNotificationDestinationsHandler(client, config),
            "list_notification_channels": ListNotificationChannelsHandler(client, config),
            "list_workflows": ListWorkflowsHandler(client, config),
            # Entity tools
            "entity_search": EntitySearchHandler(client, config),
            "get_entity_tags": GetEntityTagsHandler(client, config),
            "add_tags_to_entity": AddTagsHandler(client, config),
            "delete_tags_from_entity": DeleteTagsHandler(client, config),
            "list_service_levels": ListServiceLevelsHandler(client, config),
            "list_synthetic_monitors": ListSyntheticMonitorsHandler(client, config),
            "get_synthetic_results": GetSyntheticResultsHandler(client, config),
        }

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Route tool calls to appropriate strategy handlers"""
        try:
            account_id = arguments.get("account_id", self.config.account_id)
            if not account_id:
                return [
                    TextContent(
                        type="text",
                        text="Error: Account ID not provided. Provide via config file, command line, or account_id parameter.",
                    )
                ]

            # Use strategy pattern for clean delegation
            if name in self._strategies:
                return await self._strategies[name].handle(arguments, account_id)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]
