# slice_utils_models.py
"""
Data models for FABRIC slice topology definitions.
Provides type-safe access to topology data with automatic validation.
"""

from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field, validator
import ipaddress


# ============================================================================
# Network Configuration Models
# ============================================================================

class IPv4Config(BaseModel):
    """IPv4 network configuration for an interface."""
    address: str = ""
    gateway: str = ""
    dns: str = ""
    
    @validator('address')
    def validate_ipv4_address(cls, v):
        """Validate IPv4 address format (CIDR notation) if provided."""
        if v and v.strip():
            try:
                ipaddress.IPv4Interface(v)
            except ValueError as e:
                raise ValueError(f"Invalid IPv4 address: {v} - {e}")
        return v


class IPv6Config(BaseModel):
    """IPv6 network configuration for an interface."""
    address: str = ""
    gateway: str = ""
    dns: str = ""
    
    @validator('address')
    def validate_ipv6_address(cls, v):
        """Validate IPv6 address format (CIDR notation) if provided."""
        if v and v.strip():
            try:
                ipaddress.IPv6Interface(v)
            except ValueError as e:
                raise ValueError(f"Invalid IPv6 address: {v} - {e}")
        return v


class Interface(BaseModel):
    """Network interface configuration."""
    device: str
    connection: str
    binding: str = ""
    ipv4: IPv4Config = Field(default_factory=IPv4Config)
    ipv6: IPv6Config = Field(default_factory=IPv6Config)
    
    def get_ipv4_address(self, strip_cidr: bool = False) -> str:
        """Get IPv4 address, optionally without CIDR suffix."""
        addr = self.ipv4.address
        if strip_cidr and addr:
            return addr.split('/')[0]
        return addr
    
    def get_ipv6_address(self, strip_cidr: bool = False) -> str:
        """Get IPv6 address, optionally without CIDR suffix."""
        addr = self.ipv6.address
        if strip_cidr and addr:
            return addr.split('/')[0]
        return addr
    
    def has_ip_config(self) -> bool:
        """Check if interface has any IP configuration."""
        return bool(self.ipv4.address or self.ipv6.address)


# ============================================================================
# Hardware Component Models
# ============================================================================

class NIC(BaseModel):
    """Network Interface Card configuration."""
    name: str
    model: str
    interfaces: Dict[str, Interface] = Field(default_factory=dict)
    
    def get_interface_by_binding(self, network_name: str) -> Optional[Interface]:
        """Find interface bound to a specific network."""
        for iface in self.interfaces.values():
            if iface.binding == network_name:
                return iface
        return None


class DPU(BaseModel):
    """DPU (Data Processing Unit) component configuration with network interfaces."""
    name: str
    model: str
    interfaces: Dict[str, Interface] = Field(default_factory=dict)
    
    def get_interface_by_binding(self, network_name: str) -> Optional[Interface]:
        """Find interface bound to a specific network."""
        for iface in self.interfaces.values():
            if iface.binding == network_name:
                return iface
        return None


class GPU(BaseModel):
    """GPU component configuration."""
    name: str
    model: str


class NVMe(BaseModel):
    """NVMe storage component configuration."""
    name: str
    model: str


class FPGA(BaseModel):
    """FPGA component configuration with network interfaces."""
    name: str
    model: str
    interfaces: Dict[str, Interface] = Field(default_factory=dict)
    
    def get_interface_by_binding(self, network_name: str) -> Optional[Interface]:
        """Find interface bound to a specific network."""
        for iface in self.interfaces.values():
            if iface.binding == network_name:
                return iface
        return None


class PersistentVolume(BaseModel):
    """Persistent storage volume configuration."""
    name: str
    size: int  # Size in GB


class PCIDevices(BaseModel):
    """PCI device collections for a node."""
    gpu: Dict[str, GPU] = Field(default_factory=dict)
    fpga: Dict[str, FPGA] = Field(default_factory=dict)
    dpu: Dict[str, DPU] = Field(default_factory=dict)
    nvme: Dict[str, NVMe] = Field(default_factory=dict)
    network: Dict[str, NIC] = Field(default_factory=dict)


class PersistentStorage(BaseModel):
    """Persistent storage configuration."""
    volume: Dict[str, PersistentVolume] = Field(default_factory=dict)


# ============================================================================
# Node Configuration Models
# ============================================================================

class NodeCapacity(BaseModel):
    """Node resource capacity specifications."""
    cpu: int = Field(gt=0, description="Number of CPU cores")
    ram: int = Field(gt=0, description="RAM in GB")
    disk: int = Field(gt=0, description="Disk size in GB")
    os: str = Field(description="Operating system image")


class OpenStackRoles(BaseModel):
    """OpenStack role assignments for a node."""
    control: str = "false"
    network: str = "false"
    compute: str = "false"
    storage: str = "false"
    
    @validator('control', 'network', 'compute', 'storage')
    def validate_boolean_string(cls, v):
        """Ensure values are 'true' or 'false' strings."""
        if v not in ["true", "false"]:
            raise ValueError(f"Value must be 'true' or 'false', got: {v}")
        return v
    
    def is_control(self) -> bool:
        return self.control == "true"
    
    def is_network(self) -> bool:
        return self.network == "true"
    
    def is_compute(self) -> bool:
        return self.compute == "true"
    
    def is_storage(self) -> bool:
        return self.storage == "true"


class NodeSpecific(BaseModel):
    """Application-specific node configuration."""
    openstack: OpenStackRoles = Field(default_factory=OpenStackRoles)
    ansible: Optional[Dict[str, str]] = Field(default=None, description="Ansible configuration")
    selinux: Optional[Dict[str, str]] = Field(default=None, description="SELinux configuration")
    postboot: Optional[str] = Field(default=None, description="Post-boot commands to execute")
    
    def has_postboot_commands(self) -> bool:
        """Check if postboot commands are defined and non-empty."""
        return bool(self.postboot and self.postboot.strip())
    
    def is_ansible_control(self) -> bool:
        """Check if this node is designated as an Ansible control node."""
        if not self.ansible:
            return False
        return self.ansible.get('control', 'false').lower() == 'true'
    
    def get_ansible_role(self) -> Optional[str]:
        """Get the Ansible role for this node, if specified."""
        if not self.ansible:
            return None
        return self.ansible.get('role', None)
    
    def get_ansible_roles(self) -> List[str]:
        """
        Get all Ansible roles for this node.
        Supports both single role and comma-separated roles.
        
        Returns:
            List of role names (empty list if no roles defined)
        """
        if not self.ansible:
            return []
        
        role = self.ansible.get('role', None)
        if not role:
            return []
        
        # Support comma-separated roles
        roles = [r.strip() for r in role.split(',') if r.strip()]
        return roles
    
    def get_selinux_mode(self) -> Optional[str]:
        """
        Get the desired SELinux mode for this node.
        
        Returns:
            SELinux mode string ('enforcing', 'permissive', 'disabled') or None
        """
        if not self.selinux:
            return None
        return self.selinux.get('mode', None)
    
    def has_selinux_config(self) -> bool:
        """Check if SELinux configuration is specified."""
        return bool(self.selinux and self.selinux.get('mode'))


class Node(BaseModel):
    """Complete node configuration."""
    name: str
    hostname: str
    site: str
    worker: Optional[str] = Field(default=None, description="Specific worker host for node placement")
    capacity: NodeCapacity
    pci: PCIDevices = Field(default_factory=PCIDevices)
    persistent_storage: PersistentStorage = Field(default_factory=PersistentStorage)
    specific: NodeSpecific = Field(default_factory=NodeSpecific)
    
    def get_nics(self) -> Dict[str, NIC]:
        """Get all NICs for this node."""
        return self.pci.network
    
    def get_dpus(self) -> Dict[str, DPU]:
        """Get all DPUs for this node."""
        return self.pci.dpu
    
    def get_fpgas(self) -> Dict[str, FPGA]:
        """Get all FPGAs for this node."""
        return self.pci.fpga
    
    def get_interfaces_for_network(self, network_name: str) -> list[tuple[str, Interface]]:
        """Get all interfaces bound to a specific network from NICs, DPUs, and FPGAs.
        
        Returns:
            List of (device_name, interface) tuples where device_name is nic_name, dpu_name, or fpga_name
        """
        results = []
        
        # Get interfaces from NICs
        for nic_name, nic in self.pci.network.items():
            for iface_name, iface in nic.interfaces.items():
                if iface.binding == network_name:
                    results.append((nic_name, iface))
        
        # Get interfaces from DPUs
        for dpu_name, dpu in self.pci.dpu.items():
            for iface_name, iface in dpu.interfaces.items():
                if iface.binding == network_name:
                    results.append((dpu_name, iface))
        
        # Get interfaces from FPGAs
        for fpga_name, fpga in self.pci.fpga.items():
            for iface_name, iface in fpga.interfaces.items():
                if iface.binding == network_name:
                    results.append((fpga_name, iface))
        
        return results
    
    def get_all_interfaces(self) -> list[tuple[str, str, Interface]]:
        """Get all interfaces on this node from NICs, DPUs, and FPGAs.
        
        Returns:
            List of (device_name, iface_name, interface) tuples
            where device_name is nic_name, dpu_name, or fpga_name
        """
        results = []
        
        # Get interfaces from NICs
        for nic_name, nic in self.pci.network.items():
            for iface_name, iface in nic.interfaces.items():
                results.append((nic_name, iface_name, iface))
        
        # Get interfaces from DPUs
        for dpu_name, dpu in self.pci.dpu.items():
            for iface_name, iface in dpu.interfaces.items():
                results.append((dpu_name, iface_name, iface))
        
        # Get interfaces from FPGAs
        for fpga_name, fpga in self.pci.fpga.items():
            for iface_name, iface in fpga.interfaces.items():
                results.append((fpga_name, iface_name, iface))
        
        return results
    
    def has_worker_constraint(self) -> bool:
        """Check if this node has a specific worker host constraint."""
        return bool(self.worker and self.worker.strip())


# ============================================================================
# Facility Port Models
# ============================================================================

class FacilityPort(BaseModel):
    """Facility port configuration for external connectivity."""
    name: str = Field(description="Facility port name (e.g., 'SENSE-MGHPCC')")
    site: str = Field(description="FABRIC site where facility port is located")
    vlan: int = Field(description="VLAN ID for the facility port")
    binding: str = Field(description="Network name this facility port connects to")
    
    @validator('vlan')
    def validate_vlan(cls, v):
        """Validate VLAN is in valid range."""
        if not (1 <= v <= 4094):
            raise ValueError(f"VLAN must be between 1 and 4094, got: {v}")
        return v


class SiteTopologyFacilityPorts(BaseModel):
    """Collection of facility ports in the topology."""
    facility_ports: Dict[str, FacilityPort] = Field(default_factory=dict)
    
    def iter_facility_ports(self):
        """Iterate over all facility ports."""
        return self.facility_ports.values()
    
    def get_facility_port_by_name(self, name: str) -> Optional[FacilityPort]:
        """Find facility port by name."""
        for fp in self.facility_ports.values():
            if fp.name == name:
                return fp
        return None
    
    def get_facility_ports_for_network(self, network_name: str) -> list[FacilityPort]:
        """Get all facility ports bound to a specific network."""
        return [fp for fp in self.facility_ports.values() if fp.binding == network_name]


# ============================================================================
# Network Models
# ============================================================================

class SubnetConfig(BaseModel):
    """Subnet configuration with IPv4 and IPv6."""
    ipv4: IPv4Config = Field(default_factory=IPv4Config)
    ipv6: IPv6Config = Field(default_factory=IPv6Config)
    
    def is_empty(self) -> bool:
        """Check if subnet config is completely empty."""
        return (
            not self.ipv4.address and 
            not self.ipv4.gateway and
            not self.ipv6.address and 
            not self.ipv6.gateway
        )


class Network(BaseModel):
    """Network configuration."""
    name: str
    type: str = Field(description="Network type (L2Bridge, L2PTP, L2STS, IPv4, IPv6, IPv4Ext, IPv6Ext)")
    subnet: Optional[SubnetConfig] = Field(default=None, description="Subnet configuration (optional for orchestrator-managed networks)")
    
    # Legacy fields for backward compatibility
    gateway: Optional[str] = Field(default=None, deprecated=True)
    
    @validator('type')
    def validate_network_type(cls, v):
        """Validate network type."""
        valid_types = ["L2Bridge", "L2PTP", "L2STS", "IPv4", "IPv6", "IPv4Ext", "IPv6Ext"]
        if v not in valid_types:
            raise ValueError(f"Network type must be one of {valid_types}, got: {v}")
        return v
    
    def is_orchestrator_managed(self) -> bool:
        """Check if this network type is managed by orchestrator (IPs assigned automatically)."""
        return self.type in ["IPv4", "IPv6", "IPv4Ext", "IPv6Ext"]
    
    def requires_manual_ip_config(self) -> bool:
        """Check if this network type requires manual IP configuration."""
        return self.type in ["L2Bridge", "L2PTP", "L2STS"]
    
    @property
    def ipv4_subnet(self) -> str:
        """Get IPv4 subnet address for backward compatibility."""
        if self.subnet and self.subnet.ipv4.address:
            return self.subnet.ipv4.address
        return ""
    
    @property
    def ipv4_gateway(self) -> str:
        """Get IPv4 gateway for backward compatibility."""
        if self.subnet and self.subnet.ipv4.gateway:
            return self.subnet.ipv4.gateway
        return self.gateway or ""
    
    @property
    def ipv6_subnet(self) -> str:
        """Get IPv6 subnet address."""
        if self.subnet and self.subnet.ipv6.address:
            return self.subnet.ipv6.address
        return ""
    
    @property
    def ipv6_gateway(self) -> str:
        """Get IPv6 gateway."""
        if self.subnet and self.subnet.ipv6.gateway:
            return self.subnet.ipv6.gateway
        return ""


# ============================================================================
# Top-Level Topology Models
# ============================================================================

class SiteTopologyNodes(BaseModel):
    """Collection of nodes in the topology."""
    nodes: Dict[str, Node] = Field(default_factory=dict)
    
    def iter_nodes(self):
        """Iterate over all nodes."""
        return self.nodes.values()
    
    def get_node_by_hostname(self, hostname: str) -> Optional[Node]:
        """Find node by hostname."""
        for node in self.nodes.values():
            if node.hostname == hostname:
                return node
        return None


class SiteTopologyNetworks(BaseModel):
    """Collection of networks in the topology."""
    networks: Dict[str, Network] = Field(default_factory=dict)
    
    def iter_networks(self):
        """Iterate over all networks."""
        return self.networks.values()
    
    def get_network_by_name(self, name: str) -> Optional[Network]:
        """Find network by name."""
        for network in self.networks.values():
            if network.name == name:
                return network
        return None


class SiteTopology(BaseModel):
    """Complete site topology configuration."""
    site_topology_nodes: SiteTopologyNodes
    site_topology_networks: SiteTopologyNetworks
    site_topology_facility_ports: Optional[SiteTopologyFacilityPorts] = Field(
        default_factory=SiteTopologyFacilityPorts,
        description="Facility ports for external connectivity"
    )
    
    @classmethod
    def from_yaml_dict(cls, data: dict) -> "SiteTopology":
        """Create SiteTopology from YAML dictionary."""
        return cls(**data)
    
    def to_dict(self) -> dict:
        """Convert to dictionary (for YAML export)."""
        return self.model_dump()
    
    def get_nodes_on_network(self, network_name: str) -> list[Node]:
        """Get all nodes connected to a specific network."""
        nodes = []
        for node in self.site_topology_nodes.iter_nodes():
            if node.get_interfaces_for_network(network_name):
                nodes.append(node)
        return nodes
    
    def get_node_by_hostname(self, hostname: str) -> Optional[Node]:
        """Find node by hostname."""
        return self.site_topology_nodes.get_node_by_hostname(hostname)
    
    def get_network_by_name(self, name: str) -> Optional[Network]:
        """Find network by name."""
        return self.site_topology_networks.get_network_by_name(name)
    
    def get_facility_ports_for_network(self, network_name: str) -> list[FacilityPort]:
        """Get all facility ports connected to a specific network."""
        if self.site_topology_facility_ports:
            return self.site_topology_facility_ports.get_facility_ports_for_network(network_name)
        return []
    
    def has_facility_ports(self) -> bool:
        """Check if topology has any facility ports defined."""
        return (
            self.site_topology_facility_ports is not None and 
            len(self.site_topology_facility_ports.facility_ports) > 0
        )





# ============================================================================
# Helper Functions for Migration
# ============================================================================

def load_topology_from_dict(data: dict) -> SiteTopology:
    """
    Load and validate topology from a dictionary (e.g., from YAML).
    
    Args:
        data: Dictionary containing topology definition
        
    Returns:
        Validated SiteTopology object
        
    Raises:
        ValidationError: If topology structure is invalid
    """
    return SiteTopology.from_yaml_dict(data)


def load_topology_from_yaml_file(filepath: str) -> SiteTopology:
    """
    Load and validate topology from a YAML file.
    
    Args:
        filepath: Path to YAML file
        
    Returns:
        Validated SiteTopology object
    """
    import yaml
    with open(filepath, 'r') as f:
        data = yaml.safe_load(f)
    return load_topology_from_dict(data)


# ============================================================================
# Network Type Helper Functions
# ============================================================================

def network_requires_manual_config(network_type: str) -> bool:
    """
    Check if a network type requires manual IP configuration.
    
    Args:
        network_type: Network type string
        
    Returns:
        True if manual IP config needed, False if orchestrator-managed
    """
    return network_type in ["L2Bridge", "L2PTP", "L2STS"]


def network_is_orchestrator_managed(network_type: str) -> bool:
    """
    Check if a network type is managed by the orchestrator.
    
    Args:
        network_type: Network type string
        
    Returns:
        True if orchestrator assigns IPs automatically
    """
    return network_type in ["IPv4", "IPv6", "IPv4Ext", "IPv6Ext"]
