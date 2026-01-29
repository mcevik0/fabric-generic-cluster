# selinux_management.py
"""
SELinux management for FABRIC slices.
Handles checking status and setting modes (enforcing, permissive, disabled).
"""

import logging
from typing import Dict, Optional, Tuple
from enum import Enum

from .models import SiteTopology

logger = logging.getLogger(__name__)


class SELinuxMode(Enum):
    """SELinux mode options."""
    ENFORCING = "enforcing"
    PERMISSIVE = "permissive"
    DISABLED = "disabled"


class SELinuxManagementError(Exception):
    """Raised when SELinux management operations fail."""
    pass


def check_selinux_available(fab_node) -> bool:
    """
    Check if SELinux is available on the node.
    
    Args:
        fab_node: FABRIC node object
        
    Returns:
        True if SELinux is available, False otherwise
    """
    try:
        stdout, _ = fab_node.execute("command -v getenforce")
        return bool(stdout.strip())
    except:
        return False


def get_selinux_status(fab_node, node_name: str) -> Optional[Dict[str, str]]:
    """
    Get detailed SELinux status for a node.
    
    Args:
        fab_node: FABRIC node object
        node_name: Name of the node (for logging)
        
    Returns:
        Dictionary with SELinux status info, or None if SELinux not available
        Example: {
            'current_mode': 'enforcing',
            'mode_from_config': 'enforcing',
            'policy': 'targeted',
            'status': 'enabled'
        }
    """
    if not check_selinux_available(fab_node):
        logger.info(f"SELinux not available on {node_name}")
        return None
    
    try:
        # Get current mode
        stdout, _ = fab_node.execute("getenforce")
        current_mode = stdout.strip().lower()
        
        # Try to get detailed status
        status_info = {
            'current_mode': current_mode,
            'mode_from_config': 'unknown',
            'policy': 'unknown',
            'status': 'unknown'
        }
        
        try:
            stdout, _ = fab_node.execute("sestatus")
            
            # Parse sestatus output
            for line in stdout.split('\n'):
                if 'SELinux status:' in line:
                    status_info['status'] = line.split(':')[1].strip().lower()
                elif 'Current mode:' in line:
                    status_info['current_mode'] = line.split(':')[1].strip().lower()
                elif 'Mode from config file:' in line:
                    status_info['mode_from_config'] = line.split(':')[1].strip().lower()
                elif 'Loaded policy name:' in line:
                    status_info['policy'] = line.split(':')[1].strip().lower()
        except:
            logger.debug(f"Could not get detailed sestatus on {node_name}")
        
        return status_info
        
    except Exception as e:
        logger.error(f"Failed to get SELinux status on {node_name}: {e}")
        return None


def set_selinux_mode_runtime(fab_node, node_name: str, mode: SELinuxMode) -> bool:
    """
    Set SELinux mode at runtime (temporary, until reboot).
    
    Note: Cannot enable SELinux at runtime if it's disabled.
    To fully disable, must edit config and reboot.
    
    Args:
        fab_node: FABRIC node object
        node_name: Name of the node
        mode: SELinuxMode enum value
        
    Returns:
        True if successful, False otherwise
    """
    if not check_selinux_available(fab_node):
        logger.warning(f"SELinux not available on {node_name}")
        print(f"   ⚠️  SELinux not available on {node_name}")
        return False
    
    try:
        if mode == SELinuxMode.DISABLED:
            print(f"   ⚠️  Cannot disable SELinux at runtime on {node_name}")
            print(f"      Use set_selinux_mode_persistent() and reboot")
            return False
        
        mode_value = "0" if mode == SELinuxMode.PERMISSIVE else "1"
        
        logger.info(f"Setting SELinux to {mode.value} on {node_name}")
        stdout, stderr = fab_node.execute(f"sudo setenforce {mode_value}")
        
        # Verify
        stdout, _ = fab_node.execute("getenforce")
        current = stdout.strip().lower()
        
        if current == mode.value:
            logger.info(f"SELinux set to {mode.value} on {node_name}")
            return True
        else:
            logger.error(f"SELinux mode verification failed on {node_name}: expected {mode.value}, got {current}")
            return False
        
    except Exception as e:
        logger.error(f"Failed to set SELinux mode on {node_name}: {e}")
        print(f"   ❌ Error: {e}")
        return False


def set_selinux_mode_persistent(fab_node, node_name: str, mode: SELinuxMode) -> bool:
    """
    Set SELinux mode persistently (survives reboot).
    Modifies /etc/selinux/config file.
    
    Args:
        fab_node: FABRIC node object
        node_name: Name of the node
        mode: SELinuxMode enum value
        
    Returns:
        True if successful, False otherwise
    """
    if not check_selinux_available(fab_node):
        logger.warning(f"SELinux not available on {node_name}")
        print(f"   ⚠️  SELinux not available on {node_name}")
        return False
    
    try:
        config_file = "/etc/selinux/config"
        
        # Check if config file exists
        stdout, _ = fab_node.execute(f"test -f {config_file} && echo 'exists'")
        if "exists" not in stdout:
            logger.error(f"SELinux config file not found on {node_name}")
            print(f"   ❌ {config_file} not found on {node_name}")
            return False
        
        # Backup config file
        fab_node.execute(f"sudo cp {config_file} {config_file}.bak")
        
        # Update config file
        logger.info(f"Setting SELinux to {mode.value} persistently on {node_name}")
        fab_node.execute(
            f"sudo sed -i 's/^SELINUX=.*/SELINUX={mode.value}/' {config_file}"
        )
        
        # Verify change
        stdout, _ = fab_node.execute(f"grep '^SELINUX=' {config_file}")
        if mode.value in stdout:
            logger.info(f"SELinux config updated on {node_name}")
            print(f"   ✅ SELinux set to {mode.value} in {config_file}")
            
            if mode != SELinuxMode.DISABLED:
                # Also set runtime mode if not disabling
                set_selinux_mode_runtime(fab_node, node_name, mode)
            
            return True
        else:
            logger.error(f"Failed to verify SELinux config update on {node_name}")
            return False
        
    except Exception as e:
        logger.error(f"Failed to set persistent SELinux mode on {node_name}: {e}")
        print(f"   ❌ Error: {e}")
        return False


def check_selinux_status_all_nodes(slice, topology: SiteTopology) -> Dict[str, Optional[Dict]]:
    """
    Check SELinux status on all nodes in the slice.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        Dictionary mapping node names to their SELinux status
    """
    logger.info("Checking SELinux status on all nodes")
    print("\n🔍 Checking SELinux status on all nodes...\n")
    
    results = {}
    
    for node in topology.site_topology_nodes.iter_nodes():
        try:
            fab_node = slice.get_node(node.name)
            status = get_selinux_status(fab_node, node.name)
            results[node.name] = status
            
            if status:
                print(f"🖥️  {node.name}:")
                print(f"   Status: {status['status']}")
                print(f"   Current mode: {status['current_mode']}")
                print(f"   Config file mode: {status['mode_from_config']}")
                print(f"   Policy: {status['policy']}")
            else:
                print(f"🖥️  {node.name}:")
                print(f"   ℹ️  SELinux not available (likely not a RHEL-based system)")
            print()
            
        except Exception as e:
            logger.error(f"Failed to check SELinux on {node.name}: {e}")
            print(f"❌ Error checking {node.name}: {e}\n")
            results[node.name] = None
    
    return results


def set_selinux_mode_all_nodes(
    slice,
    topology: SiteTopology,
    mode: SELinuxMode,
    persistent: bool = True,
    nodes: Optional[list] = None
) -> Dict[str, bool]:
    """
    Set SELinux mode on all (or specified) nodes.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        mode: SELinuxMode to set
        persistent: If True, updates config file (survives reboot)
        nodes: Optional list of node names to target (if None, targets all)
        
    Returns:
        Dictionary mapping node names to success status
    """
    mode_str = "persistent" if persistent else "runtime"
    logger.info(f"Setting SELinux to {mode.value} ({mode_str}) on nodes")
    print(f"\n⚙️  Setting SELinux to {mode.value} ({mode_str})...\n")
    
    results = {}
    
    target_nodes = topology.site_topology_nodes.iter_nodes()
    if nodes:
        target_nodes = [n for n in target_nodes if n.name in nodes]
    
    for node in target_nodes:
        print(f"🔧 Configuring {node.name}...")
        
        try:
            fab_node = slice.get_node(node.name)
            
            if persistent:
                success = set_selinux_mode_persistent(fab_node, node.name, mode)
            else:
                success = set_selinux_mode_runtime(fab_node, node.name, mode)
            
            results[node.name] = success
            
            if success:
                print(f"   ✅ SELinux set to {mode.value}")
            else:
                print(f"   ❌ Failed to set SELinux mode")
            
        except Exception as e:
            logger.error(f"Failed to configure SELinux on {node.name}: {e}")
            print(f"   ❌ Error: {e}")
            results[node.name] = False
        
        print()
    
    # Summary
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"📊 Summary: {successful}/{total} nodes configured successfully")
    
    if mode == SELinuxMode.DISABLED and persistent:
        print("\n⚠️  Note: To fully disable SELinux, nodes must be rebooted.")
        print("   Current sessions may still have SELinux enforcing.")
    
    return results


def set_selinux_permissive_for_openstack(slice, topology: SiteTopology) -> Dict[str, bool]:
    """
    Convenience function to set SELinux to permissive on OpenStack nodes.
    This is often needed for OpenStack deployments.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        
    Returns:
        Dictionary mapping node names to success status
    """
    logger.info("Setting SELinux to permissive on OpenStack nodes")
    print("\n🔧 Setting SELinux to permissive for OpenStack deployment...\n")
    
    # Find OpenStack nodes
    openstack_nodes = []
    for node in topology.site_topology_nodes.iter_nodes():
        if (node.specific.openstack.is_control() or
            node.specific.openstack.is_network() or
            node.specific.openstack.is_compute() or
            node.specific.openstack.is_storage()):
            openstack_nodes.append(node.name)
    
    if not openstack_nodes:
        print("ℹ️  No OpenStack nodes found in topology")
        return {}
    
    print(f"📋 Target nodes: {', '.join(openstack_nodes)}\n")
    
    return set_selinux_mode_all_nodes(
        slice,
        topology,
        mode=SELinuxMode.PERMISSIVE,
        persistent=True,
        nodes=openstack_nodes
    )


def display_selinux_summary(slice, topology: SiteTopology) -> None:
    """
    Display a formatted summary of SELinux status across all nodes.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
    """
    from tabulate import tabulate
    
    print("\n" + "="*70)
    print("SELINUX STATUS SUMMARY")
    print("="*70 + "\n")
    
    status_data = check_selinux_status_all_nodes(slice, topology)
    
    # Prepare table
    rows = []
    for node_name, status in status_data.items():
        if status:
            rows.append([
                node_name,
                status['status'],
                status['current_mode'],
                status['mode_from_config'],
                status['policy']
            ])
        else:
            rows.append([node_name, "N/A", "N/A", "N/A", "N/A"])
    
    print(tabulate(
        rows,
        headers=["Node", "Status", "Current Mode", "Config Mode", "Policy"],
        tablefmt="fancy_grid"
    ))
    print("\n" + "="*70 + "\n")

def configure_selinux_from_topology(
    slice,
    topology: SiteTopology,
    persistent: bool = True,
    apply_immediately: bool = True
) -> Dict[str, bool]:
    """
    Configure SELinux on nodes based on topology specifications.

    Reads selinux.mode from each node's specific section and applies it.
    Only configures nodes that have selinux mode specified in topology.

    Args:
        slice: FABRIC slice object
        topology: Site topology model
        persistent: If True, updates config file (survives reboot)
        apply_immediately: If True, also sets runtime mode (when possible)

    Returns:
        Dictionary mapping node names to success status
    """
    logger.info("Configuring SELinux based on topology specifications")
    print("\n⚙️  Configuring SELinux from topology...\n")

    results = {}
    nodes_to_configure = []

    # Find nodes with SELinux configuration
    for node in topology.site_topology_nodes.iter_nodes():
        selinux_mode = node.specific.get_selinux_mode()
        if selinux_mode:
            nodes_to_configure.append((node, selinux_mode))

    if not nodes_to_configure:
        print("ℹ️  No nodes have SELinux configuration in topology")
        logger.info("No SELinux configuration found in topology")
        return {}

    print(f"📋 Found {len(nodes_to_configure)} node(s) with SELinux configuration\n")

    # Configure each node
    for node, mode_str in nodes_to_configure:
        print(f"🔧 Configuring {node.name} (mode: {mode_str})...")

        # Validate mode
        try:
            mode = SELinuxMode(mode_str.lower())
        except ValueError:
            logger.error(f"Invalid SELinux mode '{mode_str}' for {node.name}")
            print(f"   ❌ Invalid mode '{mode_str}' (must be: enforcing, permissive, or disabled)")
            results[node.name] = False
            print()
            continue

        try:
            fab_node = slice.get_node(node.name)

            # Check if SELinux is available
            if not check_selinux_available(fab_node):
                logger.info(f"SELinux not available on {node.name}, skipping")
                print(f"   ℹ️  SELinux not available (not a RHEL-based system)")
                results[node.name] = None  # Not an error, just N/A
                print()
                continue

            # Set persistent configuration
            if persistent:
                success = set_selinux_mode_persistent(fab_node, node.name, mode)
            else:
                success = False

            # Also set runtime if requested and not disabling
            if apply_immediately and mode != SELinuxMode.DISABLED:
                runtime_success = set_selinux_mode_runtime(fab_node, node.name, mode)
                if not success:  # If persistent failed, at least check runtime
                    success = runtime_success

            results[node.name] = success

            if success:
                print(f"   ✅ SELinux configured to {mode.value}")
            else:
                print(f"   ❌ Failed to configure SELinux")

        except Exception as e:
            logger.error(f"Failed to configure SELinux on {node.name}: {e}")
            print(f"   ❌ Error: {e}")
            results[node.name] = False

        print()

    # Summary
    successful = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)

    print(f"📊 Summary:")
    print(f"   ✅ Configured: {successful}/{total}")
    if skipped > 0:
        print(f"   ℹ️  Skipped (N/A): {skipped}/{total}")

    # Check if reboot needed
    needs_reboot = any(
        mode_str.lower() == 'disabled'
        for _, mode_str in nodes_to_configure
    )

    if needs_reboot and persistent:
        print("\n⚠️  Note: Nodes configured with 'disabled' require reboot for full effect.")

    print()

    return results
