# slice_topology_viewer.py
"""
Topology visualization and summary tools.
Supports both new SiteTopology models and legacy dict format.
"""

import logging
from typing import Union, Dict, List, Tuple
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

from .models import SiteTopology, Node, Network

logger = logging.getLogger(__name__)


# ============================================================================
# Type Handling - Support both models and dicts
# ============================================================================

def _ensure_topology_model(topology: Union[Dict, SiteTopology]) -> SiteTopology:
    """Convert dict to SiteTopology model if needed."""
    if isinstance(topology, dict):
        from slice_utils_models import load_topology_from_dict
        return load_topology_from_dict(topology)
    return topology


# ============================================================================
# Text-Based Summary Functions
# ============================================================================

def print_topology_summary(topology: Union[Dict, SiteTopology]) -> None:
    """
    Print a detailed text summary of the topology.
    
    Args:
        topology: SiteTopology model or dict
    """
    topology = _ensure_topology_model(topology)
    
    print("\n" + "="*70)
    print("📷 TOPOLOGY SUMMARY")
    print("="*70)
    
    # Overall statistics
    num_nodes = len(topology.site_topology_nodes.nodes)
    num_networks = len(topology.site_topology_networks.networks)
    
    print(f"\n📊 Overview:")
    print(f"   • Total Nodes: {num_nodes}")
    print(f"   • Total Networks: {num_networks}")
    
    # Network summary
    print(f"\n🌐 Networks:")
    for network in topology.site_topology_networks.iter_networks():
        print(f"   • {network.name}")
        print(f"     └─ Type: {network.type}, Subnet: {network.subnet}")
    
    # Node details
    print(f"\n🖥️ Nodes:")
    for node in topology.site_topology_nodes.iter_nodes():
        _print_node_summary(node, topology)
    
    print("="*70 + "\n")


def _print_node_summary(node: Node, topology: SiteTopology) -> None:
    """Print detailed summary for a single node."""
    print(f"\n   🔸 {node.hostname}")
    print(f"      Site: {node.site}")
    print(f"      Resources: {node.capacity.cpu} vCPU, {node.capacity.ram} GB RAM, {node.capacity.disk} GB Disk")
    print(f"      OS: {node.capacity.os}")
    
    # OpenStack roles (if defined)
    roles = node.specific.openstack
    active_roles = []
    if roles.is_control():
        active_roles.append("control")
    if roles.is_network():
        active_roles.append("network")
    if roles.is_compute():
        active_roles.append("compute")
    if roles.is_storage():
        active_roles.append("storage")
    
    if active_roles:
        print(f"      OpenStack Roles: {', '.join(active_roles)}")
    
    # Hardware components
    if node.pci.gpu:
        print(f"      GPUs: {len(node.pci.gpu)}")
        for gpu_id, gpu in node.pci.gpu.items():
            print(f"         └─ {gpu.name} ({gpu.model})")
    
    if node.pci.dpu:
        print(f"      DPUs: {len(node.pci.dpu)}")
        for dpu_id, dpu in node.pci.dpu.items():
            print(f"         └─ {dpu.name} ({dpu.model})")
    
    if node.pci.fpga:
        print(f"      FPGAs: {len(node.pci.fpga)}")
        for fpga_id, fpga in node.pci.fpga.items():
            print(f"         └─ {fpga.name} ({fpga.model})")
    
    if node.pci.nvme:
        print(f"      NVMe: {len(node.pci.nvme)}")
        for nvme_id, nvme in node.pci.nvme.items():
            print(f"         └─ {nvme.name} ({nvme.model})")
    
    if node.persistent_storage.volume:
        print(f"      Persistent Storage: {len(node.persistent_storage.volume)}")
        for vol_id, vol in node.persistent_storage.volume.items():
            print(f"         └─ {vol.name} ({vol.size} GB)")
    
    # Network interfaces
    if node.pci.network:
        print(f"      Network Interfaces:")
        for nic_name, nic in node.pci.network.items():
            print(f"         └─ {nic.name} ({nic.model})")
            for iface_name, iface in nic.interfaces.items():
                ipv4 = iface.get_ipv4_address() or "N/A"
                ipv6 = iface.get_ipv6_address() or ""
                network_info = f"{iface.binding}: {ipv4}"
                if ipv6:
                    network_info += f", {ipv6}"
                print(f"            └─ {iface_name} → {network_info}")


def print_compact_summary(topology: Union[Dict, SiteTopology]) -> None:
    """
    Print a compact, table-style summary of the topology.
    
    Args:
        topology: SiteTopology model or dict
    """
    from tabulate import tabulate
    
    topology = _ensure_topology_model(topology)
    
    print("\n" + "="*70)
    print("📷 COMPACT TOPOLOGY SUMMARY")
    print("="*70 + "\n")
    
    # Nodes table
    node_rows = []
    for node in topology.site_topology_nodes.iter_nodes():
        networks = set()
        for nic_name, iface_name, iface in node.get_all_interfaces():
            if iface.binding:
                networks.add(iface.binding)
        
        node_rows.append([
            node.hostname,
            node.site,
            f"{node.capacity.cpu}c/{node.capacity.ram}G",
            node.capacity.os.replace("default_", ""),
            ", ".join(sorted(networks))
        ])
    
    print("📋 Nodes:")
    print(tabulate(
        node_rows,
        headers=["Hostname", "Site", "Resources", "OS", "Networks"],
        tablefmt="fancy_grid"
    ))
    
    # Networks table
    network_rows = []
    for network in topology.site_topology_networks.iter_networks():
        connected_nodes = topology.get_nodes_on_network(network.name)
        network_rows.append([
            network.name,
            network.type,
            network.subnet,
            len(connected_nodes)
        ])
    
    print("\n📋 Networks:")
    print(tabulate(
        network_rows,
        headers=["Name", "Type", "Subnet", "Connected Nodes"],
        tablefmt="fancy_grid"
    ))
    
    print("\n" + "="*70 + "\n")


def print_network_details(
    topology: Union[Dict, SiteTopology],
    network_name: str
) -> None:
    """
    Print detailed information about a specific network.
    
    Args:
        topology: SiteTopology model or dict
        network_name: Name of the network to display
    """
    from tabulate import tabulate
    
    topology = _ensure_topology_model(topology)
    
    network = topology.get_network_by_name(network_name)
    if not network:
        print(f"❌ Network '{network_name}' not found")
        return
    
    print(f"\n🌐 Network: {network.name}")
    print(f"   Type: {network.type}")
    print(f"   Subnet: {network.subnet}")
    
    # Print gateway information properly
    gateway_parts = []
    if network.ipv4_gateway:
        gateway_parts.append(f"IPv4: {network.ipv4_gateway}")
    if network.ipv6_gateway:
        gateway_parts.append(f"IPv6: {network.ipv6_gateway}")
    
    if gateway_parts:
        print(f"   Gateway: {', '.join(gateway_parts)}")
    else:
        print(f"   Gateway: None")
    
    # Get connected nodes
    connected_nodes = topology.get_nodes_on_network(network_name)
    
    if not connected_nodes:
        print("   ⚠️  No nodes connected")
        return
    
    print(f"\n   Connected Nodes ({len(connected_nodes)}):")
    
    rows = []
    for node in connected_nodes:
        interfaces = node.get_interfaces_for_network(network_name)
        for nic_name, iface in interfaces:
            ipv4 = iface.get_ipv4_address() or "-"
            ipv6 = iface.get_ipv6_address() or "-"
            rows.append([node.hostname, nic_name, ipv4, ipv6])
    
    print(tabulate(
        rows,
        headers=["Hostname", "NIC", "IPv4", "IPv6"],
        tablefmt="fancy_grid"
    ))


# ============================================================================
# Graph Visualization Functions
# ============================================================================

def draw_topology_graph(
    topology: Union[Dict, SiteTopology],
    figsize: Tuple[int, int] = (14, 10),
    show_ip: bool = True,
    save_path: str = None
) -> None:
    """
    Draw a network topology graph using NetworkX and Matplotlib.
    
    Args:
        topology: SiteTopology model or dict
        figsize: Figure size (width, height)
        show_ip: Whether to show IP addresses on edges
        save_path: Optional path to save the figure
    """
    topology = _ensure_topology_model(topology)
    
    G = nx.Graph()
    
    # Color schemes
    node_colors = {
        'network': '#87CEEB',  # Sky blue for networks
        'node': '#90EE90',      # Light green for nodes
        'control': '#FFD700',   # Gold for control nodes
        'compute': '#98FB98',   # Pale green for compute
        'storage': '#DDA0DD'    # Plum for storage
    }
    
    # Add network nodes
    network_nodes = []
    for network in topology.site_topology_networks.iter_networks():
        G.add_node(network.name, node_type='network', label=network.name)
        network_nodes.append(network.name)
    
    # Add host nodes and edges
    host_nodes = []
    node_color_map = {}
    
    for node in topology.site_topology_nodes.iter_nodes():
        # Determine node color based on OpenStack role
        if node.specific.openstack.is_control():
            color = node_colors['control']
        elif node.specific.openstack.is_compute():
            color = node_colors['compute']
        elif node.specific.openstack.is_storage():
            color = node_colors['storage']
        else:
            color = node_colors['node']
        
        node_color_map[node.hostname] = color
        G.add_node(node.hostname, node_type='host', label=node.hostname)
        host_nodes.append(node.hostname)
        
        # Add edges to networks
        for nic_name, iface_name, iface in node.get_all_interfaces():
            if iface.binding:
                edge_label = ""
                if show_ip:
                    ipv4 = iface.get_ipv4_address(strip_cidr=True)
                    if ipv4:
                        edge_label = ipv4
                
                G.add_edge(
                    node.hostname,
                    iface.binding,
                    label=edge_label,
                    nic=nic_name
                )
    
    # Create layout
    pos = _create_hierarchical_layout(G, network_nodes, host_nodes)
    
    # Draw
    fig, ax = plt.subplots(figsize=figsize)
    
    # Draw network nodes
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=network_nodes,
        node_color=[node_colors['network']] * len(network_nodes),
        node_shape='s',
        node_size=3000,
        alpha=0.9,
        ax=ax
    )
    
    # Draw host nodes
    host_colors = [node_color_map[node] for node in host_nodes]
    nx.draw_networkx_nodes(
        G, pos,
        nodelist=host_nodes,
        node_color=host_colors,
        node_shape='o',
        node_size=2500,
        alpha=0.9,
        ax=ax
    )
    
    # Draw edges
    nx.draw_networkx_edges(
        G, pos,
        edge_color='gray',
        width=2,
        alpha=0.6,
        ax=ax
    )
    
    # Draw labels
    nx.draw_networkx_labels(
        G, pos,
        font_size=10,
        font_weight='bold',
        ax=ax
    )
    
    # Draw edge labels (IP addresses)
    if show_ip:
        edge_labels = nx.get_edge_attributes(G, 'label')
        # Filter out empty labels
        edge_labels = {k: v for k, v in edge_labels.items() if v}
        nx.draw_networkx_edge_labels(
            G, pos,
            edge_labels,
            font_size=8,
            ax=ax
        )
    
    # Add legend
    legend_elements = [
        plt.Line2D([0], [0], marker='s', color='w', 
                   markerfacecolor=node_colors['network'], markersize=10, label='Network'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=node_colors['control'], markersize=10, label='Control Node'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=node_colors['compute'], markersize=10, label='Compute Node'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=node_colors['storage'], markersize=10, label='Storage Node'),
        plt.Line2D([0], [0], marker='o', color='w',
                   markerfacecolor=node_colors['node'], markersize=10, label='Other Node'),
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=10)
    
    plt.title("FABRIC Topology Visualization", fontsize=16, fontweight='bold', pad=20)
    plt.axis('off')
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        logger.info(f"Topology graph saved to {save_path}")
        print(f"💾 Graph saved to {save_path}")
    
    plt.show()


def _create_hierarchical_layout(
    G: nx.Graph,
    network_nodes: List[str],
    host_nodes: List[str]
) -> Dict[str, Tuple[float, float]]:
    """
    Create a hierarchical layout with networks on top and hosts below.
    
    Args:
        G: NetworkX graph
        network_nodes: List of network node names
        host_nodes: List of host node names
        
    Returns:
        Dictionary mapping node names to (x, y) positions
    """
    pos = {}
    
    # Position networks at the top
    network_spacing = 2.0
    network_y = 2.0
    for i, net in enumerate(network_nodes):
        x = i * network_spacing - (len(network_nodes) - 1) * network_spacing / 2
        pos[net] = (x, network_y)
    
    # Position hosts below, grouped by connected networks
    host_y = 0.0
    host_spacing = 1.5
    
    # Group hosts by their primary network (first connection)
    network_hosts = {net: [] for net in network_nodes}
    ungrouped_hosts = []
    
    for host in host_nodes:
        neighbors = list(G.neighbors(host))
        if neighbors:
            # Assign to first network neighbor
            network_hosts[neighbors[0]].append(host)
        else:
            ungrouped_hosts.append(host)
    
    # Position hosts under their networks
    for i, net in enumerate(network_nodes):
        hosts = network_hosts[net]
        net_x = pos[net][0]
        
        for j, host in enumerate(hosts):
            offset = (j - len(hosts) / 2 + 0.5) * host_spacing / 2
            pos[host] = (net_x + offset, host_y)
    
    # Position ungrouped hosts
    for i, host in enumerate(ungrouped_hosts):
        pos[host] = (i * host_spacing, host_y - 1.0)
    
    return pos


def draw_simple_topology(topology: Union[Dict, SiteTopology]) -> None:
    """
    Draw a simple topology graph (backward compatible with old function).
    
    Args:
        topology: SiteTopology model or dict
    """
    draw_topology_graph(topology, figsize=(10, 6), show_ip=False)


# ============================================================================
# ASCII Art Visualization
# ============================================================================

def print_ascii_topology(topology: Union[Dict, SiteTopology]) -> None:
    """
    Print an ASCII art representation of the topology.
    
    Args:
        topology: SiteTopology model or dict
    """
    topology = _ensure_topology_model(topology)
    
    print("\n" + "="*70)
    print("📷 ASCII TOPOLOGY DIAGRAM")
    print("="*70 + "\n")
    
    for network in topology.site_topology_networks.iter_networks():
        print(f"📡 Network: {network.name} ({network.subnet})")
        
        connected_nodes = topology.get_nodes_on_network(network.name)
        
        for i, node in enumerate(connected_nodes):
            is_last = (i == len(connected_nodes) - 1)
            prefix = "   └──" if is_last else "   ├──"
            
            # Get IP for this network
            interfaces = node.get_interfaces_for_network(network.name)
            ip = "N/A"
            if interfaces:
                _, iface = interfaces[0]
                ip = iface.get_ipv4_address() or "N/A"
            
            print(f"{prefix} {node.hostname} ({ip})")
        
        print()
    
    print("="*70 + "\n")


# ============================================================================
# Summary Generation for YAML Files
# ============================================================================

def validate_fpga(fpga):
    """Validate FPGA component structure."""
    if "name" not in fpga or "model" not in fpga:
        return False, "Missing FPGA name or model"
    return True, "FPGA is valid"


# ============================================================================
# Summary Generation for YAML Files
# ============================================================================

def generate_yaml_summary(
    topology: Union[Dict, SiteTopology],
    include_ascii: bool = True
) -> str:
    """
    Generate a formatted summary suitable for YAML file headers.
    
    Args:
        topology: SiteTopology model or dict
        include_ascii: Whether to include ASCII diagram
        
    Returns:
        Formatted summary as comment block
    """
    topology = _ensure_topology_model(topology)
    
    lines = []
    lines.append("# Topology Summary (Auto-Generated)")
    lines.append("#" + "─" * 78)
    lines.append("#")
    
    # Statistics
    num_nodes = len(topology.site_topology_nodes.nodes)
    num_networks = len(topology.site_topology_networks.networks)
    
    lines.append(f"# Total Nodes: {num_nodes}")
    lines.append(f"# Total Networks: {num_networks}")
    lines.append("#" + "─" * 78)
    lines.append("#")
    
    # Node details
    for node in sorted(topology.site_topology_nodes.iter_nodes(), key=lambda n: n.name):
        lines.append(f"#🔸 Node: {node.name}")
        lines.append(f"#   Site: {node.site} | Resources: {node.capacity.cpu}c/{node.capacity.ram}G/{node.capacity.disk}G")
        lines.append(f"#   OS: {node.capacity.os}")
        
        # Network interfaces
        for nic_name, iface_name, iface in node.get_all_interfaces():
            if iface.binding:
                ipv4 = iface.get_ipv4_address() or "N/A"
                lines.append(f"#   └─ {nic_name}.{iface_name} → {iface.binding} ({ipv4})")
        lines.append("#")
    
    # ASCII diagram
    if include_ascii:
        lines.append("# ASCII Topology Diagram")
        lines.append("#" + "─" * 78)
        
        for network in topology.site_topology_networks.iter_networks():
            lines.append(f"# Network: {network.name}")
            connected_nodes = topology.get_nodes_on_network(network.name)
            
            for node in connected_nodes:
                interfaces = node.get_interfaces_for_network(network.name)
                if interfaces:
                    _, iface = interfaces[0]
                    ipv4 = iface.get_ipv4_address() or "N/A"
                    lines.append(f"#    └── {node.name}  ({ipv4})")
            lines.append("#")
    
    return "\n".join(lines) + "\n\n"


def inject_summary_into_yaml_file(
    yaml_path: str,
    topology: Union[Dict, SiteTopology] = None,
    include_ascii: bool = True,
    backup: bool = True
) -> None:
    """
    Inject topology summary into a YAML file as comment header.
    
    Args:
        yaml_path: Path to YAML file
        topology: Optional topology (will load from file if not provided)
        include_ascii: Include ASCII diagram
        backup: Create backup before modifying
    """
    from pathlib import Path
    import yaml
    
    yaml_path = Path(yaml_path)
    
    # Create backup
    if backup:
        backup_path = yaml_path.with_suffix(yaml_path.suffix + '.bak')
        backup_path.write_text(yaml_path.read_text())
        logger.info(f"Backup created: {backup_path}")
    
    # Load topology if not provided
    if topology is None:
        with open(yaml_path, 'r') as f:
            topology = yaml.safe_load(f)
    
    topology = _ensure_topology_model(topology)
    
    # Read original YAML
    original_text = yaml_path.read_text()
    
    # Remove old auto-generated summary if present
    lines = original_text.split('\n')
    start_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('#') and 'Auto-Generated' in line:
            # Find end of comment block
            for j in range(i, len(lines)):
                if lines[j].strip() and not lines[j].strip().startswith('#'):
                    start_idx = j
                    break
            break
        elif line.strip() and not line.strip().startswith('#'):
            break
    
    # Generate new summary
    summary = generate_yaml_summary(topology, include_ascii=include_ascii)
    
    # Write updated file
    cleaned_yaml = '\n'.join(lines[start_idx:])
    new_content = summary + cleaned_yaml
    
    yaml_path.write_text(new_content)
    
    logger.info(f"Summary injected into {yaml_path}")
    print(f"✅ Summary injected into {yaml_path}")


# ============================================================================
# Export Functions
# ============================================================================

def export_topology_to_json(
    topology: Union[Dict, SiteTopology],
    output_path: str
) -> None:
    """
    Export topology to JSON file.
    
    Args:
        topology: SiteTopology model or dict
        output_path: Path to save JSON file
    """
    import json
    
    topology = _ensure_topology_model(topology)
    
    with open(output_path, 'w') as f:
        json.dump(topology.to_dict(), f, indent=2)
    
    logger.info(f"Topology exported to {output_path}")
    print(f"💾 Topology exported to {output_path}")


def export_topology_to_dot(
    topology: Union[Dict, SiteTopology],
    output_path: str
) -> None:
    """
    Export topology to Graphviz DOT format.
    
    Args:
        topology: SiteTopology model or dict
        output_path: Path to save DOT file
    """
    topology = _ensure_topology_model(topology)
    
    G = nx.Graph()
    
    # Add nodes and edges
    for network in topology.site_topology_networks.iter_networks():
        G.add_node(network.name, shape='box', style='filled', fillcolor='lightblue')
    
    for node in topology.site_topology_nodes.iter_nodes():
        G.add_node(node.hostname, shape='ellipse', style='filled', fillcolor='lightgreen')
        
        for nic_name, iface_name, iface in node.get_all_interfaces():
            if iface.binding:
                G.add_edge(node.hostname, iface.binding)
    
    # Write DOT file
    nx.drawing.nx_pydot.write_dot(G, output_path)
    
    logger.info(f"Topology exported to DOT format: {output_path}")
    print(f"💾 Topology exported to {output_path}")
    print(f"   You can visualize it with: dot -Tpng {output_path} -o topology.png")
