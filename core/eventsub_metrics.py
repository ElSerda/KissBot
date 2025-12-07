"""
Compatibility shim for eventsub_metrics.
The actual implementation is in web/core/eventsub_metrics.py
This file maintains backwards compatibility for existing imports.
"""

from web.core.eventsub_metrics import (
    EventSubMetricsCollector,
    SessionMetrics,
    SendMetrics,
    ChannelMetrics,
    DropReasonStats,
    get_eventsub_metrics,
)

__all__ = [
    "EventSubMetricsCollector",
    "SessionMetrics",
    "SendMetrics",
    "ChannelMetrics",
    "DropReasonStats",
    "get_eventsub_metrics",
]
