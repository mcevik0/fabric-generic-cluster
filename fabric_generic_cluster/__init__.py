"""
FABRIC Generic Cluster Framework

A comprehensive, type-safe Python framework for managing FABRIC testbed
generic clusters and slices with support for DPUs, FPGAs, and advanced networking.
"""

__version__ = "1.0.12"
__author__ = "Mert Cevik"
__email__ = "mcevik@renci.org"

# Import main classes and functions for convenient access
from .models import (
    SiteTopology,
    Node,
    Network,
    load_topology_from_yaml_file,
    load_topology_from_dict,
)

from .deployment import (
    deploy_topology_to_fabric,
    configure_l3_networks,
    get_slice,
    delete_slice,
    check_slices,
    deploy_and_configure_slice,
)

from .network_config import (
    configure_node_interfaces,
    verify_node_interfaces,
    ping_network_from_node,
    update_hosts_file_on_nodes,
)

from .ssh_setup import (
    setup_passwordless_ssh,
    verify_ssh_access,
)

from .ansible_setup import (
    setup_ansible_environment,
    test_ansible_connectivity,
)

from .selinux_management import (
    SELinuxMode,
    check_selinux_status_all_nodes,
    set_selinux_mode_all_nodes,
    set_selinux_permissive_for_openstack,
    display_selinux_summary,
    configure_selinux_from_topology,
    SELinuxManagementError
)

from .topology_viewer import (
    print_topology_summary,
    print_compact_summary,
    draw_topology_graph,
)

__all__ = [
    # Core models
    'SiteTopology',
    'Node',
    'Network',
    'load_topology_from_yaml_file',
    'load_topology_from_dict',

    # Deployment
    'deploy_topology_to_fabric',
    'configure_l3_networks',
    'get_slice',
    'delete_slice',
    'check_slices',

    # Network configuration
    'configure_node_interfaces',
    'verify_node_interfaces',
    'ping_network_from_node',
    'update_hosts_file_on_nodes',

    # SSH setup
    'setup_passwordless_ssh',
    'verify_ssh_access',

    # Ansible setup
    'setup_ansible_environment',
    'test_ansible_connectivity',

    # Visualization
    'print_topology_summary',
    'print_compact_summary',
    'draw_topology_graph',
]
