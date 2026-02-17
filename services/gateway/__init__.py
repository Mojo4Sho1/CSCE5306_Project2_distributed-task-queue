"""
Gateway service package.

This package hosts the client-facing gRPC API surface:
- taskqueue.v1.TaskQueuePublicService (implemented by GatewayServicer)

Entry point:
- services.gateway.main:main
"""

from .servicer import GatewayServicer
from .server import run_server

__all__ = [
    "GatewayServicer",
    "run_server",
]
