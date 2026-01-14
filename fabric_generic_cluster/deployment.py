# slice_deployment.py
"""
Core slice deployment functionality.
Handles FABRIC slice creation and resource provisioning.
"""

import logging
from typing import Optional
from datetime import datetime

from fabrictestbed_extensions.fablib.fablib import FablibManager as fablib
from .models import SiteTopology, Node, NIC, DPU, FPGA, GPU, NVMe, PersistentVolume, FacilityPort

logger = logging.getLogger(__name__)


class SliceDeploymentError(Exception):
    """Raised when slice deployment fails."""
    pass


def check_or_generate_unique_slice_name(base_name: str, use_timestamp: bool = False) -> str:
    """
    Ensure the slice name is unique by checking existing slices.
    
    Args:
        base_name: Proposed base name for the slice
        use_timestamp: Whether to append a timestamp for uniqueness
        
    Returns:
        A unique slice name
    """
    fab = fablib()
    try:
        existing_names = [slice.get_name() for slice in fab.get_slices()]
        
        if base_name not in existing_names:
            return base_name
        
        if use_timestamp:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"{base_name}-{timestamp}"
        
        # Use numeric suffix
        i = 1
        new_name = f"{base_name}-{i}"
        while new_name in existing_names:
            i += 1
            new_name = f"{base_name}-{i}"
        return new_name
        
    except Exception as e:
        logger.error(f"Error checking/generating slice name: {e}")
        return base_name


def add_gpus_to_node(fab_node, node: Node) -> None:
    """
    Add GPU components to a FABRIC node.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with GPU configuration
    """
    for gpu_id, gpu in node.pci.gpu.items():
        try:
            fab_node.add_component(name=gpu.name, model=gpu.model)
            logger.debug(f"Added GPU {gpu.name} ({gpu.model}) to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add GPU {gpu.name} to {node.hostname}: {e}")


def add_dpus_to_node(fab_node, node: Node) -> None:
    """
    Add DPU components to a FABRIC node.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with DPU configuration
    """
    for dpu_id, dpu in node.pci.dpu.items():
        try:
            fab_node.add_component(name=dpu.name, model=dpu.model)
            logger.debug(f"Added DPU {dpu.name} ({dpu.model}) to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add DPU {dpu.name} to {node.hostname}: {e}")


def add_fpgas_to_node(fab_node, node: Node) -> None:
    """
    Add FPGA components to a FABRIC node.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with FPGA configuration
    """
    for fpga_id, fpga in node.pci.fpga.items():
        try:
            fab_node.add_component(name=fpga.name, model=fpga.model)
            logger.debug(f"Added FPGA {fpga.name} ({fpga.model}) to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add FPGA {fpga.name} to {node.hostname}: {e}")


def add_nvmes_to_node(fab_node, node: Node) -> None:
    """
    Add NVMe components to a FABRIC node.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with NVMe configuration
    """
    for nvme_id, nvme in node.pci.nvme.items():
        try:
            fab_node.add_component(name=nvme.name, model=nvme.model)
            logger.debug(f"Added NVMe {nvme.name} ({nvme.model}) to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add NVMe {nvme.name} to {node.hostname}: {e}")


def add_nics_to_node(fab_node, node: Node) -> None:
    """
    Add NIC components to a FABRIC node.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with NIC configuration
    """
    for nic_id, nic in node.pci.network.items():
        try:
            fab_node.add_component(name=nic.name, model=nic.model)
            logger.debug(f"Added NIC {nic.name} ({nic.model}) to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add NIC {nic.name} to {node.hostname}: {e}")


def add_persistent_storage_to_node(fab_node, node: Node) -> None:
    """
    Add persistent storage volumes to a FABRIC node.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with storage configuration
    """
    for vol_id, volume in node.persistent_storage.volume.items():
        try:
            fab_node.add_storage(name=volume.name)
            logger.debug(f"Added storage {volume.name} ({volume.size}GB) to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add storage {volume.name} to {node.hostname}: {e}")


def add_postboot_commands_to_node(fab_node, node: Node) -> None:
    """
    Add post-boot commands to a FABRIC node if specified in topology.
    
    Args:
        fab_node: FABRIC node object
        node: Node model with potential postboot commands
    """
    if node.specific.has_postboot_commands():
        try:
            postboot_cmd = node.specific.postboot.strip()
            fab_node.add_post_boot_execute(command=postboot_cmd)
            logger.info(f"Added post-boot command to {node.hostname}")
            logger.debug(f"Post-boot command: {postboot_cmd}")
            print(f"   🔧 Added post-boot commands to {node.hostname}")
        except Exception as e:
            logger.warning(f"Failed to add post-boot command to {node.hostname}: {e}")
            print(f"   ⚠️ Failed to add post-boot command to {node.hostname}: {e}")


def add_facility_ports_to_slice(topology: SiteTopology, slice) -> dict:
    """
    Add facility ports to the slice.
    
    Args:
        topology: Site topology model
        slice: FABRIC slice object
        
    Returns:
        Dictionary mapping facility port names to FABRIC facility port objects
    """
    facility_port_objects = {}
    
    if not topology.has_facility_ports():
        logger.debug("No facility ports defined in topology")
        return facility_port_objects
    
    logger.info("Adding facility ports to slice")
    print("\n🔌 Adding facility ports...\n")
    
    for fp_id, fp in topology.site_topology_facility_ports.facility_ports.items():
        try:
            logger.info(f"Adding facility port: {fp.name} at {fp.site} (VLAN {fp.vlan})")
            print(f"   🔌 {fp.name} @ {fp.site} - VLAN {fp.vlan} → {fp.binding}")
            
            fab_fp = slice.add_facility_port(
                name=fp.name,
                site=fp.site,
                vlan=str(fp.vlan)
            )
            
            facility_port_objects[fp.name] = fab_fp
            logger.info(f"Successfully added facility port: {fp.name}")
            
        except Exception as e:
            logger.error(f"Failed to add facility port {fp.name}: {e}")
            print(f"   ❌ Failed to add facility port {fp.name}: {e}")
            continue
    
    return facility_port_objects


def create_and_bind_networks(topology: SiteTopology, slice, facility_port_objects: dict = None) -> dict:
    """
    Create FABRIC networks and bind node interfaces and facility ports to them.
    Handles NIC, DPU, FPGA interfaces, and facility ports.
    
    Args:
        topology: Site topology model
        slice: FABRIC slice object
        facility_port_objects: Dictionary of facility port objects (optional)
        
    Returns:
        Dictionary mapping network names to FABRIC network objects
    """
    if facility_port_objects is None:
        facility_port_objects = {}
    
    network_objects = {}
    
    # Create networks
    for net_id, network in topology.site_topology_networks.networks.items():
        try:
            # Layer 2 networks
            if network.type in ["L2Bridge", "L2PTP", "L2STS"]:
                net = slice.add_l2network(name=network.name, type=network.type)
                logger.info(f"Created L2 network: {network.name} ({network.type})")
            
            # Layer 3 networks (orchestrator-managed)
            elif network.type in ["IPv4", "IPv6", "IPv4Ext", "IPv6Ext"]:
                net = slice.add_l3network(name=network.name, type=network.type)
                logger.info(f"Created L3 network: {network.name} ({network.type})")
            
            else:
                logger.warning(f"Unsupported network type: {network.type}")
                continue
            
            network_objects[network.name] = net
            
        except Exception as e:
            logger.error(f"Failed to create network {network.name}: {e}")
            continue
    
    # Bind facility port interfaces to networks
    if topology.has_facility_ports():
        logger.info("Binding facility port interfaces to networks")
        
        for fp_id, fp in topology.site_topology_facility_ports.facility_ports.items():
            if fp.name not in facility_port_objects:
                logger.warning(f"Facility port {fp.name} not found in facility_port_objects")
                continue
            
            if fp.binding not in network_objects:
                logger.warning(f"Network '{fp.binding}' not found for facility port {fp.name}")
                continue
            
            try:
                fab_fp = facility_port_objects[fp.name]
                fp_interfaces = fab_fp.get_interfaces()
                
                if fp_interfaces:
                    network_objects[fp.binding].add_interface(fp_interfaces[0])
                    logger.info(f"Connected facility port {fp.name} to network {fp.binding}")
                    print(f"   ✅ Connected facility port {fp.name} to {fp.binding}")
                else:
                    logger.warning(f"No interfaces found for facility port {fp.name}")
                    print(f"   ⚠️ No interfaces found for facility port {fp.name}")
                    
            except Exception as e:
                logger.error(f"Failed to bind facility port {fp.name} to network {fp.binding}: {e}")
                print(f"   ❌ Failed to bind facility port {fp.name}: {e}")
    
    # Bind node NIC interfaces to networks
    for node_id, node in topology.site_topology_nodes.nodes.items():
        try:
            fab_node = slice.get_node(name=node.hostname)
        except Exception as e:
            logger.error(f"Could not retrieve node '{node.hostname}': {e}")
            continue
        
        # Process NICs
        for nic_id, nic in node.pci.network.items():
            try:
                fab_nic = fab_node.get_component(name=nic.name)
                iface_list = fab_nic.get_interfaces()
            except Exception as e:
                logger.error(f"Could not retrieve NIC '{nic.name}' on node '{node.hostname}': {e}")
                continue
            
            for i, (iface_name, iface) in enumerate(nic.interfaces.items()):
                if not iface.binding:
                    continue
                
                if iface.binding not in network_objects:
                    logger.warning(f"Network '{iface.binding}' not found in topology")
                    continue
                
                if i < len(iface_list):
                    network_objects[iface.binding].add_interface(iface_list[i])
                    logger.info(f"Connected {node.hostname}.{nic.name}.{iface_name} to {iface.binding}")
                else:
                    logger.warning(f"Interface index out of range: {node.hostname}.{nic.name}.{iface_name}")
        
        # Process DPUs (same logic as NICs)
        for dpu_id, dpu in node.pci.dpu.items():
            try:
                fab_dpu = fab_node.get_component(name=dpu.name)
                iface_list = fab_dpu.get_interfaces()
            except Exception as e:
                logger.error(f"Could not retrieve DPU '{dpu.name}' on node '{node.hostname}': {e}")
                continue
            
            for i, (iface_name, iface) in enumerate(dpu.interfaces.items()):
                if not iface.binding:
                    continue
                
                if iface.binding not in network_objects:
                    logger.warning(f"Network '{iface.binding}' not found in topology")
                    continue
                
                if i < len(iface_list):
                    network_objects[iface.binding].add_interface(iface_list[i])
                    logger.info(f"Connected {node.hostname}.{dpu.name}.{iface_name} to {iface.binding}")
                else:
                    logger.warning(f"Interface index out of range: {node.hostname}.{dpu.name}.{iface_name}")
        
        # Process FPGAs (same logic as NICs and DPUs)
        for fpga_id, fpga in node.pci.fpga.items():
            try:
                fab_fpga = fab_node.get_component(name=fpga.name)
                iface_list = fab_fpga.get_interfaces()
            except Exception as e:
                logger.error(f"Could not retrieve FPGA '{fpga.name}' on node '{node.hostname}': {e}")
                continue
            
            for i, (iface_name, iface) in enumerate(fpga.interfaces.items()):
                if not iface.binding:
                    continue
                
                if iface.binding not in network_objects:
                    logger.warning(f"Network '{iface.binding}' not found in topology")
                    continue
                
                if i < len(iface_list):
                    network_objects[iface.binding].add_interface(iface_list[i])
                    logger.info(f"Connected {node.hostname}.{fpga.name}.{iface_name} to {iface.binding}")
                else:
                    logger.warning(f"Interface index out of range: {node.hostname}.{fpga.name}.{iface_name}")
    
    return network_objects


def configure_l3_networks(slice, topology: SiteTopology) -> None:
    """
    Configure L3 (IPv4/IPv6) networks after slice submission.
    
    This function:
    1. Gets available IP addresses from the orchestrator-assigned subnet
    2. Assigns IPs to node interfaces (both NIC and DPU interfaces)
    3. For IPv4Ext/IPv6Ext networks, enables public routing
    
    Args:
        slice: FABRIC slice object (must be already submitted)
        topology: Site topology model
        
    Raises:
        SliceDeploymentError: If L3 network configuration fails
    """
    logger.info("Starting L3 network configuration")
    print("\n🌐 Configuring L3 networks (IPv4/IPv6)...\n")
    
    try:
        fab = fablib()
        
        # Track if we need to submit again (for public routing)
        needs_resubmit = False
        
        # Process each network
        for network_model in topology.site_topology_networks.iter_networks():
            # Only process L3 networks (IPv4, IPv4Ext, IPv6, IPv6Ext)
            if network_model.type not in ["IPv4", "IPv4Ext", "IPv6", "IPv6Ext"]:
                continue
            
            network_name = network_model.name
            logger.info(f"Configuring L3 network: {network_name} (type: {network_model.type})")
            print(f"🔧 Configuring network: {network_name} ({network_model.type})")
            
            try:
                # Get the network from the slice
                fabric_network = slice.get_network(name=network_name)
                
                # Get available IPs from orchestrator
                available_ips = fabric_network.get_available_ips()
                logger.info(f"Network {network_name} has {len(available_ips)} available IPs")
                print(f"   📋 Available IPs: {len(available_ips)}")
                
                if not available_ips:
                    logger.warning(f"No available IPs for network {network_name}")
                    print(f"   ⚠️ No available IPs for {network_name}")
                    continue
                
                # Get the subnet for this network
                network_subnet = fabric_network.get_subnet()
                logger.debug(f"Network {network_name} subnet: {network_subnet}")
                
                # Get all nodes connected to this network
                connected_nodes = topology.get_nodes_on_network(network_name)
                
                # Track IPs for external routing
                public_ips_to_route = []
                
                # Configure each node's interface
                for node_model in connected_nodes:
                    try:
                        fab_node = slice.get_node(name=node_model.hostname)
                        fab_iface = fab_node.get_interface(network_name=network_name)
                        
                        # Pop the first available IP
                        if not available_ips:
                            logger.error(f"Ran out of IPs for network {network_name}")
                            print(f"   ❌ No more IPs available for {node_model.hostname}")
                            break
                        
                        node_ip = available_ips.pop(0)
                        
                        # Assign IP to interface
                        fab_iface.ip_addr_add(addr=node_ip, subnet=network_subnet)
                        logger.info(f"Assigned {node_ip} to {node_model.hostname}")
                        print(f"   ✅ {node_model.hostname}: {node_ip}")
                        
                        # Track for public routing if IPv4Ext or IPv6Ext
                        if network_model.type in ["IPv4Ext", "IPv6Ext"]:
                            public_ips_to_route.append(str(node_ip))
                        
                    except Exception as e:
                        logger.error(f"Failed to configure {node_model.hostname} on {network_name}: {e}")
                        print(f"   ❌ Error configuring {node_model.hostname}: {e}")
                        continue
                
                # For IPv4Ext/IPv6Ext, enable public routing
                if network_model.type in ["IPv4Ext", "IPv6Ext"] and public_ips_to_route:
                    logger.info(f"Enabling public routing for {network_name}")
                    print(f"   🌐 Enabling public routing for {len(public_ips_to_route)} IPs...")
                    
                    try:
                        if network_model.type == "IPv4Ext":
                            fabric_network.make_ip_publicly_routable(ipv4=public_ips_to_route)
                        elif network_model.type == "IPv6Ext":
                            fabric_network.make_ip_publicly_routable(ipv6=public_ips_to_route)
                        
                        logger.info(f"Public routing enabled for {network_name}")
                        print(f"   ✅ Public routing enabled")
                        needs_resubmit = True
                    except Exception as e:
                        logger.error(f"Failed to enable public routing for {network_name}: {e}")
                        print(f"   ❌ Failed to enable public routing: {e}")
                
            except Exception as e:
                logger.error(f"Failed to configure network {network_name}: {e}")
                print(f"   ❌ Error configuring network: {e}")
                continue
        
        # Submit changes if any external networks were configured
        if needs_resubmit:
            logger.info("Submitting slice with public routing configuration...")
            print("\n🚀 Submitting public routing configuration...")
            slice.submit()
            print("✅ Public routing configuration submitted")
        
        logger.info("L3 network configuration completed")
        print("\n✅ L3 network configuration completed\n")
        
    except Exception as e:
        error_msg = f"Failed to configure L3 networks: {e}"
        logger.error(error_msg)
        print(f"❌ {error_msg}")
        raise SliceDeploymentError(error_msg) from e


def deploy_topology_to_fabric(
    topology: SiteTopology,
    slice_name: str,
    use_timestamp: bool = False
) -> Optional[object]:
    """
    Create and submit a FABRIC slice from the provided topology.
    
    This function creates the slice infrastructure:
    1. Create nodes with components (NICs, DPUs, GPUs, FPGAs, NVMe)
    2. Apply worker constraints if specified
    3. Add post-boot commands if specified
    4. Add facility ports if defined
    5. Create and bind networks (including facility port connections)
    6. Submit slice
    
    After this, you should call:
    - configure_l3_networks(slice, topology) - for L3 network IP assignment
    - configure_node_interfaces(slice, topology) - for persistent network config
    
    Args:
        topology: Site topology model
        slice_name: Proposed name for the slice
        use_timestamp: If True, ensure uniqueness by timestamping
        
    Returns:
        The created and submitted FABRIC slice, or None on failure
        
    Raises:
        SliceDeploymentError: If deployment fails
    """
    # Generate unique slice name
    unique_slice_name = check_or_generate_unique_slice_name(slice_name, use_timestamp)
    
    try:
        fab = fablib()
        slice = fab.new_slice(name=unique_slice_name)
        logger.info(f"Creating slice: {unique_slice_name}")
        print(f"\n🛠️ Creating slice: {unique_slice_name}\n")
        
        # Add nodes
        for node_id, node in topology.site_topology_nodes.nodes.items():
            logger.info(f"Adding node: {node.hostname}")
            
            # Prepare add_node arguments
            add_node_kwargs = {
                'name': node.hostname,
                'site': node.site,
                'cores': node.capacity.cpu,
                'ram': node.capacity.ram,
                'disk': node.capacity.disk,
                'image': node.capacity.os
            }
            
            # Add worker constraint if specified
            if node.has_worker_constraint():
                add_node_kwargs['host'] = node.worker
                logger.info(f"Node {node.hostname} constrained to worker: {node.worker}")
                print(f"   📍 Placing {node.hostname} on worker: {node.worker}")
            
            # Create the node
            fab_node = slice.add_node(**add_node_kwargs)
            
            # Add components
            add_gpus_to_node(fab_node, node)
            add_dpus_to_node(fab_node, node)
            add_fpgas_to_node(fab_node, node)
            add_nvmes_to_node(fab_node, node)
            add_nics_to_node(fab_node, node)
            add_persistent_storage_to_node(fab_node, node)
            
            # Add post-boot commands if specified
            add_postboot_commands_to_node(fab_node, node)
        
        # Add facility ports if defined
        facility_port_objects = add_facility_ports_to_slice(topology, slice)
        
        # Create and bind networks (handles NICs, DPUs, FPGAs, and facility ports)
        create_and_bind_networks(topology, slice, facility_port_objects)
        
        # Submit slice
        logger.info("Submitting slice to FABRIC...")
        print("\n🚀 Submitting slice...")
        slice.submit()
        
        logger.info(f"Slice '{unique_slice_name}' submitted successfully")
        print(f"✅ Slice '{unique_slice_name}' created successfully")
        print(f"\n💡 Next steps:")
        print(f"   1. Call configure_l3_networks(slice, topology) for L3 IP assignment")
        print(f"   2. Call configure_node_interfaces(slice, topology) for persistent config")
        
        return slice
        
    except Exception as e:
        error_msg = f"Failed to deploy slice: {e}"
        logger.critical(error_msg)
        print(f"❌ {error_msg}")
        raise SliceDeploymentError(error_msg) from e


def get_slice(slice_name: str) -> Optional[object]:
    """
    Retrieve an existing FABRIC slice by name.
    
    Args:
        slice_name: Name of the slice to retrieve
        
    Returns:
        FABRIC slice object, or None if not found
    """
    try:
        fab = fablib()
        logger.info(f"Retrieving slice: {slice_name}")
        print(f"\n🚀 Getting slice object for: '{slice_name}'")
        
        slice = fab.get_slice(name=slice_name)
        print(f"✅ Slice retrieved successfully")
        return slice
        
    except Exception as e:
        logger.error(f"Failed to retrieve slice '{slice_name}': {e}")
        print(f"❌ Exception: {e}")
        return None


def delete_slice(slice_name: str) -> bool:
    """
    Delete a FABRIC slice.
    
    Args:
        slice_name: Name of the slice to delete
        
    Returns:
        True if deletion successful, False otherwise
    """
    try:
        fab = fablib()
        slice = fab.get_slice(name=slice_name)
        
        logger.info(f"Deleting slice: {slice_name}")
        print(f"\n🚀 Deleting slice '{slice_name}'")
        
        slice.delete()
        logger.info(f"Slice '{slice_name}' deleted successfully")
        print(f"✅ Slice '{slice_name}' deleted")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete slice '{slice_name}': {e}")
        print(f"❌ Slice deletion failed: {e}")
        return False


def check_slices() -> None:
    """Display all existing slices."""
    try:
        fab = fablib()
        print(f"\n🚀 Checking existing slices...")
        
        slices = list(fab.get_slices())
        if not slices:
            print("No slices found")
            return
        
        for slice in slices:
            print(f"✅ {slice}")
            
    except Exception as e:
        logger.error(f"Failed to check slices: {e}")
        print(f"❌ Exception: {e}")


def show_config() -> None:
    """Display current Fablib configuration."""
    try:
        fab = fablib()
        print(f"\n🚀 Fablib Configuration:")
        fab.show_config()
        print(f"✅ Configuration displayed")
        
    except Exception as e:
        logger.error(f"Failed to show config: {e}")
        print(f"❌ Exception: {e}")
