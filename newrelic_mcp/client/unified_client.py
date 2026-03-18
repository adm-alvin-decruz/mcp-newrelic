"""
Unified New Relic client combining all functionality.
"""

from .alerts_client import AlertsClient
from .dashboards_client import DashboardsClient
from .entities_client import EntitiesClient
from .monitoring_client import MonitoringClient


class NewRelicClient(MonitoringClient, AlertsClient, DashboardsClient, EntitiesClient):
    """Unified New Relic client combining all functionality"""

    pass
