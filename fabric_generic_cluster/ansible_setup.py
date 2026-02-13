# ansible_setup.py
"""
Ansible setup and configuration for FABRIC slices.
Handles Ansible control node setup, inventory generation, and playbook deployment.
"""

import logging
from typing import Optional, List, Dict
from pathlib import Path

from .models import SiteTopology, Node

logger = logging.getLogger(__name__)


class AnsibleSetupError(Exception):
    """Raised when Ansible setup operations fail."""
    pass


def get_ansible_control_node(topology: SiteTopology) -> Optional[Node]:
    """
    Find the designated Ansible control node in the topology.
    
    Args:
        topology: Site topology model
        
    Returns:
        Node object of the control node, or None if not found
    """
    for node in topology.site_topology_nodes.iter_nodes():
        if node.specific.is_ansible_control():
            return node
    return None


def detect_os_family(fab_node) -> str:
    """
    Detect the operating system family on a node.
    
    Args:
        fab_node: FABRIC node object
        
    Returns:
        'ubuntu', 'debian', 'rhel', or 'unknown'
    """
    try:
        # Check for OS release file
        stdout, _ = fab_node.execute("cat /etc/os-release")
        stdout_lower = stdout.lower()
        
        if 'ubuntu' in stdout_lower:
            return 'ubuntu'
        elif 'debian' in stdout_lower:
            return 'debian'
        elif 'rocky' in stdout_lower or 'rhel' in stdout_lower or 'red hat' in stdout_lower or 'centos' in stdout_lower:
            return 'rhel'
        else:
            logger.warning(f"Unknown OS detected: {stdout}")
            return 'unknown'
    except Exception as e:
        logger.error(f"Failed to detect OS: {e}")
        return 'unknown'


def install_ansible_on_control_node(slice, topology: SiteTopology, python_version: str = "3.11") -> bool:
    """
    Install Ansible in a virtual environment on the control node.
    
    Supports:
    - Ubuntu 20.04, 22.04, 24.04
    - Debian 11 (Bullseye), 12 (Bookworm)
    - Rocky Linux 8, 9 (and RHEL derivatives)
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        python_version: Python version to use (default: 3.11)
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Installing Ansible on control node")
    print("\n🔧 Installing Ansible on control node...\n")
    
    # Find control node
    control_node_model = get_ansible_control_node(topology)
    if not control_node_model:
        logger.error("No Ansible control node found in topology")
        print("❌ No node has ansible.control: 'true' in the topology")
        return False
    
    try:
        fab_node = slice.get_node(control_node_model.name)
        logger.info(f"Control node: {control_node_model.name}")
        print(f"📍 Control node: {control_node_model.name}")
        
        # Detect OS family
        os_family = detect_os_family(fab_node)
        print(f"   🐧 Detected OS: {os_family}")
        
        if os_family == 'unknown':
            print("   ⚠️  Unknown OS detected, attempting Ubuntu/Debian commands...")
            os_family = 'ubuntu'  # Fallback to Ubuntu
        
        # Install based on OS family
        if os_family in ['ubuntu', 'debian']:
            success = _install_ansible_debian_based(fab_node, python_version, os_family)
        elif os_family == 'rhel':
            success = _install_ansible_rhel_based(fab_node, python_version)
        else:
            logger.error(f"Unsupported OS family: {os_family}")
            print(f"❌ Unsupported OS family: {os_family}")
            return False
        
        if not success:
            return False
        
        # Verify installation (common for all OS families)
        print("   ✓ Verifying Ansible installation...")
        stdout, _ = fab_node.execute("~/ansible/venv/bin/ansible --version")
        if "ansible" in stdout.lower():
            logger.info("Ansible installed successfully")
            print(f"   ✅ Ansible installed successfully\n")
            
            # Show version info
            version_lines = stdout.split('\n')[:3]  # First 3 lines
            for line in version_lines:
                if line.strip():
                    print(f"   {line}")
            print()
            
            return True
        else:
            logger.error("Ansible installation verification failed")
            print("   ❌ Ansible installation verification failed")
            return False
        
    except Exception as e:
        logger.error(f"Failed to install Ansible: {e}")
        print(f"❌ Failed to install Ansible: {e}")
        import traceback
        traceback.print_exc()
        return False


def _install_ansible_debian_based(fab_node, python_version: str, os_type: str) -> bool:
    """
    Install Ansible on Debian-based systems (Ubuntu, Debian).
    
    Args:
        fab_node: FABRIC node object
        python_version: Python version to use
        os_type: 'ubuntu' or 'debian'
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print(f"   📦 Installing on {os_type.title()}...")
        
        # Update package manager
        print("   ⏳ Updating package manager (this may take a moment)...")
        fab_node.execute("sudo apt-get update -qq")
        
        # Detect which Python version is actually available
        print(f"   🔍 Checking for Python {python_version}...")
        
        python_cmd = None
        
        # Try requested Python version first
        try:
            stdout, stderr = fab_node.execute(f"which python{python_version}")
            if stdout.strip():
                python_cmd = f"python{python_version}"
                print(f"   ✅ Found python{python_version}")
        except:
            pass
        
        # If not found, try to install it
        if not python_cmd:
            try:
                print(f"   ⏳ Attempting to install python{python_version}...")
                stdout, stderr = fab_node.execute(
                    f"sudo apt-get install -y python{python_version} python{python_version}-venv python{python_version}-dev 2>&1"
                )
                
                # Check if installation succeeded
                stdout_check, _ = fab_node.execute(f"which python{python_version}")
                if stdout_check.strip():
                    python_cmd = f"python{python_version}"
                    print(f"   ✅ Installed python{python_version}")
                else:
                    print(f"   ⚠️  python{python_version} not available in repositories")
            except Exception as e:
                print(f"   ⚠️  Could not install python{python_version}: {e}")
        
        # Fall back to python3 if specific version not available
        if not python_cmd:
            print(f"   ℹ️  Falling back to default python3")
            try:
                stdout, _ = fab_node.execute("python3 --version")
                python_cmd = "python3"
                print(f"   ✅ Using {stdout.strip()}")
            except:
                print("   ❌ No suitable Python found")
                return False
        
        # Install Python venv and dev packages for the detected version
        print(f"   📦 Installing {python_cmd} dependencies...")
        
        if "python3.11" in python_cmd or "python3.10" in python_cmd or "python3.9" in python_cmd:
            # Specific version
            version_num = python_cmd.replace("python", "")
            fab_node.execute(
                f"sudo apt-get install -y {python_cmd}-venv {python_cmd}-dev 2>&1 || "
                f"sudo apt-get install -y python3-venv python3-dev"
            )
        else:
            # Generic python3
            fab_node.execute("sudo apt-get install -y python3-venv python3-dev")
        
        # Install pip and build tools
        print("   📦 Installing build tools...")
        fab_node.execute("sudo apt-get install -y python3-pip build-essential libssl-dev libffi-dev")
        
        # Create ansible directory structure
        print("   📁 Creating Ansible directory structure...")
        fab_node.execute("rm -rf ~/ansible")  # Clean up any failed attempts
        fab_node.execute("mkdir -p ~/ansible/{playbooks,roles,inventory,group_vars,host_vars}")
        
        # Create virtual environment
        print(f"   🔨 Creating Python virtual environment with {python_cmd}...")
        stdout, stderr = fab_node.execute(f"{python_cmd} -m venv ~/ansible/venv")
        
        if stderr and "Error" in stderr:
            print(f"   ⚠️  venv creation had warnings: {stderr[:200]}")
        
        # Verify venv was created
        stdout, _ = fab_node.execute("test -f ~/ansible/venv/bin/activate && echo 'EXISTS'")
        if "EXISTS" not in stdout:
            print("   ❌ Virtual environment was not created successfully")
            return False
        
        print("   ✅ Virtual environment created")
        
        # Install Ansible in venv
        print("   ⚙️  Upgrading pip in virtual environment...")
        stdout, stderr = fab_node.execute("~/ansible/venv/bin/pip install --quiet --upgrade pip setuptools wheel")
        
        print("   ⚙️  Installing Ansible (this may take a few minutes)...")
        stdout, stderr = fab_node.execute("~/ansible/venv/bin/pip install --quiet ansible")
        
        if stderr and ("error" in stderr.lower() or "failed" in stderr.lower()):
            print(f"   ⚠️  Ansible installation had issues: {stderr[:500]}")
            return False
        
        logger.info(f"Ansible installed successfully on {os_type}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to install Ansible on {os_type}: {e}")
        print(f"   ❌ Installation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def _install_ansible_rhel_based(fab_node, python_version: str) -> bool:
    """
    Install Ansible on RHEL-based systems (Rocky Linux, RHEL, CentOS).
    
    Args:
        fab_node: FABRIC node object
        python_version: Python version to use
        
    Returns:
        True if successful, False otherwise
    """
    try:
        print("   📦 Installing on Rocky Linux/RHEL...")
        
        # Determine major version
        stdout, _ = fab_node.execute("cat /etc/os-release | grep VERSION_ID")
        if "9" in stdout:
            rhel_major = 9
        elif "8" in stdout:
            rhel_major = 8
        else:
            rhel_major = 9  # Default to 9
        
        print(f"   🔍 Detected RHEL major version: {rhel_major}")
        
        # Enable EPEL repository (Extra Packages for Enterprise Linux)
        print("   📦 Enabling EPEL repository...")
        if rhel_major == 9:
            fab_node.execute("sudo dnf install -y epel-release")
        else:
            fab_node.execute("sudo yum install -y epel-release")
        
        # Update package manager
        print("   ⏳ Updating package manager...")
        if rhel_major == 9:
            fab_node.execute("sudo dnf update -y -q")
        else:
            fab_node.execute("sudo yum update -y -q")
        
        # Install Python and development tools
        print(f"   🐍 Installing Python and dependencies...")
        
        if rhel_major == 9:
            # Rocky 9 / RHEL 9
            try:
                # Try specific Python version first
                fab_node.execute(f"sudo dnf install -y python{python_version} python{python_version}-devel")
                python_cmd = f"python{python_version}"
            except:
                logger.warning(f"Python {python_version} not available, using python3")
                print(f"   ⚠️  Python {python_version} not available, using python3")
                fab_node.execute("sudo dnf install -y python3 python3-devel")
                python_cmd = "python3"
            
            # Install build tools
            fab_node.execute("sudo dnf install -y gcc openssl-devel libffi-devel")
            
        else:
            # Rocky 8 / RHEL 8
            try:
                fab_node.execute(f"sudo yum install -y python{python_version} python{python_version}-devel")
                python_cmd = f"python{python_version}"
            except:
                logger.warning(f"Python {python_version} not available, using python3")
                print(f"   ⚠️  Python {python_version} not available, using python3")
                fab_node.execute("sudo yum install -y python3 python3-devel")
                python_cmd = "python3"
            
            # Install build tools
            fab_node.execute("sudo yum install -y gcc openssl-devel libffi-devel")
        
        # Ensure pip is installed
        print("   📦 Ensuring pip is available...")
        try:
            fab_node.execute(f"sudo {python_cmd} -m ensurepip --upgrade")
        except:
            # Try alternative method
            if rhel_major == 9:
                fab_node.execute("sudo dnf install -y python3-pip")
            else:
                fab_node.execute("sudo yum install -y python3-pip")
        
        # Create ansible directory structure
        print("   📁 Creating Ansible directory structure...")
        fab_node.execute("mkdir -p ~/ansible/{playbooks,roles,inventory,group_vars,host_vars}")
        
        # Create virtual environment
        print("   🔨 Creating Python virtual environment...")
        fab_node.execute(f"{python_cmd} -m venv ~/ansible/venv")
        
        # Install Ansible in venv
        print("   ⚙️  Installing Ansible (this may take a few minutes)...")
        fab_node.execute("~/ansible/venv/bin/pip install --quiet --upgrade pip setuptools wheel")
        fab_node.execute("~/ansible/venv/bin/pip install --quiet ansible")
        
        logger.info("Ansible installed successfully on RHEL-based system")
        return True
        
    except Exception as e:
        logger.error(f"Failed to install Ansible on RHEL-based system: {e}")
        print(f"   ❌ Installation failed: {e}")
        return False


def get_ansible_user_for_os(os_image: str) -> str:
    """
    Determine the default SSH user based on the OS image name.
    
    Args:
        os_image: OS image string from the topology (e.g., 'default_ubuntu_24')
        
    Returns:
        Username string (e.g., 'ubuntu', 'rocky', 'debian', 'centos')
    """
    os_lower = os_image.lower()
    
    if 'ubuntu' in os_lower:
        return 'ubuntu'
    elif 'rocky' in os_lower or 'rhel' in os_lower:
        return 'rocky'
    elif 'centos' in os_lower:
        return 'centos'
    elif 'debian' in os_lower:
        return 'debian'
    elif 'fedora' in os_lower:
        return 'fedora'
    elif 'alma' in os_lower or 'almalinux' in os_lower:
        return 'almalinux'
    else:
        # Default fallback
        logger.warning(f"Unknown OS image '{os_image}', defaulting to 'ubuntu' user")
        return 'ubuntu'



def generate_ansible_inventory(slice, topology: SiteTopology) -> str:
    """
    Generate an Ansible inventory file based on the topology.
    
    Creates groups based on:
    - All nodes in an 'all_nodes' group
    - OpenStack roles (control, network, compute, storage)
    - OS families (os_ubuntu, os_rocky, os_debian, etc.)
    - Sites (site_MAX, site_RENC, etc.)
    - Custom Ansible roles from topology (role_webserver, role_database, etc.)
    
    Each node gets the appropriate ansible_user based on its OS image.
    Management network can be specified via ansible.management_network in topology.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        String containing the inventory file content
    """
    logger.info("Generating Ansible inventory with enhanced grouping")
    
    inventory_lines = ["# Ansible Inventory - Auto-generated by fabric-generic-cluster"]
    inventory_lines.append(f"# Generated for slice")
    inventory_lines.append(f"# Groups: all_nodes, openstack_*, os_*, site_*, role_*\n")
    
    # Collections for different groupings
    all_nodes = []
    
    # OpenStack role groups
    control_nodes = []
    network_nodes = []
    compute_nodes = []
    storage_nodes = []
    
    # OS-based groups
    os_groups = {}  # {os_name: [node_entries]}
    
    # Site-based groups
    site_groups = {}  # {site_name: [node_entries]}
    
    # Custom Ansible role groups
    role_groups = {}  # {role_name: [node_entries]}
    
    for node in topology.site_topology_nodes.iter_nodes():
        # Get management IP - try specified management network first, then fall back
        management_ip = None
        management_network_used = None
        
        try:
            fab_node = slice.get_node(node.name)
            
            # Check if a specific management network is configured
            mgmt_network_binding = node.get_management_network_binding()
            
            if mgmt_network_binding:
                # Use the specified management network
                logger.info(f"Using specified management network '{mgmt_network_binding}' for {node.name}")
                print(f"   🔍 {node.name}: Using management network '{mgmt_network_binding}'")
                
                try:
                    fab_iface = fab_node.get_interface(network_name=mgmt_network_binding)
                    ip = fab_iface.get_ip_addr()
                    if ip:
                        management_ip = ip.split('/')[0] if '/' in ip else ip
                        management_network_used = mgmt_network_binding
                        logger.debug(f"Got management IP {management_ip} from {mgmt_network_binding}")
                except Exception as e:
                    logger.warning(f"Could not get IP from management network '{mgmt_network_binding}' for {node.name}: {e}")
                    print(f"   ⚠️  Could not get IP from management network '{mgmt_network_binding}': {e}")
            
            # Fall back to first available interface if management network not specified or failed
            if not management_ip:
                logger.debug(f"Falling back to first available interface for {node.name}")
                
                for nic_name, iface_name, iface in node.get_all_interfaces():
                    if iface.binding:
                        try:
                            fab_iface = fab_node.get_interface(network_name=iface.binding)
                            ip = fab_iface.get_ip_addr()
                            if ip:
                                management_ip = ip.split('/')[0] if '/' in ip else ip
                                management_network_used = iface.binding
                                logger.debug(f"Using fallback network '{iface.binding}' for {node.name}")
                                print(f"   ℹ️  {node.name}: Using first available network '{iface.binding}'")
                                break
                        except:
                            continue
                            
        except Exception as e:
            logger.warning(f"Could not get IP for {node.name}: {e}")
            print(f"   ⚠️  Error getting IP for {node.name}: {e}")
        
        if not management_ip:
            logger.warning(f"No IP found for {node.name}, skipping from inventory")
            print(f"   ❌ No IP found for {node.name}, skipping")
            continue
        
        # Determine ansible_user based on OS image
        ansible_user = get_ansible_user_for_os(node.capacity.os)
        
        # Build node entry with ansible_user
        node_entry = f"{node.hostname} ansible_host={management_ip} ansible_user={ansible_user}"
        
        # Add comment showing which network is used (helpful for debugging)
        if management_network_used:
            node_entry += f"  # via {management_network_used}"
        
        # Add to all_nodes
        all_nodes.append(node_entry)
        
        # Add to OpenStack role groups
        if node.specific.openstack.is_control():
            control_nodes.append(node_entry)
        if node.specific.openstack.is_network():
            network_nodes.append(node_entry)
        if node.specific.openstack.is_compute():
            compute_nodes.append(node_entry)
        if node.specific.openstack.is_storage():
            storage_nodes.append(node_entry)
        
        # Add to OS-based groups
        os_type = _extract_os_name(node.capacity.os)
        if os_type not in os_groups:
            os_groups[os_type] = []
        os_groups[os_type].append(node_entry)
        
        # Add to site-based groups
        if node.site:
            site_name = node.site.strip()
            if site_name not in site_groups:
                site_groups[site_name] = []
            site_groups[site_name].append(node_entry)
        
        # Add to custom Ansible role groups
        ansible_roles = node.specific.get_ansible_roles()
        for role_name in ansible_roles:
            if role_name not in role_groups:
                role_groups[role_name] = []
            role_groups[role_name].append(node_entry)
    
    # Build inventory file
    
    # All nodes group
    inventory_lines.append("# ============================================")
    inventory_lines.append("# ALL NODES")
    inventory_lines.append("# ============================================")
    inventory_lines.append("[all_nodes]")
    inventory_lines.extend(all_nodes)
    
    # OpenStack role groups
    if control_nodes or network_nodes or compute_nodes or storage_nodes:
        inventory_lines.append("")
        inventory_lines.append("# ============================================")
        inventory_lines.append("# OPENSTACK ROLES")
        inventory_lines.append("# ============================================")
        
        if control_nodes:
            inventory_lines.append("[openstack_control]")
            inventory_lines.extend(control_nodes)
            inventory_lines.append("")
        
        if network_nodes:
            inventory_lines.append("[openstack_network]")
            inventory_lines.extend(network_nodes)
            inventory_lines.append("")
        
        if compute_nodes:
            inventory_lines.append("[openstack_compute]")
            inventory_lines.extend(compute_nodes)
            inventory_lines.append("")
        
        if storage_nodes:
            inventory_lines.append("[openstack_storage]")
            inventory_lines.extend(storage_nodes)
    
    # OS-based groups
    if os_groups:
        inventory_lines.append("")
        inventory_lines.append("# ============================================")
        inventory_lines.append("# OS-BASED GROUPS")
        inventory_lines.append("# ============================================")
        for os_name in sorted(os_groups.keys()):
            inventory_lines.append(f"[os_{os_name}]")
            inventory_lines.extend(os_groups[os_name])
            inventory_lines.append("")
    
    # Site-based groups
    if site_groups:
        inventory_lines.append("# ============================================")
        inventory_lines.append("# SITE-BASED GROUPS")
        inventory_lines.append("# ============================================")
        for site_name in sorted(site_groups.keys()):
            inventory_lines.append(f"[site_{site_name}]")
            inventory_lines.extend(site_groups[site_name])
            inventory_lines.append("")
    
    # Custom Ansible role groups
    if role_groups:
        inventory_lines.append("# ============================================")
        inventory_lines.append("# CUSTOM ANSIBLE ROLES")
        inventory_lines.append("# ============================================")
        for role_name in sorted(role_groups.keys()):
            inventory_lines.append(f"[role_{role_name}]")
            inventory_lines.extend(role_groups[role_name])
            inventory_lines.append("")
    
    # Add common variables
    inventory_lines.append("# ============================================")
    inventory_lines.append("# GLOBAL VARIABLES")
    inventory_lines.append("# ============================================")
    inventory_lines.append("[all_nodes:vars]")
    inventory_lines.append("ansible_python_interpreter=/usr/bin/python3")
    inventory_lines.append("ansible_ssh_common_args='-o StrictHostKeyChecking=no'")
    
    return "\n".join(inventory_lines)


def _extract_os_name(os_image: str) -> str:
    """
    Extract a clean OS name from the OS image string for grouping.
    
    Args:
        os_image: OS image string (e.g., 'default_ubuntu_24', 'default_rocky_9')
        
    Returns:
        Clean OS name (e.g., 'ubuntu', 'rocky', 'debian')
    """
    os_lower = os_image.lower()
    
    if 'ubuntu' in os_lower:
        return 'ubuntu'
    elif 'rocky' in os_lower:
        return 'rocky'
    elif 'rhel' in os_lower:
        return 'rhel'
    elif 'centos' in os_lower:
        return 'centos'
    elif 'debian' in os_lower:
        return 'debian'
    elif 'fedora' in os_lower:
        return 'fedora'
    elif 'alma' in os_lower:
        return 'almalinux'
    else:
        return 'unknown'


def deploy_ansible_inventory(slice, topology: SiteTopology) -> bool:
    """
    Generate and deploy Ansible inventory to the control node.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Deploying Ansible inventory")
    print("\n📋 Deploying Ansible inventory...\n")
    
    # Find control node
    control_node_model = get_ansible_control_node(topology)
    if not control_node_model:
        logger.error("No Ansible control node found in topology")
        print("❌ No Ansible control node found")
        return False
    
    try:
        fab_node = slice.get_node(control_node_model.name)
        
        # Generate inventory
        inventory_content = generate_ansible_inventory(slice, topology)
        
        # Write inventory to control node
        print(f"   📝 Writing inventory to {control_node_model.name}...")
        
        # Escape content for shell
        escaped_content = inventory_content.replace('"', '\\"').replace('$', '\\$')
        
        fab_node.execute(f'cat > ~/ansible/inventory/hosts << "EOF"\n{inventory_content}\nEOF')
        
        logger.info("Inventory deployed successfully")
        print("   ✅ Inventory deployed to ~/ansible/inventory/hosts")
        
        # Display inventory
        print("\n📋 Inventory contents:")
        print("=" * 70)
        print(inventory_content)
        print("=" * 70)
        
        # Generate host_vars from topology
        if not generate_host_vars_from_topology(fab_node, topology):
            logger.warning("Failed to generate host variables, continuing...")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to deploy inventory: {e}")
        print(f"❌ Failed to deploy inventory: {e}")
        return False




def generate_host_vars_from_topology(fab_node, topology: SiteTopology) -> bool:
    """
    Generate host variable files from topology information on the control node.
    
    Creates detailed host_vars YAML files for each node based on the topology
    model, including hardware specs, ansible roles, network info, etc.
    
    Args:
        fab_node: FABRIC control node object
        topology: Site topology model
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Generating host variables from topology")
    print("\n📝 Generating host variables from topology...\n")
    
    # Create host_vars directory
    fab_node.execute("mkdir -p ~/ansible/host_vars")
    
    generated_count = 0
    
    for node in topology.site_topology_nodes.iter_nodes():
        hostname = node.hostname
        
        # Parse OS information
        os_string = node.capacity.os if node.capacity.os else "unknown"
        os_parts = os_string.replace("default_", "").split("_")
        os_name = os_parts[0].capitalize() if os_parts else "Unknown"
        os_version = os_parts[1] if len(os_parts) > 1 else ""
        
        # Parse ansible roles
        ansible_roles = []
        if node.specific.ansible and hasattr(node.specific.ansible, 'role') and node.specific.ansible.role:
            ansible_roles = [r.strip() for r in node.specific.ansible.role.split(',') if r.strip()]
        
        # Build host_vars content
        host_vars_content = f"""---
# host_vars/{hostname}.yml
# Host-specific variables for {hostname}
# Auto-generated from topology

# Host identification
hostname: "{hostname}"
fqdn: "{hostname}.fabric.net"

# Site information
site_name: "{node.site if node.site else 'Unknown'}"
"""
        
        if node.worker:
            host_vars_content += f'fabric_worker: "{node.worker}"\n'
        
        host_vars_content += f"""
# Hardware specifications (for reference)
cpu_cores: {node.capacity.cpu if node.capacity.cpu else 0}
memory_gb: {node.capacity.ram if node.capacity.ram else 0}
disk_size_gb: {node.capacity.disk if node.capacity.disk else 0}

# Operating System
os_name: "{os_name}"
os_version: "{os_version}"
os_full: "{os_string}"
"""
        
        # Add ansible configuration
        if node.specific.ansible:
            host_vars_content += "\n# Ansible configuration\nansible_config:\n"
            
            if hasattr(node.specific.ansible, 'control') and node.specific.ansible.control:
                is_control = node.specific.ansible.control.lower() == 'true'
                host_vars_content += f"  is_control_node: {str(is_control).lower()}\n"
            
            if hasattr(node.specific.ansible, 'management_network') and node.specific.ansible.management_network:
                host_vars_content += f'  management_network: "{node.specific.ansible.management_network}"\n'
            
            if ansible_roles:
                host_vars_content += "  roles:\n"
                for role in ansible_roles:
                    host_vars_content += f"    - {role}\n"
        
        # Add SELinux configuration
        if node.specific.selinux and hasattr(node.specific.selinux, 'mode') and node.specific.selinux.mode:
            mode = node.specific.selinux.mode.strip()
            if mode:
                host_vars_content += f'\n# SELinux configuration\nselinux_target_state: "{mode}"\n'
        
        # Add OpenStack roles
        if node.specific.openstack:
            openstack_roles = {}
            if hasattr(node.specific.openstack, 'control') and node.specific.openstack.control and node.specific.openstack.control.lower() == 'true':
                openstack_roles['control'] = True
            if hasattr(node.specific.openstack, 'compute') and node.specific.openstack.compute and node.specific.openstack.compute.lower() == 'true':
                openstack_roles['compute'] = True
            if hasattr(node.specific.openstack, 'network') and node.specific.openstack.network and node.specific.openstack.network.lower() == 'true':
                openstack_roles['network'] = True
            if hasattr(node.specific.openstack, 'storage') and node.specific.openstack.storage and node.specific.openstack.storage.lower() == 'true':
                openstack_roles['storage'] = True
            
            if openstack_roles:
                host_vars_content += "\n# OpenStack roles\nopenstack_roles:\n"
                for key, value in openstack_roles.items():
                    host_vars_content += f"  {key}: {str(value).lower()}\n"
        
        # Add network interfaces
        has_interfaces = False
        interfaces_content = ""
        if node.pci and node.pci.network:
            for nic_name, nic in node.pci.network.items():
                if nic.interfaces:
                    for iface_name, iface in nic.interfaces.items():
                        if not has_interfaces:
                            has_interfaces = True
                            interfaces_content = "\n# Network interfaces\nnetwork_interfaces:\n"
                        
                        interfaces_content += f'  - name: "{iface_name}"\n'
                        interfaces_content += f'    device: "{iface.device if iface.device else ""}"\n'
                        interfaces_content += f'    connection: "{iface.connection if iface.connection else ""}"\n'
                        interfaces_content += f'    binding: "{iface.binding if iface.binding else ""}"\n'
        
        if has_interfaces:
            host_vars_content += interfaces_content
        
        # Add monitoring tags
        monitoring_tags = ['fabric-node']
        if ansible_roles:
            monitoring_tags.extend(ansible_roles)
        if node.site:
            monitoring_tags.append(f"site-{node.site.lower()}")
        
        host_vars_content += "\n# Monitoring\nmonitoring_tags:\n"
        for tag in monitoring_tags:
            host_vars_content += f"  - {tag}\n"
        
        # Add backup and maintenance
        host_vars_content += f"""
# Backup configuration
backup_enabled: true
backup_schedule: "0 2 * * *"

# Maintenance
maintenance_window: "Sunday 02:00-04:00"

# Add host-specific overrides below
"""
        
        # Write to control node
        try:
            # Escape content for shell
            escaped_content = host_vars_content.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
            
            fab_node.execute(f'cat > ~/ansible/host_vars/{hostname}.yml << "EOF"\n{host_vars_content}\nEOF')
            
            print(f"   ✓ Generated: {hostname}.yml")
            generated_count += 1
            
        except Exception as e:
            logger.error(f"Failed to write host_vars for {hostname}: {e}")
            print(f"   ✗ Failed: {hostname}.yml - {e}")
            return False
    
    print(f"\n✅ Generated {generated_count} host variable file(s)\n")
    logger.info(f"Generated {generated_count} host variable files")
    
    return True


def create_ansible_config(slice, topology: SiteTopology) -> bool:
    """
    Create ansible.cfg configuration file on the control node.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Creating Ansible configuration")
    print("\n⚙️  Creating Ansible configuration...\n")
    
    control_node_model = get_ansible_control_node(topology)
    if not control_node_model:
        return False
    
    try:
        fab_node = slice.get_node(control_node_model.name)
        
        ansible_cfg = """[defaults]
inventory = ~/ansible/inventory/hosts
roles_path = ~/ansible/roles
host_key_checking = False
retry_files_enabled = False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = ~/ansible/.ansible_cache
fact_caching_timeout = 86400

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False

[ssh_connection]
pipelining = True
ssh_args = -o ControlMaster=auto -o ControlPersist=60s -o StrictHostKeyChecking=no
"""
        
        fab_node.execute(f'cat > ~/ansible/ansible.cfg << "EOF"\n{ansible_cfg}\nEOF')
        
        logger.info("Ansible configuration created")
        print("   ✅ ansible.cfg created")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create Ansible config: {e}")
        print(f"❌ Failed to create Ansible config: {e}")
        return False


def deploy_sample_playbook(slice, topology: SiteTopology) -> bool:
    """
    Deploy a sample playbook template to the control node.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Deploying sample playbook")
    print("\n📝 Deploying sample playbook...\n")
    
    control_node_model = get_ansible_control_node(topology)
    if not control_node_model:
        return False
    
    try:
        fab_node = slice.get_node(control_node_model.name)
        
        sample_playbook = """---
# Sample playbook for FABRIC slice management
- name: Configure all nodes
  hosts: all_nodes
  become: yes
  tasks:
    - name: Update apt cache
      apt:
        update_cache: yes
        cache_valid_time: 3600
      when: ansible_os_family == "Debian"
    
    - name: Install common packages
      apt:
        name:
          - vim
          - htop
          - curl
          - wget
          - net-tools
        state: present
      when: ansible_os_family == "Debian"
    
    - name: Ensure hostname is set correctly
      hostname:
        name: "{{ inventory_hostname }}"
    
    - name: Display node information
      debug:
        msg: "Node {{ inventory_hostname }} at {{ ansible_host }}"

- name: Configure OpenStack control nodes
  hosts: openstack_control
  become: yes
  tasks:
    - name: Display control node info
      debug:
        msg: "This is an OpenStack control node"

- name: Configure OpenStack compute nodes
  hosts: openstack_compute
  become: yes
  tasks:
    - name: Display compute node info
      debug:
        msg: "This is an OpenStack compute node"
"""
        
        fab_node.execute(f'cat > ~/ansible/playbooks/sample.yml << "EOF"\n{sample_playbook}\nEOF')
        
        logger.info("Sample playbook deployed")
        print("   ✅ Sample playbook deployed to ~/ansible/playbooks/sample.yml")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to deploy sample playbook: {e}")
        print(f"❌ Failed to deploy sample playbook: {e}")
        return False


def setup_ansible_environment(slice, topology: SiteTopology, 
                              python_version: str = "3.11",
                              deploy_sample: bool = True) -> bool:
    """
    Complete Ansible environment setup on the control node.
    
    This performs all steps:
    1. Install Ansible in a virtual environment
    2. Create directory structure
    3. Generate and deploy inventory
    4. Create ansible.cfg
    5. Optionally deploy sample playbook
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        python_version: Python version to use
        deploy_sample: Whether to deploy sample playbook
        
    Returns:
        True if successful, False otherwise
    """
    logger.info("Setting up complete Ansible environment")
    print("\n🚀 Setting up Ansible environment...\n")
    
    # Check for control node
    control_node = get_ansible_control_node(topology)
    if not control_node:
        print("❌ No Ansible control node found in topology")
        print("   Add 'ansible: {control: \"true\"}' to a node's specific section")
        return False
    
    print(f"✅ Ansible control node: {control_node.name}\n")
    
    # Step 1: Install Ansible
    if not install_ansible_on_control_node(slice, topology, python_version):
        return False
    
    # Step 2: Create config
    if not create_ansible_config(slice, topology):
        return False
    
    # Step 3: Deploy inventory
    if not deploy_ansible_inventory(slice, topology):
        return False
    
    # Step 4: Deploy sample playbook
    if deploy_sample:
        if not deploy_sample_playbook(slice, topology):
            logger.warning("Failed to deploy sample playbook, continuing...")
    
    # Print usage instructions
    print("\n" + "=" * 70)
    print("✅ Ansible environment setup complete!")
    print("=" * 70)
    print(f"\nTo use Ansible on {control_node.name}:")
    print(f"  1. SSH to the control node")
    print(f"  2. Activate the virtual environment:")
    print(f"     source ~/ansible/venv/bin/activate")
    print(f"  3. Test connectivity:")
    print(f"     ansible all_nodes -m ping")
    print(f"  4. Run the sample playbook:")
    print(f"     ansible-playbook ~/ansible/playbooks/sample.yml")
    print(f"\nDirectory structure:")
    print(f"  ~/ansible/")
    print(f"    ├── venv/              (Python virtual environment)")
    print(f"    ├── ansible.cfg        (Ansible configuration)")
    print(f"    ├── inventory/hosts    (Inventory file)")
    print(f"    ├── playbooks/         (Your playbooks)")
    print(f"    ├── roles/             (Ansible roles)")
    print(f"    ├── group_vars/        (Group variables)")
    print(f"    └── host_vars/         (Host variables)")
    print("=" * 70 + "\n")
    
    return True


def test_ansible_connectivity(slice, topology: SiteTopology) -> Dict[str, bool]:
    """
    Test Ansible connectivity to all managed nodes.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        Dictionary mapping hostname to connectivity status
    """
    logger.info("Testing Ansible connectivity")
    print("\n🔍 Testing Ansible connectivity...\n")
    
    control_node_model = get_ansible_control_node(topology)
    if not control_node_model:
        print("❌ No Ansible control node found")
        return {}
    
    try:
        fab_node = slice.get_node(control_node_model.name)
        
        # Run ansible ping
        print("   Running: ansible all_nodes -m ping\n")
        stdout, stderr = fab_node.execute(
            "source ~/ansible/venv/bin/activate && "
            "cd ~/ansible && "
            "ansible all_nodes -m ping"
        )
        
        print(stdout)
        if stderr:
            print(f"Warnings/Errors:\n{stderr}")
        
        # Parse results
        results = {}
        for node in topology.site_topology_nodes.iter_nodes():
            if node.hostname in stdout:
                results[node.hostname] = "SUCCESS" in stdout
        
        # Summary
        print("\n📊 Connectivity Summary:")
        for hostname, success in results.items():
            status = "✅" if success else "❌"
            print(f"   {status} {hostname}")
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to test connectivity: {e}")
        print(f"❌ Failed to test connectivity: {e}")
        return {}

def generate_ansible_inventory_from_topology(
    topology: SiteTopology,
    use_placeholder_ips: bool = True,
    placeholder_subnet: str = "10.10.10.0/24"
) -> str:
    """
    Generate an Ansible inventory file directly from topology (without querying FABRIC).
    
    This is useful for:
    - Pre-deployment planning
    - Generating inventory templates
    - Offline inventory generation
    
    Uses IP addresses from the topology YAML if available, otherwise uses placeholder IPs.
    
    Args:
        topology: Site topology model
        use_placeholder_ips: If True, generates placeholder IPs when not specified
        placeholder_subnet: Subnet to use for generating placeholder IPs
        
    Returns:
        String containing the inventory file content
    """
    import ipaddress
    
    logger.info("Generating Ansible inventory from topology (offline mode)")
    
    inventory_lines = ["# Ansible Inventory - Generated from topology (offline mode)"]
    inventory_lines.append(f"# Note: IP addresses may be placeholders or from topology configuration")
    inventory_lines.append(f"# Groups: all_nodes, openstack_*, os_*, site_*, role_*\n")
    
    # Collections for different groupings
    all_nodes = []
    
    # OpenStack role groups
    control_nodes = []
    network_nodes = []
    compute_nodes = []
    storage_nodes = []
    
    # OS-based groups
    os_groups = {}
    
    # Site-based groups
    site_groups = {}
    
    # Custom Ansible role groups
    role_groups = {}
    
    # IP address generator for placeholder IPs
    if use_placeholder_ips:
        network = ipaddress.IPv4Network(placeholder_subnet)
        ip_generator = network.hosts()
        next(ip_generator)  # Skip .1 (typically gateway)
    
    node_counter = 0
    
    for node in topology.site_topology_nodes.iter_nodes():
        node_counter += 1
        
        # Get management IP from topology
        management_ip = None
        management_network_used = None
        ip_source = None
        
        # Check if a specific management network is configured
        mgmt_network_binding = node.get_management_network_binding()
        
        if mgmt_network_binding:
            # Try to get IP from the specified management network interface
            logger.debug(f"Looking for management network '{mgmt_network_binding}' on {node.name}")
            
            for nic_name, iface_name, iface in node.get_all_interfaces():
                if iface.binding == mgmt_network_binding:
                    # Check if IP is configured in topology
                    if iface.ipv4.address:
                        # Use configured IPv4 address
                        ip_str = iface.ipv4.address
                        management_ip = ip_str.split('/')[0] if '/' in ip_str else ip_str
                        management_network_used = mgmt_network_binding
                        ip_source = "topology_config"
                        logger.debug(f"Using configured IP {management_ip} from topology")
                        break
                    elif iface.ipv6.address:
                        # Use configured IPv6 address
                        ip_str = iface.ipv6.address
                        management_ip = ip_str.split('/')[0] if '/' in ip_str else ip_str
                        management_network_used = mgmt_network_binding
                        ip_source = "topology_config"
                        logger.debug(f"Using configured IPv6 {management_ip} from topology")
                        break
        
        # Fall back to first interface with configured IP if management network not specified
        if not management_ip:
            logger.debug(f"Checking all interfaces for configured IP on {node.name}")
            
            for nic_name, iface_name, iface in node.get_all_interfaces():
                if iface.binding:
                    if iface.ipv4.address:
                        ip_str = iface.ipv4.address
                        management_ip = ip_str.split('/')[0] if '/' in ip_str else ip_str
                        management_network_used = iface.binding
                        ip_source = "topology_config"
                        logger.debug(f"Using first configured IP {management_ip} from {iface.binding}")
                        break
                    elif iface.ipv6.address:
                        ip_str = iface.ipv6.address
                        management_ip = ip_str.split('/')[0] if '/' in ip_str else ip_str
                        management_network_used = iface.binding
                        ip_source = "topology_config"
                        logger.debug(f"Using first configured IPv6 {management_ip} from {iface.binding}")
                        break
        
        # Generate placeholder IP if no configured IP found
        if not management_ip and use_placeholder_ips:
            try:
                management_ip = str(next(ip_generator))
                ip_source = "placeholder"
                
                # Try to identify the network that would be used
                if mgmt_network_binding:
                    management_network_used = mgmt_network_binding
                else:
                    # Use first available binding
                    for nic_name, iface_name, iface in node.get_all_interfaces():
                        if iface.binding:
                            management_network_used = iface.binding
                            break
                
                logger.debug(f"Generated placeholder IP {management_ip} for {node.name}")
            except StopIteration:
                logger.error(f"Ran out of placeholder IPs in subnet {placeholder_subnet}")
                management_ip = "PLACEHOLDER_IP_NEEDED"
                ip_source = "error"
        
        if not management_ip:
            logger.warning(f"No IP found or generated for {node.name}, using placeholder")
            management_ip = f"PLACEHOLDER_IP_{node_counter}"
            ip_source = "placeholder_text"
        
        # Determine ansible_user based on OS image
        ansible_user = get_ansible_user_for_os(node.capacity.os)
        
        # Build node entry with ansible_user and comment
        node_entry = f"{node.hostname} ansible_host={management_ip} ansible_user={ansible_user}"
        
        # Add informative comment
        comment_parts = []
        if management_network_used:
            comment_parts.append(f"via {management_network_used}")
        if ip_source == "placeholder":
            comment_parts.append("PLACEHOLDER IP - UPDATE AFTER DEPLOYMENT")
        elif ip_source == "placeholder_text":
            comment_parts.append("NO IP - MUST BE CONFIGURED")
        elif ip_source == "topology_config":
            comment_parts.append("from topology config")
        
        if comment_parts:
            node_entry += f"  # {', '.join(comment_parts)}"
        
        # Add to all_nodes
        all_nodes.append(node_entry)
        
        # Add to OpenStack role groups
        if node.specific.openstack.is_control():
            control_nodes.append(node_entry)
        if node.specific.openstack.is_network():
            network_nodes.append(node_entry)
        if node.specific.openstack.is_compute():
            compute_nodes.append(node_entry)
        if node.specific.openstack.is_storage():
            storage_nodes.append(node_entry)
        
        # Add to OS-based groups
        os_type = _extract_os_name(node.capacity.os)
        if os_type not in os_groups:
            os_groups[os_type] = []
        os_groups[os_type].append(node_entry)
        
        # Add to site-based groups
        if node.site:
            site_name = node.site.strip()
            if site_name not in site_groups:
                site_groups[site_name] = []
            site_groups[site_name].append(node_entry)
        
        # Add to custom Ansible role groups
        ansible_roles = node.specific.get_ansible_roles()
        for role_name in ansible_roles:
            if role_name not in role_groups:
                role_groups[role_name] = []
            role_groups[role_name].append(node_entry)
    
    # Build inventory file
    
    # All nodes group
    inventory_lines.append("# ============================================")
    inventory_lines.append("# ALL NODES")
    inventory_lines.append("# ============================================")
    inventory_lines.append("[all_nodes]")
    inventory_lines.extend(all_nodes)
    
    # OpenStack role groups
    if control_nodes or network_nodes or compute_nodes or storage_nodes:
        inventory_lines.append("")
        inventory_lines.append("# ============================================")
        inventory_lines.append("# OPENSTACK ROLES")
        inventory_lines.append("# ============================================")
        
        if control_nodes:
            inventory_lines.append("[openstack_control]")
            inventory_lines.extend(control_nodes)
            inventory_lines.append("")
        
        if network_nodes:
            inventory_lines.append("[openstack_network]")
            inventory_lines.extend(network_nodes)
            inventory_lines.append("")
        
        if compute_nodes:
            inventory_lines.append("[openstack_compute]")
            inventory_lines.extend(compute_nodes)
            inventory_lines.append("")
        
        if storage_nodes:
            inventory_lines.append("[openstack_storage]")
            inventory_lines.extend(storage_nodes)
    
    # OS-based groups
    if os_groups:
        inventory_lines.append("")
        inventory_lines.append("# ============================================")
        inventory_lines.append("# OS-BASED GROUPS")
        inventory_lines.append("# ============================================")
        for os_name in sorted(os_groups.keys()):
            inventory_lines.append(f"[os_{os_name}]")
            inventory_lines.extend(os_groups[os_name])
            inventory_lines.append("")
    
    # Site-based groups
    if site_groups:
        inventory_lines.append("# ============================================")
        inventory_lines.append("# SITE-BASED GROUPS")
        inventory_lines.append("# ============================================")
        for site_name in sorted(site_groups.keys()):
            inventory_lines.append(f"[site_{site_name}]")
            inventory_lines.extend(site_groups[site_name])
            inventory_lines.append("")
    
    # Custom Ansible role groups
    if role_groups:
        inventory_lines.append("# ============================================")
        inventory_lines.append("# CUSTOM ANSIBLE ROLES")
        inventory_lines.append("# ============================================")
        for role_name in sorted(role_groups.keys()):
            inventory_lines.append(f"[role_{role_name}]")
            inventory_lines.extend(role_groups[role_name])
            inventory_lines.append("")
    
    # Add common variables
    inventory_lines.append("# ============================================")
    inventory_lines.append("# GLOBAL VARIABLES")
    inventory_lines.append("# ============================================")
    inventory_lines.append("[all_nodes:vars]")
    inventory_lines.append("ansible_python_interpreter=/usr/bin/python3")
    inventory_lines.append("ansible_ssh_common_args='-o StrictHostKeyChecking=no'")
    
    return "\n".join(inventory_lines)


def save_inventory_to_file(inventory_content: str, filepath: str) -> bool:
    """
    Save inventory content to a file.
    
    Args:
        inventory_content: Inventory file content
        filepath: Path where to save the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(filepath, 'w') as f:
            f.write(inventory_content)
        logger.info(f"Inventory saved to {filepath}")
        print(f"✅ Inventory saved to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Failed to save inventory to {filepath}: {e}")
        print(f"❌ Failed to save inventory: {e}")
        return False


def generate_inventory_template_from_yaml(
    yaml_path: str,
    output_path: str = "inventory_template.ini",
    use_placeholder_ips: bool = True,
    placeholder_subnet: str = "10.10.10.0/24"
) -> bool:
    """
    Convenience function to generate inventory template directly from YAML file.
    
    Args:
        yaml_path: Path to topology YAML file
        output_path: Where to save the generated inventory
        use_placeholder_ips: Generate placeholder IPs if not in topology
        placeholder_subnet: Subnet for placeholder IPs
        
    Returns:
        True if successful, False otherwise
    """
    from .models import load_topology_from_yaml_file
    
    try:
        print(f"\n📋 Generating inventory template from {yaml_path}...\n")
        
        # Load topology
        topology = load_topology_from_yaml_file(yaml_path)
        
        # Generate inventory
        inventory_content = generate_ansible_inventory_from_topology(
            topology,
            use_placeholder_ips=use_placeholder_ips,
            placeholder_subnet=placeholder_subnet
        )
        
        # Save to file
        save_inventory_to_file(inventory_content, output_path)
        
        print(f"\n💡 Review {output_path} and update placeholder IPs after deployment")
        return True
        
    except Exception as e:
        logger.error(f"Failed to generate inventory template: {e}")
        print(f"❌ Error: {e}")
        return False
