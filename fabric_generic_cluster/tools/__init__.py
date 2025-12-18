"""
FABRIC Generic Cluster - Tools

Command-line tools for FABRIC cluster management.
"""

from .topology_summary import (
    generate_full_summary,
    inject_summary_into_yaml,
)

__all__ = [
    'generate_full_summary',
    'inject_summary_into_yaml',
]
