# slice_ssh_setup.py
"""
SSH key management and passwordless access configuration for FABRIC slices.
"""

import logging
from typing import Dict, List

from .models import SiteTopology

logger = logging.getLogger(__name__)


class SSHSetupError(Exception):
    """Raised when SSH setup operations fail."""
    pass


def generate_ssh_keys_on_nodes(slice) -> Dict[str, bool]:
    """
    Generate SSH keypairs on all nodes in the slice (if not already present).
    
    Args:
        slice: FABRIC slice object
        
    Returns:
        Dictionary mapping hostname to success status
    """
    logger.info("Checking and generating SSH keys on all nodes")
    print("\n🔑 Checking SSH keys on all nodes...\n")
    
    check_command = 'test -f ~/.ssh/id_rsa && echo "EXISTS" || echo "MISSING"'
    generate_command = 'ssh-keygen -t ed25519 -q -f "$HOME/.ssh/id_rsa" -N "" <<< y'
    
    results = {}
    
    for node in slice.get_nodes():
        hostname = node.get_name()
        logger.debug(f"Checking SSH key on {hostname}")
        print(f"🔎 Checking SSH key on {hostname}...")
        
        try:
            result, _ = node.execute(check_command)
            
            if "EXISTS" in result:
                logger.info(f"SSH key already exists on {hostname}")
                print(f"✅ SSH key already exists on {hostname}")
                results[hostname] = True
            else:
                logger.info(f"Generating SSH key on {hostname}")
                print(f"🛠️  Generating SSH key on {hostname}...")
                
                stdout, stderr = node.execute(generate_command)
                logger.info(f"SSH key generated on {hostname}")
                print(f"✅ SSH key generated on {hostname}")
                
                if stdout.strip():
                    logger.debug(f"stdout: {stdout.strip()}")
                if stderr.strip():
                    logger.debug(f"stderr: {stderr.strip()}")
                
                results[hostname] = True
                
        except Exception as e:
            logger.error(f"Failed to generate SSH key on {hostname}: {e}")
            print(f"❌ Error on {hostname}: {e}")
            results[hostname] = False
    
    return results


def collect_public_keys(slice) -> Dict[str, str]:
    """
    Collect SSH public keys from all nodes.
    
    Args:
        slice: FABRIC slice object
        
    Returns:
        Dictionary mapping hostname to public key
    """
    logger.info("Collecting SSH public keys from all nodes")
    print("\n📋 Collecting SSH public keys...\n")
    
    public_keys = {}
    get_pub_key_command = 'cat ~/.ssh/id_rsa.pub'
    
    for node in slice.get_nodes():
        hostname = node.get_name()
        
        try:
            pub_key, _ = node.execute(get_pub_key_command)
            public_keys[hostname] = pub_key.strip()
            logger.info(f"Retrieved public key from {hostname}")
            print(f"✅ Retrieved public key from {hostname}")
            
        except Exception as e:
            logger.error(f"Failed to retrieve public key from {hostname}: {e}")
            print(f"❌ Failed to retrieve key from {hostname}: {e}")
    
    return public_keys


def distribute_ssh_keys(slice, public_keys: Dict[str, str]) -> Dict[str, bool]:
    """
    Distribute SSH public keys to all nodes (avoiding duplicates).
    Each node will trust all other nodes AND itself.
    
    Args:
        slice: FABRIC slice object
        public_keys: Dictionary mapping hostname to public key
        
    Returns:
        Dictionary mapping hostname to success status
    """
    logger.info("Distributing SSH public keys to all nodes")
    print("\n🔗 Distributing public keys (including self-trust)...\n")
    
    results = {}
    
    for node in slice.get_nodes():
        hostname = node.get_name()
        logger.debug(f"Updating authorized_keys on {hostname}")
        
        try:
            # Ensure .ssh directory exists
            node.execute("mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys")
            
            # Get existing keys to avoid duplicates
            existing_keys, _ = node.execute("cat ~/.ssh/authorized_keys || true")
            existing_keys_set = set(existing_keys.strip().splitlines())
            
            # Add new keys (including the node's own key for self-trust)
            keys_added = 0
            for peer_host, pub_key in public_keys.items():
                # Add all keys, including own key (no skip for self)
                if pub_key and pub_key not in existing_keys_set:
                    safe_key = pub_key.replace('"', '\\"')
                    append_command = f'echo "{safe_key}" >> ~/.ssh/authorized_keys'
                    node.execute(append_command)
                    keys_added += 1
            
            logger.info(f"Added {keys_added} keys to {hostname} (including self)")
            print(f"🔑 Updated authorized_keys on {hostname} ({keys_added} new keys, self-trust enabled)")
            results[hostname] = True
            
        except Exception as e:
            logger.error(f"Failed to update authorized_keys on {hostname}: {e}")
            print(f"❌ Error updating {hostname}: {e}")
            results[hostname] = False
    
    return results


def disable_strict_host_key_checking(slice) -> Dict[str, bool]:
    """
    Configure SSH to disable StrictHostKeyChecking on all nodes.
    
    Args:
        slice: FABRIC slice object
        
    Returns:
        Dictionary mapping hostname to success status
    """
    logger.info("Disabling StrictHostKeyChecking on all nodes")
    print("\n🚫 Disabling StrictHostKeyChecking...\n")
    
    ssh_config_content = (
        'Host *\n'
        '    StrictHostKeyChecking no\n'
        '    UserKnownHostsFile=/dev/null\n'
    )
    
    results = {}
    
    for node in slice.get_nodes():
        hostname = node.get_name()
        
        try:
            logger.debug(f"Configuring SSH on {hostname}")
            print(f"🔧 Configuring SSH on {hostname}...")
            
            # Create .ssh directory if needed
            node.execute('mkdir -p ~/.ssh && chmod 700 ~/.ssh')
            
            # Write SSH config
            node.execute(f'echo "{ssh_config_content}" >> ~/.ssh/config')
            node.execute('chmod 600 ~/.ssh/config')
            
            logger.info(f"SSH configured on {hostname}")
            print(f"✅ SSH config updated on {hostname}")
            results[hostname] = True
            
        except Exception as e:
            logger.error(f"Failed to configure SSH on {hostname}: {e}")
            print(f"⚠️  Failed to update SSH config on {hostname}: {e}")
            results[hostname] = False
    
    return results


def setup_passwordless_ssh(slice) -> bool:
    """
    Complete setup for passwordless SSH access between all nodes.
    Each node will trust all other nodes AND itself.
    
    This performs:
    1. Generate SSH keypairs (if missing)
    2. Collect public keys
    3. Distribute keys to all nodes (including self-trust)
    4. Disable strict host key checking
    
    Args:
        slice: FABRIC slice object
        
    Returns:
        True if setup successful, False otherwise
    """
    logger.info("Starting passwordless SSH setup with self-trust")
    print("\n🔐 Setting up passwordless SSH access (with self-trust)...\n")
    
    try:
        # Step 1: Generate keys
        gen_results = generate_ssh_keys_on_nodes(slice)
        if not all(gen_results.values()):
            logger.warning("Some nodes failed key generation")
            print("⚠️  Warning: Some nodes failed key generation")
        
        # Step 2: Collect keys
        public_keys = collect_public_keys(slice)
        if len(public_keys) != len(list(slice.get_nodes())):
            logger.warning("Failed to collect all public keys")
            print("⚠️  Warning: Could not collect all public keys")
        
        # Step 3: Distribute keys (including self-trust)
        dist_results = distribute_ssh_keys(slice, public_keys)
        if not all(dist_results.values()):
            logger.warning("Some nodes failed key distribution")
            print("⚠️  Warning: Some nodes failed key distribution")
        
        # Step 4: Disable strict checking
        ssh_results = disable_strict_host_key_checking(slice)
        if not all(ssh_results.values()):
            logger.warning("Some nodes failed SSH config update")
            print("⚠️  Warning: Some nodes failed SSH config")
        
        logger.info("Passwordless SSH setup completed (self-trust enabled)")
        print("\n✅ Passwordless SSH setup completed")
        print("   ℹ️  All nodes can now SSH to each other AND to themselves\n")
        return True
        
    except Exception as e:
        logger.error(f"SSH setup failed: {e}")
        print(f"❌ SSH setup failed: {e}")
        return False


def verify_ssh_access(
    slice,
    topology: SiteTopology,
    source_hostname: str,
    network_name: str,
    use_ipv6: bool = False
) -> Dict[str, bool]:
    """
    Verify SSH access from source node to all other nodes on a network.
    
    Args:
        slice: FABRIC slice object
        topology: Site topology model
        source_hostname: Hostname of the source node
        network_name: Name of the network to test
        use_ipv6: Whether to use IPv6 addresses
        
    Returns:
        Dictionary mapping target hostname to success status
    """
    logger.info(f"Verifying SSH access from {source_hostname} on {network_name}")
    print(f"\n🔍 Verifying SSH from {source_hostname} on {network_name}:\n")
    
    # Get source node
    source_node_model = topology.get_node_by_hostname(source_hostname)
    if not source_node_model:
        logger.error(f"Source node '{source_hostname}' not found")
        print(f"❌ Source node not found: {source_hostname}")
        return {}
    
    try:
        source_fab_node = slice.get_node(source_hostname)
    except Exception as e:
        logger.error(f"Failed to get source node from slice: {e}")
        print(f"❌ Error retrieving source node: {e}")
        return {}
    
    results = {}
    
    # Get target nodes on the same network from topology
    target_nodes_from_topology = topology.get_nodes_on_network(network_name)
    
    # Debug: Print what we found
    print(f"🔍 Found {len(target_nodes_from_topology)} nodes on network '{network_name}'")
    if len(target_nodes_from_topology) == 0:
        print(f"⚠️  No nodes found on network '{network_name}'")
        print(f"   Available networks in topology:")
        for net_name in topology.site_topology_networks.networks.keys():
            nodes_on_net = topology.get_nodes_on_network(net_name)
            print(f"      - {net_name}: {[n.hostname for n in nodes_on_net]}")
        return {}
    
    target_hostnames = [node.hostname for node in target_nodes_from_topology if node.hostname != source_hostname]
    print(f"   Target nodes to test: {target_hostnames}\n")
    
    for target_node_model in target_nodes_from_topology:
        if target_node_model.hostname == source_hostname:
            continue  # Skip self
        
        target_hostname = target_node_model.hostname
        
        # Get the actual FABRIC node to retrieve real IP addresses
        try:
            target_fab_node = slice.get_node(target_hostname)
        except Exception as e:
            logger.error(f"Failed to get FABRIC node {target_hostname}: {e}")
            print(f"❌ Could not get FABRIC node {target_hostname}: {e}")
            continue
        
        # Get the interface from the FABRIC node
        # First, find which device/interface is connected to this network from topology
        interfaces_from_topology = target_node_model.get_interfaces_for_network(network_name)
        if not interfaces_from_topology:
            print(f"⚠️  {target_hostname} has no interfaces on {network_name} in topology")
            continue
        
        device_name, _ = interfaces_from_topology[0]
        
        # Get the actual interface from FABRIC slice node
        try:
            target_fab_iface = target_fab_node.get_interface(network_name=network_name)
        except:
            # Fallback: try by device name
            try:
                target_fab_iface = target_fab_node.get_interface(name=device_name)
            except Exception as e:
                logger.error(f"Could not get interface for {target_hostname}: {e}")
                print(f"⚠️  Could not get interface on {target_hostname}: {e}")
                continue
        
        # Get IP address from the actual FABRIC interface
        if use_ipv6:
            try:
                target_ip = target_fab_iface.get_ip_addr()
                # Check if it's IPv6 (contains ':')
                if target_ip and ':' not in target_ip:
                    # It's IPv4, we need IPv6
                    target_ip = None
            except:
                target_ip = None
        else:
            try:
                target_ip = target_fab_iface.get_ip_addr()
                # Check if it's IPv4 (contains '.')
                if target_ip and '.' not in target_ip:
                    # It's IPv6, we need IPv4
                    target_ip = None
            except:
                target_ip = None
        
        if not target_ip:
            logger.warning(f"No IP address for {target_hostname}")
            print(f"⚠️  No {'IPv6' if use_ipv6 else 'IPv4'} address for {target_hostname}")
            print(f"   Try running 'slice.get_node(\"{target_hostname}\").get_interface(network_name=\"{network_name}\").show()' to debug")
            continue
        
        # Test SSH connection
        print(f"🔗 Testing SSH to {target_hostname} at {target_ip}...")
        
        try:
            stdout, stderr = source_fab_node.execute(
                f'ssh -o ConnectTimeout=5 {target_ip} '
                f'"echo SSH to {target_hostname} OK"'
            )
            
            success = "OK" in stdout
            results[target_hostname] = success
            
            if success:
                print(f"✅ {stdout.strip()}")
            else:
                print(f"⚠️  SSH connection issue: {stdout.strip()}")
            
            if stderr and stderr.strip():
                logger.debug(f"stderr: {stderr.strip()}")
                # Don't print stderr unless there's an actual error
                # (SSH often writes warnings to stderr that we can ignore)
                
        except Exception as e:
            logger.error(f"SSH to {target_hostname} ({target_ip}) failed: {e}")
            print(f"❌ SSH to {target_hostname} failed: {e}")
            results[target_hostname] = False
    
    # Summary
    print(f"\n📊 SSH Verification Summary:")
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"   Successful: {successful}/{total}")
    
    return results


def remove_ssh_keys(slice, remove_entire_ssh_dir: bool = False) -> Dict[str, bool]:
    """
    Remove SSH keypairs from all nodes in the slice.
    
    Args:
        slice: FABRIC slice object
        remove_entire_ssh_dir: If True, removes entire ~/.ssh directory
        
    Returns:
        Dictionary mapping hostname to success status
    """
    logger.info("Removing SSH keys from all nodes")
    print("\n🧹 Removing SSH keys from all nodes...\n")
    
    results = {}
    
    for node in slice.get_nodes():
        hostname = node.get_name()
        logger.debug(f"Removing SSH keys from {hostname}")
        print(f"🗑️  Removing SSH keys from {hostname}...")
        
        try:
            if remove_entire_ssh_dir:
                node.execute("rm -rf ~/.ssh")
                logger.info(f"Removed entire .ssh directory from {hostname}")
                print(f"✅ Entire ~/.ssh directory removed from {hostname}")
            else:
                node.execute("rm -f ~/.ssh/id_rsa ~/.ssh/id_rsa.pub")
                logger.info(f"Removed SSH keypair from {hostname}")
                print(f"✅ SSH keypair removed from {hostname}")
            
            results[hostname] = True
            
        except Exception as e:
            logger.error(f"Failed to remove SSH keys from {hostname}: {e}")
            print(f"❌ Error removing keys from {hostname}: {e}")
            results[hostname] = False
    
    return results
