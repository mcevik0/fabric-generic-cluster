#!/usr/bin/env python3
"""
Complete FABRIC Deployment Example with DPU Interface Support

This script demonstrates the full deployment workflow:
1. Load topology from YAML
2. Create and submit slice
3. Configure L3 networks (if any)
4. Configure node interfaces (both NICs and DPUs)
5. Setup passwordless SSH
6. Verify connectivity

Usage:
    python complete_deployment_example.py --yaml _slice_topology_6-new.yaml --slice-name my-dpu-test
"""
import sys
sys.path.insert(0, '..')  # Add parent directory to path


import argparse
import sys
import time
import logging

# Import all the modules
from slice_utils_models import load_topology_from_yaml_file
import slice_deployment as sd
import slice_network_config as snc
import slice_ssh_setup as ssh

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def wait_for_slice(slice, timeout=600):
    """
    Wait for slice to reach Active state.
    
    Args:
        slice: FABRIC slice object
        timeout: Maximum time to wait in seconds
    """
    print_section("⏳ Waiting for Slice to Become Active")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = slice.get_state()
        print(f"   Status: {status} ({int(time.time() - start_time)}s elapsed)")
        
        if status == "StableError":
            print("❌ Slice failed to provision")
            return False
        elif status == "Active":
            print("✅ Slice is active!")
            return True
        
        time.sleep(30)
    
    print("❌ Timeout waiting for slice to become active")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Deploy FABRIC slice with DPU interface support",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--yaml",
        required=True,
        help="Path to topology YAML file"
    )
    
    parser.add_argument(
        "--slice-name",
        required=True,
        help="Name for the slice"
    )
    
    parser.add_argument(
        "--skip-deployment",
        action="store_true",
        help="Skip deployment, use existing slice (for testing configuration only)"
    )
    
    parser.add_argument(
        "--skip-ssh",
        action="store_true",
        help="Skip SSH setup"
    )
    
    parser.add_argument(
        "--test-network",
        help="Network name to test connectivity (default: first L2 network)"
    )
    
    args = parser.parse_args()
    
    try:
        # ====================================================================
        # Step 1: Load Topology
        # ====================================================================
        print_section("📋 Step 1: Loading Topology")
        
        print(f"Loading topology from: {args.yaml}")
        topology = load_topology_from_yaml_file(args.yaml)
        
        print(f"✅ Topology loaded successfully")
        print(f"   Nodes: {len(topology.site_topology_nodes.nodes)}")
        print(f"   Networks: {len(topology.site_topology_networks.networks)}")
        
        # Show what we found
        for node in topology.site_topology_nodes.iter_nodes():
            print(f"\n   📍 Node: {node.hostname}")
            print(f"      Site: {node.site}")
            print(f"      Resources: {node.capacity.cpu}c/{node.capacity.ram}G/{node.capacity.disk}G")
            
            # Show DPUs
            if node.pci.dpu:
                print(f"      DPUs: {len(node.pci.dpu)}")
                for dpu_name, dpu in node.pci.dpu.items():
                    print(f"         • {dpu.name} ({dpu.model}) - {len(dpu.interfaces)} interfaces")
            
            # Show NICs
            if node.pci.network:
                print(f"      NICs: {len(node.pci.network)}")
                for nic_name, nic in node.pci.network.items():
                    print(f"         • {nic.name} ({nic.model}) - {len(nic.interfaces)} interfaces")
            
            # Show other hardware
            if node.pci.gpu:
                print(f"      GPUs: {len(node.pci.gpu)}")
            if node.pci.fpga:
                print(f"      FPGAs: {len(node.pci.fpga)}")
            if node.pci.nvme:
                print(f"      NVMe: {len(node.pci.nvme)}")
        
        # Show networks
        print("\n   🌐 Networks:")
        for network in topology.site_topology_networks.iter_networks():
            print(f"      • {network.name} ({network.type})")
        
        # ====================================================================
        # Step 2: Deploy Slice (or get existing)
        # ====================================================================
        if args.skip_deployment:
            print_section("🔄 Step 2: Retrieving Existing Slice")
            slice = sd.get_slice(args.slice_name)
            if not slice:
                print("❌ Could not retrieve slice. Exiting.")
                return 1
        else:
            print_section("🚀 Step 2: Deploying Slice to FABRIC")
            
            print(f"Creating slice: {args.slice_name}")
            slice = sd.deploy_topology_to_fabric(
                topology=topology,
                slice_name=args.slice_name,
                use_timestamp=False
            )
            
            if not slice:
                print("❌ Slice deployment failed")
                return 1
            
            # Wait for slice to become active
            if not wait_for_slice(slice):
                print("❌ Slice failed to become active")
                return 1
        
        # ====================================================================
        # Step 3: Configure L3 Networks (if any)
        # ====================================================================
        has_l3_networks = any(
            net.is_orchestrator_managed() 
            for net in topology.site_topology_networks.iter_networks()
        )
        
        if has_l3_networks:
            print_section("🌐 Step 3: Configuring L3 Networks")
            try:
                sd.configure_l3_networks(slice, topology)
                print("✅ L3 networks configured")
            except Exception as e:
                print(f"❌ L3 network configuration failed: {e}")
                return 1
        else:
            print_section("⏭️  Step 3: Skipping L3 Network Configuration")
            print("   No L3 networks in topology (all are L2)")
        
        # ====================================================================
        # Step 4: Configure Node Interfaces
        # ====================================================================
        print_section("🔧 Step 4: Configuring Node Interfaces")
        print("This will configure both NIC and DPU interfaces...")
        
        try:
            snc.configure_node_interfaces(slice, topology)
            print("\n✅ All interfaces configured successfully")
        except Exception as e:
            print(f"\n❌ Interface configuration failed: {e}")
            import traceback
            traceback.print_exc()
            return 1
        
        # ====================================================================
        # Step 5: Verify Interfaces
        # ====================================================================
        print_section("🔍 Step 5: Verifying Interface Configuration")
        
        try:
            snc.verify_node_interfaces(slice, topology)
            print("✅ Interface verification completed")
        except Exception as e:
            print(f"⚠️  Interface verification had issues: {e}")
        
        # ====================================================================
        # Step 6: Setup Passwordless SSH (optional)
        # ====================================================================
        if not args.skip_ssh:
            print_section("🔐 Step 6: Setting Up Passwordless SSH")
            
            try:
                success = ssh.setup_passwordless_ssh(slice)
                if success:
                    print("✅ SSH setup completed")
                else:
                    print("⚠️  SSH setup had some issues")
            except Exception as e:
                print(f"⚠️  SSH setup failed: {e}")
        else:
            print_section("⏭️  Step 6: Skipping SSH Setup")
        
        # ====================================================================
        # Step 7: Test Network Connectivity (optional)
        # ====================================================================
        # Find a network to test
        test_network = args.test_network
        if not test_network:
            # Find first L2 network
            for network in topology.site_topology_networks.iter_networks():
                if network.type in ["L2Bridge", "L2PTP", "L2STS"]:
                    test_network = network.name
                    break
        
        if test_network:
            print_section("📡 Step 7: Testing Network Connectivity")
            
            # Find a node on this network
            nodes_on_network = topology.get_nodes_on_network(test_network)
            if len(nodes_on_network) >= 2:
                source_node = nodes_on_network[0].hostname
                
                print(f"Testing connectivity from {source_node} on {test_network}")
                
                try:
                    results = snc.ping_network_from_node(
                        slice=slice,
                        topology=topology,
                        source_hostname=source_node,
                        network_name=test_network,
                        use_ipv6=False,
                        count=3
                    )
                    
                    if all(results.values()):
                        print("✅ All pings successful!")
                    else:
                        print("⚠️  Some pings failed")
                except Exception as e:
                    print(f"⚠️  Connectivity test failed: {e}")
            else:
                print(f"⚠️  Network {test_network} has fewer than 2 nodes, skipping connectivity test")
        else:
            print_section("⏭️  Step 7: Skipping Connectivity Test")
            print("   No suitable network found for testing")
        
        # ====================================================================
        # Summary
        # ====================================================================
        print_section("🎉 Deployment Complete!")
        
        print("Your slice is now ready with:")
        print("   ✅ All nodes deployed")
        print("   ✅ DPU interfaces configured")
        print("   ✅ NIC interfaces configured")
        if not args.skip_ssh:
            print("   ✅ Passwordless SSH enabled")
        
        print(f"\nSlice name: {args.slice_name}")
        print(f"\nTo manage your slice:")
        print(f"   • View status: slice.show()")
        print(f"   • Delete slice: python -c 'import slice_deployment as sd; sd.delete_slice(\"{args.slice_name}\")'")
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
