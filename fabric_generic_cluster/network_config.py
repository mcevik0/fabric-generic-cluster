# slice_network_config.py
"""
Network interface configuration for FABRIC slices.
Handles IP address assignment, routing, NetworkManager configuration, and network testing.
Supports NetworkManager (RHEL/Rocky), netplan (Ubuntu), systemd-networkd (modern Debian),
and traditional /etc/network/interfaces (old Debian).
"""

import logging
from typing import Optional, Dict, List, Tuple
from tabulate import tabulate

from .models import SiteTopology, Node, Interface

logger = logging.getLogger(__name__)


class NetworkConfigError(Exception):
    """Raised when network configuration fails."""
    pass


def detect_network_manager(fab_node) -> str:
    """
    Detect which network management tool is available on the node.
    
    Priority order:
    1. NetworkManager (RHEL/Rocky/Fedora)
    2. netplan (Ubuntu 18.04+)
    3. systemd-networkd (modern Debian 11+, some Ubuntu)
    4. /etc/network/interfaces (old Debian/Ubuntu)
    
    Args:
        fab_node: FABRIC node object
        
    Returns:
        'networkmanager', 'netplan', 'systemd-networkd', or 'interfaces'
    """
    try:
        stdout, _ = fab_node.execute("command -v nmcli")
        if stdout.strip():
            logger.debug("Detected NetworkManager (nmcli)")
            return 'networkmanager'
    except:
        pass
    
    try:
        stdout, _ = fab_node.execute("command -v netplan")
        if stdout.strip():
            logger.debug("Detected netplan")
            return 'netplan'
    except:
        pass
    
    try:
        stdout, _ = fab_node.execute("systemctl is-active systemd-networkd 2>/dev/null || systemctl status systemd-networkd 2>/dev/null")
        if stdout.strip():
            logger.debug("Detected systemd-networkd")
            return 'systemd-networkd'
    except:
        pass
    
    try:
        stdout1, _ = fab_node.execute("test -f /etc/network/interfaces && echo 'exists'")
        stdout2, _ = fab_node.execute("command -v ifup")
        if "exists" in stdout1 and stdout2.strip():
            logger.debug("Using traditional /etc/network/interfaces")
            return 'interfaces'
    except:
        pass
    
    logger.warning("Could not detect network manager, defaulting to systemd-networkd")
    return 'systemd-networkd'


def prefix_to_netmask(prefix_len: int) -> str:
    """
    Convert CIDR prefix length to netmask.
    
    Args:
        prefix_len: Prefix length (e.g., 24)
        
    Returns:
        Netmask string (e.g., '255.255.255.0')
    """
    import ipaddress
    return str(ipaddress.IPv4Network(f'0.0.0.0/{prefix_len}').netmask)


def configure_interface_networkmanager(
    fab_node,
    os_iface: str,
    ipv4_addr: str = None,
    ipv6_addr: str = None,
    routes: List[Tuple[str, str]] = None
) -> bool:
    """
    Configure interface using NetworkManager (nmcli) with routing support.
    
    Args:
        fab_node: FABRIC node object
        os_iface: OS interface name (e.g., 'eth1', 'enp7s0')
        ipv4_addr: IPv4 address with CIDR (e.g., '10.0.1.1/24')
        ipv6_addr: IPv6 address with CIDR (e.g., 'fd00::1/64')
        routes: List of (subnet, gateway) tuples for static routes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        connection_name = f"conn-{os_iface}"
        
        # Delete existing connections for this interface
        fab_node.execute(
            f'sudo nmcli -t -f NAME,DEVICE connection show | '
            f'grep -E "{connection_name}" | cut -d: -f1 | '
            f'while read -r conn; do sudo nmcli connection delete "$conn" 2>/dev/null || true; done'
        )
        
        # Create new connection
        fab_node.execute(
            f'sudo nmcli connection add type ethernet ifname "{os_iface}" '
            f'con-name "{connection_name}" connection.autoconnect yes'
        )
        
        # Configure IPv4
        if ipv4_addr:
            fab_node.execute(
                f'sudo nmcli connection modify "{connection_name}" '
                f'ipv4.addresses {ipv4_addr} ipv4.method manual'
            )
        
        # Configure IPv6
        if ipv6_addr:
            fab_node.execute(
                f'sudo nmcli connection modify "{connection_name}" '
                f'ipv6.addresses {ipv6_addr} ipv6.method manual'
            )
        
        # Add static routes
        if routes:
            for subnet, gateway in routes:
                try:
                    if ':' in subnet:
                        # IPv6 route
                        fab_node.execute(
                            f'sudo nmcli connection modify "{connection_name}" '
                            f'+ipv6.routes "{subnet} {gateway}"'
                        )
                    else:
                        # IPv4 route
                        fab_node.execute(
                            f'sudo nmcli connection modify "{connection_name}" '
                            f'+ipv4.routes "{subnet} {gateway}"'
                        )
                    logger.info(f"NetworkManager: Added route {subnet} via {gateway}")
                except Exception as e:
                    logger.warning(f"Failed to add route {subnet} via {gateway}: {e}")
        
        # Bring up the interface
        fab_node.execute(f'sudo nmcli connection up "{connection_name}"')
        
        logger.info(f"NetworkManager: Configured {os_iface}")
        return True
        
    except Exception as e:
        logger.error(f"NetworkManager configuration failed for {os_iface}: {e}")
        return False


def configure_interface_netplan(
    fab_node,
    os_iface: str,
    ipv4_addr: str = None,
    ipv6_addr: str = None,
    routes: List[Tuple[str, str]] = None
) -> bool:
    """
    Configure interface using netplan (Ubuntu 18.04+) with routing support.
    
    Args:
        fab_node: FABRIC node object
        os_iface: OS interface name
        ipv4_addr: IPv4 address with CIDR
        ipv6_addr: IPv6 address with CIDR
        routes: List of (subnet, gateway) tuples for static routes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create netplan configuration
        netplan_config = f"/etc/netplan/60-fabric-{os_iface}.yaml"
        
        config_content = f"""network:
  version: 2
  renderer: networkd
  ethernets:
    {os_iface}:
      dhcp4: no
      dhcp6: no
"""
        
        if ipv4_addr or ipv6_addr:
            config_content += "      addresses:\n"
            if ipv4_addr:
                config_content += f"        - {ipv4_addr}\n"
            if ipv6_addr:
                config_content += f"        - {ipv6_addr}\n"
        
        # Add static routes
        if routes:
            config_content += "      routes:\n"
            for subnet, gateway in routes:
                config_content += f"        - to: {subnet}\n"
                config_content += f"          via: {gateway}\n"
                logger.info(f"netplan: Adding route {subnet} via {gateway}")
        
        # Write configuration file
        fab_node.execute(f'cat > /tmp/netplan-{os_iface}.yaml << "EOF"\n{config_content}\nEOF')
        fab_node.execute(f'sudo mv /tmp/netplan-{os_iface}.yaml {netplan_config}')
        fab_node.execute(f'sudo chmod 600 {netplan_config}')
        
        # Apply configuration
        fab_node.execute('sudo netplan apply')
        
        logger.info(f"netplan: Configured {os_iface}")
        return True
        
    except Exception as e:
        logger.error(f"netplan configuration failed for {os_iface}: {e}")
        return False


def configure_interface_systemd_networkd(
    fab_node,
    os_iface: str,
    ipv4_addr: str = None,
    ipv6_addr: str = None,
    routes: List[Tuple[str, str]] = None
) -> bool:
    """
    Configure interface using systemd-networkd (modern Debian/Ubuntu) with routing support.
    
    Args:
        fab_node: FABRIC node object
        os_iface: OS interface name
        ipv4_addr: IPv4 address with CIDR
        ipv6_addr: IPv6 address with CIDR
        routes: List of (subnet, gateway) tuples for static routes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Create systemd-networkd configuration directory
        fab_node.execute('sudo mkdir -p /etc/systemd/network')
        
        # Create configuration file
        config_file = f"/etc/systemd/network/10-fabric-{os_iface}.network"
        
        config_content = f"""[Match]
Name={os_iface}

[Network]
"""
        
        if ipv4_addr:
            config_content += f"Address={ipv4_addr}\n"
        
        if ipv6_addr:
            config_content += f"Address={ipv6_addr}\n"
        
        # Add static routes
        if routes:
            for subnet, gateway in routes:
                config_content += f"\n[Route]\nDestination={subnet}\nGateway={gateway}\n"
                logger.info(f"systemd-networkd: Adding route {subnet} via {gateway}")
        
        # Write configuration file
        fab_node.execute(f'cat > /tmp/networkd-{os_iface}.network << "EOF"\n{config_content}\nEOF')
        fab_node.execute(f'sudo mv /tmp/networkd-{os_iface}.network {config_file}')
        fab_node.execute(f'sudo chmod 644 {config_file}')
        
        # Ensure systemd-networkd is enabled and restart it
        fab_node.execute('sudo systemctl enable systemd-networkd 2>/dev/null || true')
        fab_node.execute('sudo systemctl restart systemd-networkd')
        
        # Give it a moment to apply
        fab_node.execute('sleep 2')
        
        logger.info(f"systemd-networkd: Configured {os_iface}")
        return True
        
    except Exception as e:
        logger.error(f"systemd-networkd configuration failed for {os_iface}: {e}")
        return False


def configure_interface_traditional(
    fab_node,
    os_iface: str,
    ipv4_addr: str = None,
    ipv6_addr: str = None,
    routes: List[Tuple[str, str]] = None
) -> bool:
    """
    Configure interface using traditional /etc/network/interfaces (old Debian/Ubuntu) with routing support.
    
    Args:
        fab_node: FABRIC node object
        os_iface: OS interface name
        ipv4_addr: IPv4 address with CIDR
        ipv6_addr: IPv6 address with CIDR
        routes: List of (subnet, gateway) tuples for static routes
        
    Returns:
        True if successful, False otherwise
    """
    try:
        interfaces_file = "/etc/network/interfaces"
        
        # Check if file exists
        stdout, _ = fab_node.execute(f'test -f {interfaces_file} && echo "exists"')
        if "exists" not in stdout:
            logger.error(f"{interfaces_file} does not exist")
            print(f"   ⚠️  {interfaces_file} not found, cannot use traditional method")
            return False
        
        # Check if ifup/ifdown are available
        stdout, _ = fab_node.execute('command -v ifup')
        if not stdout.strip():
            logger.error("ifup command not found")
            print(f"   ⚠️  ifup/ifdown commands not available")
            return False
        
        # Backup existing file
        fab_node.execute(f'sudo cp {interfaces_file} {interfaces_file}.bak 2>/dev/null || true')
        
        # Remove existing configuration for this interface
        fab_node.execute(
            f'sudo sed -i "/^# FABRIC configuration for {os_iface}/,/^$/d" {interfaces_file}'
        )
        fab_node.execute(
            f'sudo sed -i "/^auto {os_iface}/d" {interfaces_file}'
        )
        fab_node.execute(
            f'sudo sed -i "/^iface {os_iface}/,/^$/d" {interfaces_file}'
        )
        
        # Build configuration
        config_lines = [f"\n# FABRIC configuration for {os_iface}"]
        config_lines.append(f"auto {os_iface}")
        
        if ipv4_addr:
            # Parse CIDR to get address and netmask
            ip_parts = ipv4_addr.split('/')
            address = ip_parts[0]
            prefix_len = int(ip_parts[1]) if len(ip_parts) > 1 else 24
            
            config_lines.append(f"iface {os_iface} inet static")
            config_lines.append(f"    address {address}")
            config_lines.append(f"    netmask {prefix_to_netmask(prefix_len)}")
            
            # Add IPv4 routes
            if routes:
                for subnet, gateway in routes:
                    if ':' not in subnet:  # IPv4 route
                        config_lines.append(f"    up ip route add {subnet} via {gateway}")
                        config_lines.append(f"    down ip route del {subnet} via {gateway} 2>/dev/null || true")
                        logger.info(f"Traditional: Adding IPv4 route {subnet} via {gateway}")
        else:
            config_lines.append(f"iface {os_iface} inet manual")
        
        if ipv6_addr:
            config_lines.append(f"\niface {os_iface} inet6 static")
            config_lines.append(f"    address {ipv6_addr}")
            
            # Add IPv6 routes
            if routes:
                for subnet, gateway in routes:
                    if ':' in subnet:  # IPv6 route
                        config_lines.append(f"    up ip -6 route add {subnet} via {gateway}")
                        config_lines.append(f"    down ip -6 route del {subnet} via {gateway} 2>/dev/null || true")
                        logger.info(f"Traditional: Adding IPv6 route {subnet} via {gateway}")
        
        # Append to interfaces file
        config_text = '\n'.join(config_lines) + '\n'
        fab_node.execute(f'echo "{config_text}" | sudo tee -a {interfaces_file} > /dev/null')
        
        # Bring up the interface
        fab_node.execute(f'sudo ifdown {os_iface} 2>/dev/null || true')
        fab_node.execute(f'sudo ifup {os_iface}')
        
        logger.info(f"Traditional interfaces: Configured {os_iface}")
        return True
        
    except Exception as e:
        logger.error(f"Traditional interfaces configuration failed for {os_iface}: {e}")
        return False


def collect_node_routes(
    fab_node,
    node: Node,
    topology: SiteTopology,
    slice_obj
) -> List[Tuple[str, str]]:
    """
    Collect all routes that should be configured for a node.
    
    This implements the same routing logic as configure_l3_networks:
    - For each L3 network the node is NOT connected to, add a route via a gateway
      from a network the node IS connected to
    
    Args:
        fab_node: FABRIC node object
        node: Node model from topology
        topology: Site topology model
        slice_obj: FABRIC slice object
        
    Returns:
        List of (subnet, gateway) tuples
    """
    routes = []
    
    try:
        # Find all L3 networks the node is connected to
        connected_networks = []
        network_gateways = {}  # {network_name: (gateway, type)}
        
        for nic_name, iface_name, iface in node.get_all_interfaces():
            if not iface.binding:
                continue
            
            network = topology.get_network_by_name(iface.binding)
            if network and network.is_orchestrator_managed():
                connected_networks.append(iface.binding)
                
                # Get the gateway for this network
                try:
                    fabric_network = slice_obj.get_network(name=iface.binding)
                    gateway = fabric_network.get_gateway()
                    if gateway:
                        network_gateways[iface.binding] = (gateway, network.type)
                except Exception as e:
                    logger.warning(f"Could not get gateway for {iface.binding}: {e}")
        
        # Find all L3 networks in the topology
        all_l3_networks = []
        for network in topology.site_topology_networks.iter_networks():
            if network.is_orchestrator_managed():
                all_l3_networks.append(network.name)
        
        # Find networks this node is NOT connected to
        other_networks = [net for net in all_l3_networks if net not in connected_networks]
        
        # For each remote network, add a route
        for target_network_name in other_networks:
            target_network = topology.get_network_by_name(target_network_name)
            if not target_network:
                continue
            
            try:
                fabric_network = slice_obj.get_network(name=target_network_name)
                target_subnet = fabric_network.get_subnet()
                
                # Determine if target is IPv6
                is_ipv6_target = target_network.type in ["IPv6", "IPv6Ext"]
                
                # Find a suitable gateway from connected networks
                for connected_network, (gateway, network_type) in network_gateways.items():
                    is_ipv6_gateway = network_type in ["IPv6", "IPv6Ext"]
                    
                    # Match IPv4 with IPv4, IPv6 with IPv6
                    if is_ipv6_target == is_ipv6_gateway:
                        routes.append((str(target_subnet), str(gateway)))
                        logger.info(f"Collected route: {target_subnet} via {gateway}")
                        break
            except Exception as e:
                logger.warning(f"Failed to collect route for {target_network_name}: {e}")
                continue
    
    except Exception as e:
        logger.error(f"Error collecting routes for {node.hostname}: {e}")
    
    return routes


def configure_interface_on_node(
    fab_node,
    node: Node,
    network_name: str,
    iface: Interface,
    topology: SiteTopology,
    slice_obj
) -> bool:
    """
    Configure a single network interface on a node.
    
    Supports multiple network management tools:
    - NetworkManager (RHEL/Rocky/Fedora)
    - netplan (Ubuntu 18.04+)
    - systemd-networkd (modern Debian 11+)
    - /etc/network/interfaces (old Debian/Ubuntu)
    
    For L2 networks (L2Bridge, L2PTP, L2STS):
        - Uses IP addresses from the YAML topology configuration
    
    For L3 networks (IPv4, IPv6, IPv4Ext, IPv6Ext):
        - Retrieves actual assigned IPs from the FABRIC interface
        - These IPs were assigned by configure_l3_networks() from orchestrator
        - Configures routing to other L3 networks
    
    Args:
        fab_node: FABRIC node object
        node: Node model from topology
        network_name: Name of the network this interface connects to
        iface: Interface configuration from topology
        topology: Site topology model
        slice_obj: FABRIC slice object
        
    Returns:
        True if configuration successful or skipped, False otherwise
    """
    try:
        # Get network type
        network = topology.get_network_by_name(network_name)
        if not network:
            logger.warning(f"Network '{network_name}' not found in topology")
            print(f"   ⚠️  Network '{network_name}' not found in topology")
            return False
        
        # Get FABRIC interface object
        fab_iface = fab_node.get_interface(network_name=network_name)
        os_iface = fab_iface.get_os_interface()
        
        logger.info(f"Configuring {node.hostname}:{os_iface} for network {network_name}")
        
        # Detect network management tool
        net_manager = detect_network_manager(fab_node)
        logger.info(f"Using {net_manager} for {node.hostname}")
        print(f"🔧 Configuring {os_iface} on {node.hostname} using {net_manager}")
        
        # Determine IP addresses based on network type
        ipv4_addr = None
        ipv6_addr = None
        
        if network.requires_manual_ip_config():
            # L2 networks: Use IPs from YAML configuration
            ipv4_addr = iface.get_ipv4_address()
            ipv6_addr = iface.get_ipv6_address()
            logger.debug(f"Using configured IPs from topology for L2 network {network_name}")
            
        elif network.is_orchestrator_managed():
            # L3 networks: Get actual assigned IPs from FABRIC interface
            try:
                # Get the subnet from the network FIRST
                # This is the authoritative source for the subnet mask
                fabric_network = slice_obj.get_network(name=network_name)
                network_subnet = fabric_network.get_subnet()
                
                logger.debug(f"Network {network_name} subnet from fabric: {network_subnet}")
                print(f"   🔍 Network subnet: {network_subnet}")
                
                # Extract CIDR prefix from network subnet
                subnet_prefix = None
                if network_subnet:
                    subnet_str = str(network_subnet)
                    if '/' in subnet_str:
                        subnet_prefix = subnet_str.split('/')[-1]
                        logger.debug(f"Extracted subnet prefix: /{subnet_prefix}")
                        print(f"   🔍 Subnet prefix: /{subnet_prefix}")
                
                # Default fallback if we can't get subnet
                if not subnet_prefix:
                    subnet_prefix = "64" if network.type in ["IPv6", "IPv6Ext"] else "24"
                    logger.warning(f"Could not determine subnet prefix, defaulting to /{subnet_prefix}")
                    print(f"   ⚠️  Using default prefix: /{subnet_prefix}")
                
                # Get the IP address that was assigned by configure_l3_networks()
                assigned_ip = fab_iface.get_ip_addr()
                
                logger.debug(f"Retrieved IP from interface: {assigned_ip}")
                print(f"   🔍 Retrieved IP from interface: {assigned_ip}")
                
                if assigned_ip:
                    # Strip any CIDR notation from the retrieved IP
                    ip_only = assigned_ip.split('/')[0] if '/' in assigned_ip else assigned_ip
                    
                    # Reconstruct IP with the CORRECT subnet from the network
                    assigned_ip_with_subnet = f"{ip_only}/{subnet_prefix}"
                    
                    logger.info(f"Final IP with correct subnet: {assigned_ip_with_subnet}")
                    print(f"   ✅ Configuring with: {assigned_ip_with_subnet}")
                    
                    # Determine if it's IPv4 or IPv6
                    if ':' in ip_only:
                        ipv6_addr = assigned_ip_with_subnet
                        logger.debug(f"Setting orchestrator-assigned IPv6: {ipv6_addr}")
                    else:
                        ipv4_addr = assigned_ip_with_subnet
                        logger.debug(f"Setting orchestrator-assigned IPv4: {ipv4_addr}")
                else:
                    logger.warning(f"No IP assigned yet for {node.hostname}:{os_iface} on {network_name}")
                    print(f"⚠️  No IP assigned yet for {os_iface} on {node.hostname}")
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to retrieve assigned IP for {node.hostname}:{os_iface}: {e}")
                print(f"❌ Failed to retrieve assigned IP: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Check if there's any IP configuration to apply
        if not ipv4_addr and not ipv6_addr:
            logger.info(f"No IP addresses to configure for {node.hostname}:{os_iface}")
            print(f"ℹ️  No IP configuration for {os_iface} on {node.hostname}")
            return True
        
        if ipv4_addr:
            logger.debug(f"Setting IPv4 {ipv4_addr} on {node.hostname}:{os_iface}")
            print(f"   🔹 IPv4: {ipv4_addr}")
        if ipv6_addr:
            logger.debug(f"Setting IPv6 {ipv6_addr} on {node.hostname}:{os_iface}")
            print(f"   🔹 IPv6: {ipv6_addr}")
        
        # ============================================================
        # NEW SECTION: Collect routes for this node (only for L3 networks)
        # ============================================================
        routes = []
        if network.is_orchestrator_managed():
            routes = collect_node_routes(fab_node, node, topology, slice_obj)
            if routes:
                logger.info(f"Collected {len(routes)} routes for {node.hostname}")
                print(f"   🔀 Adding {len(routes)} inter-network routes")
                for subnet, gateway in routes:
                    print(f"      → {subnet} via {gateway}")
        # ============================================================
        
        # Configure based on detected tool
        success = False
        if net_manager == 'networkmanager':
            success = configure_interface_networkmanager(
                fab_node, os_iface, ipv4_addr, ipv6_addr, routes
            )
        elif net_manager == 'netplan':
            success = configure_interface_netplan(
                fab_node, os_iface, ipv4_addr, ipv6_addr, routes
            )
        elif net_manager == 'systemd-networkd':
            success = configure_interface_systemd_networkd(
                fab_node, os_iface, ipv4_addr, ipv6_addr, routes
            )
        else:  # traditional interfaces
            success = configure_interface_traditional(
                fab_node, os_iface, ipv4_addr, ipv6_addr, routes
            )
        
        if success:
            logger.info(f"Successfully configured {os_iface} on {node.hostname}")
            print(f"✅ Interface {os_iface} configured on {node.hostname}")
        else:
            logger.error(f"Failed to configure {os_iface} on {node.hostname}")
            print(f"❌ Failed to configure {os_iface} on {node.hostname}")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to configure interface on {node.hostname}: {e}")
        print(f"❌ Error configuring interface on {node.hostname}: {e}")
        import traceback
        traceback.print_exc()
        return False


def configure_node_interfaces(slice_obj, topology: SiteTopology) -> None:
    """
    Configure network interfaces for all nodes in the slice.
    
    Handles both L2 and L3 networks:
    - L2 networks: Uses IPs from YAML configuration
    - L3 networks: Retrieves IPs assigned by configure_l3_networks()
    - Adds persistent routing configuration for inter-network connectivity
    
    Args:
        slice_obj: FABRIC slice object
        topology: Site topology model
    """
    logger.info("Starting interface configuration for all nodes")
    print("\n🔧 Configuring interfaces for all nodes...\n")
    
    for node in topology.site_topology_nodes.iter_nodes():
        print(f"\n🔧 Configuring node: {node.hostname}")
        
        try:
            fab_node = slice_obj.get_node(node.hostname)
        except Exception as e:
            logger.error(f"Failed to retrieve node {node.hostname}: {e}")
            print(f"❌ Error retrieving node {node.hostname}: {e}")
            continue
        
        # Configure each interface
        for nic_name, iface_name, iface in node.get_all_interfaces():
            # Get the network binding for this interface
            if not iface.binding:
                continue
            
            configure_interface_on_node(
                fab_node, node, iface.binding, iface, topology, slice_obj
            )
    
    logger.info("Interface configuration completed")
    print("\n✅ Interface configuration completed\n")


def verify_node_interfaces(slice, topology: SiteTopology) -> None:
    """
    Verify and display configured interfaces for all nodes.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
    """
    logger.info("Starting interface verification")
    print("\n🔍 Verifying network interface configuration...\n")
    
    for node in topology.site_topology_nodes.iter_nodes():
        print(f"\n🖥️  Node: {node.hostname}")
        
        try:
            fab_node = slice.get_node(node.hostname)
        except Exception as e:
            logger.error(f"Could not access node '{node.hostname}': {e}")
            print(f"❌ Could not access node: {e}")
            continue
        
        summary_rows = []
        
        # Check each interface
        for nic_name, iface_name, iface in node.get_all_interfaces():
            network_name = iface.binding
            if not network_name:
                continue
            
            try:
                fab_iface = fab_node.get_interface(network_name=network_name)
                os_iface = fab_iface.get_os_interface()
                
                # Check if orchestrator-managed
                network = topology.get_network_by_name(network_name)
                network_type = network.type if network else "Unknown"
                is_orchestrator = network and network.is_orchestrator_managed()
                
                # Show detailed interface info
                print(f"\n🔧 Interface '{os_iface}' (network: {network_name}, type: {network_type}):")
                stdout, stderr = fab_node.execute(f"ip addr show {os_iface}")
                if stdout:
                    print(stdout)
                if stderr:
                    logger.warning(f"stderr from ip addr: {stderr}")
                
                # Collect summary
                if is_orchestrator:
                    # Try to get actual assigned IP
                    try:
                        actual_ip = fab_iface.get_ip_addr()
                        ipv4 = actual_ip if actual_ip and ':' not in actual_ip else "auto"
                        ipv6 = actual_ip if actual_ip and ':' in actual_ip else "auto"
                    except:
                        ipv4 = "auto"
                        ipv6 = "auto"
                else:
                    ipv4 = iface.get_ipv4_address() or "-"
                    ipv6 = iface.get_ipv6_address() or "-"
                
                summary_rows.append([os_iface, network_name, network_type, ipv4, ipv6])
                
            except Exception as e:
                logger.warning(f"Failed to retrieve interface for {network_name}: {e}")
                continue
        
        # Display summary table
        if summary_rows:
            print("\n📋 Interface Summary:")
            print(tabulate(
                summary_rows,
                headers=["OS Interface", "Network", "Type", "IPv4", "IPv6"],
                tablefmt="fancy_grid"
            ))
        else:
            print("⚠️  No configured interfaces found")


def ping_network_from_node(
    slice,
    topology: SiteTopology,
    source_hostname: str,
    network_name: str,
    use_ipv6: bool = False,
    count: int = 3
) -> Dict[str, bool]:
    """
    Test connectivity by pinging all nodes on a network from a source node.
    
    For orchestrator-managed networks (IPv4, IPv6, IPv4Ext, IPv6Ext),
    this will use the actual assigned IPs from the running nodes.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        source_hostname: Hostname of the source node
        network_name: Name of the network to test
        use_ipv6: Whether to use IPv6 instead of IPv4
        count: Number of ping packets to send
        
    Returns:
        Dictionary with results: {target_hostname: success_boolean}
    """
    logger.info(f"Starting ping test from {source_hostname} on {network_name}")
    print(f"\n📡 Ping test from {source_hostname} on network {network_name}")
    
    # Get source node
    source_node_model = topology.get_node_by_hostname(source_hostname)
    if not source_node_model:
        logger.error(f"Source node '{source_hostname}' not found in topology")
        print(f"❌ Source node not found: {source_hostname}")
        return {}
    
    try:
        source_fab_node = slice.get_node(source_hostname)
    except Exception as e:
        logger.error(f"Failed to get source node from slice: {e}")
        print(f"❌ Error retrieving source node: {e}")
        return {}
    
    # Check if network is orchestrator-managed
    network = topology.get_network_by_name(network_name)
    is_orchestrator = network and network.is_orchestrator_managed()
    
    # Find target nodes on the same network
    target_nodes = topology.get_nodes_on_network(network_name)
    results = {}
    
    for target_node in target_nodes:
        if target_node.hostname == source_hostname:
            continue  # Skip self
        
        # For orchestrator-managed networks, get the actual assigned IP
        if is_orchestrator:
            try:
                target_fab_node = slice.get_node(target_node.hostname)
                target_fab_iface = target_fab_node.get_interface(network_name=network_name)
                
                # Get actual IP from the running interface
                target_ip = target_fab_iface.get_ip_addr()
                
                if not target_ip:
                    logger.warning(f"Could not get IP for {target_node.hostname} on {network_name}")
                    continue
                
                # Extract just IP without CIDR if present
                if '/' in target_ip:
                    target_ip = target_ip.split('/')[0]
                    
            except Exception as e:
                logger.error(f"Failed to get IP for {target_node.hostname}: {e}")
                continue
        else:
            # Use configured IP from topology
            interfaces = target_node.get_interfaces_for_network(network_name)
            if not interfaces:
                continue
            
            _, iface = interfaces[0]  # Use first interface on this network
            
            if use_ipv6:
                target_ip = iface.get_ipv6_address(strip_cidr=True)
            else:
                target_ip = iface.get_ipv4_address(strip_cidr=True)
        
        if not target_ip:
            logger.warning(f"No IP address found for {target_node.hostname}")
            continue
        
        # Perform ping
        print(f"\n🔍 Pinging {target_node.hostname} ({target_ip})...")
        try:
            ping_cmd = f"ping6 -c {count}" if use_ipv6 else f"ping -c {count}"
            stdout, stderr = source_fab_node.execute(f"{ping_cmd} {target_ip}")
            success = "0% packet loss" in stdout or "100% packet loss" not in stdout
            results[target_node.hostname] = success
            
            print(stdout)
            if stderr:
                logger.warning(f"stderr: {stderr}")
            
            if success:
                print(f"✅ Ping to {target_node.hostname} successful")
            else:
                print(f"⚠️  Ping to {target_node.hostname} had packet loss")
                
        except Exception as e:
            logger.error(f"Ping to {target_ip} failed: {e}")
            print(f"❌ Ping failed: {e}")
            results[target_node.hostname] = False
    
    # Summary
    print(f"\n📊 Ping Test Summary for {network_name}:")
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"   Successful: {successful}/{total}")
    
    return results


def update_hosts_file_on_nodes(slice, topology: SiteTopology) -> None:
    """
    Update /etc/hosts on each node with hostname-to-IP mappings.
    
    For orchestrator-managed networks, this will use the actual assigned IPs.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
    """
    logger.info("Updating /etc/hosts on all nodes")
    print("\n🛠️  Updating /etc/hosts with hostname mappings...\n")
    
    # Collect all host entries
    host_entries = []
    for node in topology.site_topology_nodes.iter_nodes():
        # Get first IPv4 and IPv6 addresses
        ipv4_address = None
        ipv6_address = None
        
        try:
            fab_node = slice.get_node(node.hostname)
            
            for nic_name, iface_name, iface in node.get_all_interfaces():
                network_name = iface.binding
                if not network_name:
                    continue
                
                network = topology.get_network_by_name(network_name)
                
                # For orchestrator-managed, get actual IP
                if network and network.is_orchestrator_managed():
                    try:
                        fab_iface = fab_node.get_interface(network_name=network_name)
                        actual_ip = fab_iface.get_ip_addr()
                        if actual_ip:
                            # Strip CIDR notation
                            if '/' in actual_ip:
                                actual_ip = actual_ip.split('/')[0]
                            
                            if ':' in actual_ip and not ipv6_address:
                                ipv6_address = actual_ip
                            elif ':' not in actual_ip and not ipv4_address:
                                ipv4_address = actual_ip
                    except Exception as e:
                        logger.warning(f"Could not get IP for {node.hostname}:{network_name}: {e}")
                else:
                    # Use configured IPs
                    if not ipv4_address:
                        addr = iface.get_ipv4_address(strip_cidr=True)
                        if addr:
                            ipv4_address = addr
                    
                    if not ipv6_address:
                        addr = iface.get_ipv6_address(strip_cidr=True)
                        if addr:
                            ipv6_address = addr
            
            # Add entries
            if ipv4_address:
                host_entries.append(f"{ipv4_address} {node.hostname}")
            if ipv6_address:
                host_entries.append(f"{ipv6_address} {node.hostname}")
                
        except Exception as e:
            logger.error(f"Failed to process {node.hostname}: {e}")
            continue
    
    if not host_entries:
        logger.warning("No host entries to add")
        print("⚠️  No host entries found")
        return
    
    hosts_block = "\n".join(host_entries)
    
    # Update each node
    for node_model in topology.site_topology_nodes.iter_nodes():
        try:
            fab_node = slice.get_node(node_model.hostname)
            
            logger.info(f"Updating /etc/hosts on {node_model.hostname}")
            print(f"🔧 Modifying /etc/hosts on {node_model.hostname}")
            
            # Backup existing hosts file
            fab_node.execute("sudo cp /etc/hosts /etc/hosts.bak")
            
            # Append new entries
            fab_node.execute(
                f'echo -e "\\n# FABRIC topology host mappings\\n{hosts_block}" | '
                f'sudo tee -a /etc/hosts > /dev/null'
            )
            
            logger.info(f"Successfully updated /etc/hosts on {node_model.hostname}")
            print(f"✅ /etc/hosts updated on {node_model.hostname}")
            
        except Exception as e:
            logger.error(f"Failed to update /etc/hosts on {node_model.hostname}: {e}")
            print(f"❌ Failed to update /etc/hosts on {node_model.hostname}: {e}")
    
    print("\n✅ /etc/hosts update completed\n")
