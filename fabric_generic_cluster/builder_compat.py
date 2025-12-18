# slice_utils_builder_compat.py
"""
Backward compatibility wrapper for existing code.
Allows old dict-based code to work alongside new model-based code.

Usage:
    # Old code still works:
    import slice_utils_builder_compat as sb
    sb.deploy_topology_to_fabric(site_topology_dict, slice_name)
    
    # Or use new models directly:
    from slice_utils_models import load_topology_from_yaml_file
    from slice_deployment import deploy_topology_to_fabric
    topology = load_topology_from_yaml_file("topology.yaml")
    deploy_topology_to_fabric(topology, slice_name)
"""

import logging
from typing import Union, Dict, Any

from .models import SiteTopology, load_topology_from_dict
from . import deployment
from . import network_config
from . import ssh_setup

logger = logging.getLogger(__name__)


def _ensure_topology_model(topology: Union[Dict, SiteTopology]) -> SiteTopology:
    """
    Convert dict to SiteTopology model if needed.
    
    Args:
        topology: Either dict (old format) or SiteTopology model
        
    Returns:
        SiteTopology model
    """
    if isinstance(topology, dict):
        logger.debug("Converting dict topology to SiteTopology model")
        return load_topology_from_dict(topology)
    return topology


# ============================================================================
# Deployment Functions
# ============================================================================

def deploy_topology_to_fabric(
    site_topology: Union[Dict, SiteTopology],
    slice_name: str,
    use_timestamp: bool = False
):
    """
    Deploy topology to FABRIC. Accepts dict or SiteTopology model.
    
    Args:
        site_topology: Topology definition (dict or SiteTopology)
        slice_name: Name for the slice
        use_timestamp: Whether to use timestamp for uniqueness
        
    Returns:
        FABRIC slice object
    """
    topology = _ensure_topology_model(site_topology)
    return slice_deployment.deploy_topology_to_fabric(
        topology, slice_name, use_timestamp
    )


def get_slice(slice_name: str):
    """Get existing slice by name."""
    return slice_deployment.get_slice(slice_name)


def delete_slice(slice_name: str) -> bool:
    """Delete a slice."""
    return slice_deployment.delete_slice(slice_name)


def check_slices():
    """Display all existing slices."""
    return slice_deployment.check_slices()


def show_config():
    """Display Fablib configuration."""
    return slice_deployment.show_config()


def check_or_generate_unique_slice_name(
    base_name: str,
    use_timestamp: bool = False
) -> str:
    """Generate unique slice name."""
    return slice_deployment.check_or_generate_unique_slice_name(
        base_name, use_timestamp
    )


# ============================================================================
# Network Configuration Functions
# ============================================================================

def configure_node_interfaces(slice, site_topology: Union[Dict, SiteTopology]):
    """
    Configure network interfaces. Accepts dict or SiteTopology model.
    
    Args:
        slice: FABRIC slice object
        site_topology: Topology definition (dict or SiteTopology)
    """
    topology = _ensure_topology_model(site_topology)
    return slice_network_config.configure_node_interfaces(slice, topology)


def verify_node_interfaces(slice, site_topology: Union[Dict, SiteTopology]):
    """
    Verify network interfaces. Accepts dict or SiteTopology model.
    
    Args:
        slice: FABRIC slice object
        site_topology: Topology definition (dict or SiteTopology)
    """
    topology = _ensure_topology_model(site_topology)
    return slice_network_config.verify_node_interfaces(slice, topology)


def ping_network_from_node(
    slice,
    site_topology: Union[Dict, SiteTopology],
    source_hostname: str,
    network_name: str,
    use_ipv6: bool = False,
    count: int = 3
):
    """
    Test network connectivity. Accepts dict or SiteTopology model.
    
    Args:
        slice: FABRIC slice object
        site_topology: Topology definition (dict or SiteTopology)
        source_hostname: Source node for pings
        network_name: Network to test
        use_ipv6: Use IPv6 instead of IPv4
        count: Number of ping packets
        
    Returns:
        Dictionary of results
    """
    topology = _ensure_topology_model(site_topology)
    return slice_network_config.ping_network_from_node(
        slice, topology, source_hostname, network_name, use_ipv6, count
    )


def update_hosts_file_on_nodes(slice, site_topology: Union[Dict, SiteTopology]):
    """
    Update /etc/hosts on all nodes. Accepts dict or SiteTopology model.
    
    Args:
        slice: FABRIC slice object
        site_topology: Topology definition (dict or SiteTopology)
    """
    topology = _ensure_topology_model(site_topology)
    return slice_network_config.update_hosts_file_on_nodes(slice, topology)


# ============================================================================
# SSH Setup Functions
# ============================================================================

def setup_passwordless_ssh(slice) -> bool:
    """Setup passwordless SSH between all nodes."""
    return slice_ssh_setup.setup_passwordless_ssh(slice)


def generate_ssh_keys_on_slice_nodes_safe(
    slice,
    site_topology: Union[Dict, SiteTopology] = None
):
    """
    Generate SSH keys on all nodes (backward compatible name).
    
    Args:
        slice: FABRIC slice object
        site_topology: Unused, kept for compatibility
    """
    return slice_ssh_setup.generate_ssh_keys_on_nodes(slice)


def generate_ssh_keys_if_missing(slice):
    """Generate SSH keys if missing (backward compatible name)."""
    return slice_ssh_setup.generate_ssh_keys_on_nodes(slice)


def setup_ssh_keys_and_distribution(
    slice,
    site_topology: Union[Dict, SiteTopology] = None
):
    """
    Setup SSH keys and distribution (backward compatible).
    
    Args:
        slice: FABRIC slice object
        site_topology: Unused, kept for compatibility
    """
    return slice_ssh_setup.setup_passwordless_ssh(slice)


def distribute_ssh_keys(
    slice,
    site_topology: Union[Dict, SiteTopology] = None
):
    """
    Distribute SSH keys (backward compatible).
    
    Args:
        slice: FABRIC slice object
        site_topology: Unused, kept for compatibility
    """
    public_keys = slice_ssh_setup.collect_public_keys(slice)
    return slice_ssh_setup.distribute_ssh_keys(slice, public_keys)


def disable_strict_host_key_checking(slice):
    """Disable SSH strict host key checking."""
    return slice_ssh_setup.disable_strict_host_key_checking(slice)


def verify_ssh_access(
    slice,
    site_topology: Union[Dict, SiteTopology],
    source_hostname: str,
    network_name: str,
    use_ipv6: bool = False
):
    """
    Verify SSH access. Accepts dict or SiteTopology model.
    
    Args:
        slice: FABRIC slice object
        site_topology: Topology definition (dict or SiteTopology)
        source_hostname: Source node
        network_name: Network to test
        use_ipv6: Use IPv6 instead of IPv4
        
    Returns:
        Dictionary of results
    """
    topology = _ensure_topology_model(site_topology)
    return slice_ssh_setup.verify_ssh_access(
        slice, topology, source_hostname, network_name, use_ipv6
    )


def remove_ssh_keys(slice, remove_entire_ssh_dir: bool = False):
    """Remove SSH keys from all nodes."""
    return slice_ssh_setup.remove_ssh_keys(slice, remove_entire_ssh_dir)


# ============================================================================
# Deprecated/Placeholder Functions
# ============================================================================

def setup_ssh_environment(slice, site_topology: Union[Dict, SiteTopology]):
    """
    Deprecated: Use setup_passwordless_ssh() instead.
    Kept for backward compatibility.
    """
    logger.warning(
        "setup_ssh_environment() is deprecated. "
        "Use setup_passwordless_ssh() instead."
    )
    topology = _ensure_topology_model(site_topology)
    slice_ssh_setup.setup_passwordless_ssh(slice)
    slice_network_config.update_hosts_file_on_nodes(slice, topology)


def initialize_fabric_slice(site_topology: Union[Dict, SiteTopology], slice_name: str):
    """
    Deprecated: Use individual functions instead.
    Full pipeline to create and configure a slice.
    """
    logger.warning(
        "initialize_fabric_slice() is deprecated. "
        "Use individual functions for better control."
    )
    topology = _ensure_topology_model(site_topology)
    
    # Deploy slice
    slice = slice_deployment.deploy_topology_to_fabric(topology, slice_name)
    if not slice:
        return None
    
    # Configure
    slice_ssh_setup.generate_ssh_keys_on_nodes(slice)
    slice_network_config.configure_node_interfaces(slice, topology)
    slice_network_config.update_hosts_file_on_nodes(slice, topology)
    
    return slice


# Export commonly used functions for convenience
__all__ = [
    'deploy_topology_to_fabric',
    'get_slice',
    'delete_slice',
    'check_slices',
    'show_config',
    'check_or_generate_unique_slice_name',
    'configure_node_interfaces',
    'verify_node_interfaces',
    'ping_network_from_node',
    'update_hosts_file_on_nodes',
    'setup_passwordless_ssh',
    'generate_ssh_keys_on_slice_nodes_safe',
    'verify_ssh_access',
    'remove_ssh_keys',
]
