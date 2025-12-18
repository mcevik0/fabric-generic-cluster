#!/usr/bin/env python3
"""
Topology Summary Generator
Generates and injects descriptive comment headers into topology YAML files.
Works with both dict-based and model-based topologies.
Supports DPU interfaces alongside NIC interfaces.
"""

import logging
from pathlib import Path
from typing import Union, Dict
import yaml

from .models import SiteTopology, load_topology_from_dict

logger = logging.getLogger(__name__)


# ============================================================================
# YAML File Handling
# ============================================================================

def load_yaml_file(path: Union[str, Path]) -> tuple[dict, str]:
    """
    Load YAML file and return both parsed data and original text.
    
    Args:
        path: Path to YAML file
        
    Returns:
        Tuple of (parsed_dict, original_text)
    """
    path = Path(path)
    original_text = path.read_text()
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    
    return data, original_text


def save_yaml_with_summary(
    path: Union[str, Path],
    summary: str,
    original_yaml_text: str,
    preserve_existing_comments: bool = False
) -> None:
    """
    Write summary at the top of YAML file as comment block.
    
    Args:
        path: Path to YAML file
        summary: Summary text to prepend
        original_yaml_text: Original YAML content
        preserve_existing_comments: If True, keeps existing top comments
    """
    path = Path(path)
    
    # Remove old auto-generated summary if present
    lines = original_yaml_text.split('\n')
    start_idx = 0
    
    if not preserve_existing_comments:
        # Skip old summary blocks
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                if 'Auto-Generated' in line or 'Topology Summary' in line:
                    # Find the end of this comment block
                    for j in range(i, len(lines)):
                        if lines[j].strip() and not lines[j].strip().startswith('#'):
                            start_idx = j
                            break
                    break
            elif line.strip():  # First non-comment, non-empty line
                break
    
    # Reconstruct YAML
    cleaned_yaml = '\n'.join(lines[start_idx:])
    new_content = summary + "\n" + cleaned_yaml
    
    with open(path, "w") as f:
        f.write(new_content)
    
    logger.info(f"Summary written to {path}")


# ============================================================================
# Summary Generation
# ============================================================================

def fmt(s: str, indent: int = 0) -> str:
    """Format a line with comment prefix and indentation."""
    return "#" + (" " * indent) + s


def generate_node_summary(topology: SiteTopology) -> str:
    """
    Generate detailed node summary section with DPU support.
    
    Args:
        topology: SiteTopology model
        
    Returns:
        Formatted summary string
    """
    lines = []
    
    # Sort nodes alphabetically by name
    sorted_nodes = sorted(
        topology.site_topology_nodes.nodes.items(),
        key=lambda x: x[1].name
    )
    
    for node_key, node in sorted_nodes:
        lines.append(fmt(f"📸 Node: {node.name}"))
        
        # System information
        lines.append(fmt("  ├─ System:", 0))
        lines.append(fmt("      • OS: " + str(node.capacity.os), 0))
        lines.append(fmt(f"      • CPU: {node.capacity.cpu} vCPU", 0))
        lines.append(fmt(f"      • RAM: {node.capacity.ram} GB", 0))
        lines.append(fmt(f"      • Disk: {node.capacity.disk} GB", 0))
        
        # Persistent Storage
        if node.persistent_storage.volume:
            volumes = []
            for vol_id, vol in node.persistent_storage.volume.items():
                volumes.append(f"{vol.name}: {vol.size}GB")
            lines.append(fmt(f"      • Persistent Storage: {{{', '.join(volumes)}}}", 0))
        else:
            lines.append(fmt("      • Persistent Storage: {}", 0))
        
        # GPUs
        if node.pci.gpu:
            lines.append(fmt("  ├─ GPUs:", 0))
            for gpu_id, gpu in node.pci.gpu.items():
                lines.append(fmt(f"    └─ {gpu.name} ({gpu.model})", 0))
        
        # FPGAs with interfaces
        if node.pci.fpga:
            sorted_fpgas = sorted(node.pci.fpga.items(), key=lambda x: x[0])
            
            for fpga_key, fpga in sorted_fpgas:
                lines.append(fmt(f"  ├─ FPGA: {fpga.name} ({fpga.model})", 0))
                
                # Sort interfaces alphabetically
                sorted_ifaces = sorted(fpga.interfaces.items(), key=lambda x: x[0])
                
                for iface_key, iface in sorted_ifaces:
                    ipv4 = iface.get_ipv4_address() or ""
                    ipv6 = iface.get_ipv6_address() or ""
                    
                    iface_line = f"    └─ Interface: {iface_key}, Binding: {iface.binding}, IPv4: {ipv4}"
                    if ipv6:
                        iface_line += f", IPv6: {ipv6}"
                    
                    lines.append(fmt(iface_line, 0))
        
        # NVMe
        if node.pci.nvme:
            lines.append(fmt("  ├─ NVMe Storage:", 0))
            for nvme_id, nvme in node.pci.nvme.items():
                lines.append(fmt(f"    └─ {nvme.name} ({nvme.model})", 0))
        
        # DPUs with interfaces
        if node.pci.dpu:
            sorted_dpus = sorted(node.pci.dpu.items(), key=lambda x: x[0])
            
            for dpu_key, dpu in sorted_dpus:
                lines.append(fmt(f"  ├─ DPU: {dpu.name} ({dpu.model})", 0))
                
                # Sort interfaces alphabetically
                sorted_ifaces = sorted(dpu.interfaces.items(), key=lambda x: x[0])
                
                for iface_key, iface in sorted_ifaces:
                    ipv4 = iface.get_ipv4_address() or ""
                    ipv6 = iface.get_ipv6_address() or ""
                    
                    iface_line = f"    └─ Interface: {iface_key}, Binding: {iface.binding}, IPv4: {ipv4}"
                    if ipv6:
                        iface_line += f", IPv6: {ipv6}"
                    
                    lines.append(fmt(iface_line, 0))
        
        # Network interfaces (NICs) - sorted alphabetically
        sorted_nics = sorted(node.pci.network.items(), key=lambda x: x[0])
        
        for nic_key, nic in sorted_nics:
            lines.append(fmt(f"  ├─ NIC: {nic.name} ({nic.model})", 0))
            
            # Sort interfaces alphabetically
            sorted_ifaces = sorted(nic.interfaces.items(), key=lambda x: x[0])
            
            for iface_key, iface in sorted_ifaces:
                ipv4 = iface.get_ipv4_address() or ""
                ipv6 = iface.get_ipv6_address() or ""
                
                iface_line = f"    └─ Interface: {iface_key}, Binding: {iface.binding}, IPv4: {ipv4}"
                if ipv6:
                    iface_line += f", IPv6: {ipv6}"
                
                lines.append(fmt(iface_line, 0))
        
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
            lines.append(fmt(f"  ├─ OpenStack Roles: {', '.join(active_roles)}", 0))
        
        lines.append("#")
    
    return "\n".join(lines)


def generate_ascii_diagram(topology: SiteTopology) -> str:
    """
    Generate ASCII art network diagram.
    
    Args:
        topology: SiteTopology model
        
    Returns:
        ASCII diagram string
    """
    lines = []
    lines.append("# ASCII Topology Diagram")
    lines.append("#" + "─" * 78)
    
    # Build network-to-nodes mapping
    for network in topology.site_topology_networks.iter_networks():
        lines.append(f"# Network: {network.name}")
        
        connected_nodes = topology.get_nodes_on_network(network.name)
        
        for node in connected_nodes:
            # Get IP for this network (from both NICs and DPUs)
            interfaces = node.get_interfaces_for_network(network.name)
            if interfaces:
                _, iface = interfaces[0]
                ipv4 = iface.get_ipv4_address() or "N/A"
                lines.append(f"#    └── {node.name}  ({ipv4})")
        
        lines.append("#")
    
    return "\n".join(lines)


def generate_network_summary(topology: SiteTopology) -> str:
    """
    Generate network summary section.
    
    Args:
        topology: SiteTopology model
        
    Returns:
        Formatted network summary
    """
    lines = []
    lines.append("#")
    lines.append("# Network Summary")
    lines.append("#" + "─" * 78)
    
    for network in topology.site_topology_networks.iter_networks():
        connected_nodes = topology.get_nodes_on_network(network.name)
        
        lines.append(f"# 📡 {network.name}")
        lines.append(f"#    Type: {network.type}")
        
        # Check if network is orchestrator-managed
        if network.is_orchestrator_managed():
            lines.append(f"#    Subnet: Managed by orchestrator (IPs auto-assigned)")
            lines.append(f"#    Gateway: Managed by orchestrator")
        else:
            # Format subnet information for manually configured networks
            if network.subnet and not network.subnet.is_empty():
                subnet_parts = []
                if network.subnet.ipv4.address:
                    subnet_parts.append(f"IPv4: {network.subnet.ipv4.address}")
                if network.subnet.ipv6.address:
                    subnet_parts.append(f"IPv6: {network.subnet.ipv6.address}")
                
                if subnet_parts:
                    lines.append(f"#    Subnet: {', '.join(subnet_parts)}")
                
                # Format gateway information
                gateway_parts = []
                if network.subnet.ipv4.gateway:
                    gateway_parts.append(f"IPv4: {network.subnet.ipv4.gateway}")
                if network.subnet.ipv6.gateway:
                    gateway_parts.append(f"IPv6: {network.subnet.ipv6.gateway}")
                
                if gateway_parts:
                    lines.append(f"#    Gateway: {', '.join(gateway_parts)}")
            else:
                lines.append(f"#    Subnet: Not configured")
                lines.append(f"#    Gateway: Not configured")
        
        lines.append(f"#    Connected Nodes: {len(connected_nodes)}")
        lines.append("#")
    
    return "\n".join(lines)


def generate_full_summary(topology: SiteTopology, include_ascii: bool = True) -> str:
    """
    Generate complete summary with all sections.
    
    Args:
        topology: SiteTopology model
        include_ascii: Whether to include ASCII diagram
        
    Returns:
        Complete formatted summary
    """
    lines = []
    
    # Header
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
    lines.append(generate_node_summary(topology))
    
    # Network summary
    lines.append(generate_network_summary(topology))
    
    # ASCII diagram
    if include_ascii:
        lines.append(generate_ascii_diagram(topology))
    
    lines.append("#")
    
    # Convert to comment block
    summary = "\n".join(lines)
    return summary + "\n\n"


# ============================================================================
# Main Functions
# ============================================================================

def inject_summary_into_yaml(
    yaml_path: Union[str, Path],
    include_ascii: bool = True,
    preserve_comments: bool = False,
    backup: bool = True
) -> None:
    """
    Inject topology summary into YAML file as comment header.
    
    Args:
        yaml_path: Path to YAML file
        include_ascii: Include ASCII diagram
        preserve_comments: Preserve existing comments
        backup: Create backup file before modifying
    """
    yaml_path = Path(yaml_path)
    
    # Create backup
    if backup:
        backup_path = yaml_path.with_suffix(yaml_path.suffix + '.bak')
        backup_path.write_text(yaml_path.read_text())
        logger.info(f"Backup created: {backup_path}")
    
    # Load topology
    data, original_text = load_yaml_file(yaml_path)
    
    try:
        topology = load_topology_from_dict(data)
    except Exception as e:
        logger.error(f"Failed to parse topology: {e}")
        raise
    
    # Generate summary
    summary = generate_full_summary(topology, include_ascii=include_ascii)
    
    # Save with summary
    save_yaml_with_summary(
        yaml_path,
        summary,
        original_text,
        preserve_existing_comments=preserve_comments
    )
    
    logger.info(f"Summary injected into {yaml_path}")
    print(f"✅ Summary and diagram inserted into {yaml_path}")


def generate_summary_to_file(
    yaml_path: Union[str, Path],
    output_path: Union[str, Path],
    include_ascii: bool = True
) -> None:
    """
    Generate summary and save to separate file (don't modify original).
    
    Args:
        yaml_path: Path to topology YAML file
        output_path: Path to output summary file
        include_ascii: Include ASCII diagram
    """
    data, _ = load_yaml_file(yaml_path)
    topology = load_topology_from_dict(data)
    
    summary = generate_full_summary(topology, include_ascii=include_ascii)
    
    output_path = Path(output_path)
    output_path.write_text(summary)
    
    logger.info(f"Summary written to {output_path}")
    print(f"✅ Summary written to {output_path}")


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """Command-line interface for topology summary generation."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Generate and inject topology summary into YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Inject summary into YAML file (creates backup)
  python tool_topology_summary_generator.py topology.yaml
  
  # Inject without ASCII diagram
  python tool_topology_summary_generator.py topology.yaml --no-ascii
  
  # Generate summary to separate file
  python tool_topology_summary_generator.py topology.yaml --output summary.txt
  
  # No backup
  python tool_topology_summary_generator.py topology.yaml --no-backup
        """
    )
    
    parser.add_argument(
        "yaml_file",
        help="Path to topology YAML file"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Save summary to separate file instead of injecting"
    )
    
    parser.add_argument(
        "--no-ascii",
        action="store_true",
        help="Don't include ASCII diagram"
    )
    
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backup file"
    )
    
    parser.add_argument(
        "--preserve-comments",
        action="store_true",
        help="Preserve existing comments at top of file"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    
    try:
        if args.output:
            # Generate to separate file
            generate_summary_to_file(
                args.yaml_file,
                args.output,
                include_ascii=not args.no_ascii
            )
        else:
            # Inject into YAML
            inject_summary_into_yaml(
                args.yaml_file,
                include_ascii=not args.no_ascii,
                preserve_comments=args.preserve_comments,
                backup=not args.no_backup
            )
    
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
