"""
Job service package.

This package hosts the internal Job service API surface:
- taskqueue.internal.v1.JobInternalService (implemented by JobServicer)
"""

from .servicer import JobServicer

__all__ = [
    "JobServicer",
]
