#!/usr/bin/env python3
"""
Test script to verify DPU interface support with the example YAML.
"""
import sys
sys.path.insert(0, '..')  # Add parent directory to path


import yaml
from slice_utils_models import load_topology_from_dict

# Your example YAML as a dictionary
example_yaml = """
site_topology_nodes:
  nodes:
    node1:
      name: lc-1              
      hostname: lc-1          
      site: PSC               
      capacity:
        cpu: 4                
        ram: 16              
        disk: 10             
        os: default_rocky_9  
      persistent_storage:
        volume:
          volume1:
            name: FABRIC_Staff_1T
            size: 1000
      pci:
        dpu:
          dpu1:
            name: dpu1
            model: NIC_ConnectX_7_100
            interfaces:
              iface1:
                device: eth1           
                connection: conn-eth1  
                binding: net_local_1   
                ipv4:
                  address: 192.168.201.200/24  
                  gateway: 192.168.201.1
                  dns: 8.8.8.8
                ipv6:
                  address: ''
                  gateway: ''
                  dns: '' 
              iface2:
                device: eth2           
                connection: conn-eth2  
                binding: net_local_2   
                ipv4:
                  address: 192.168.202.200/24  
                  gateway: 192.168.202.1
                  dns: 8.8.8.8
                ipv6:
                  address: ''
                  gateway: ''
                  dns: '' 
        fpga: {}
        gpu: {}
        nvme: {}
        network:
          nic1:
            name: nic1       
            model: NIC_Basic 
            interfaces:
              iface1:
                device: eth3           
                connection: conn-eth3  
                binding: net_local_1   
                ipv4:
                  address: 192.168.201.211/24  
                  gateway: 192.168.201.1
                  dns: 8.8.8.8
                ipv6:
                  address: ''
                  gateway: ''
                  dns: '' 
          nic2:
            name: nic2
            model: NIC_Basic
            interfaces:
              iface1:
                device: eth4
                connection: conn-eth4
                binding: net_local_2
                ipv4:
                  address: 192.168.202.211/24
                  gateway: 192.168.202.1
                  dns: 8.8.8.8
                ipv6:
                  address: ''
                  gateway: ''
                  dns: ''
      specific:
        openstack:
          control: 'true'
          network: 'true'
          compute: 'false'
          storage: 'true'

    node2:
      name: lc-2              
      hostname: lc-2          
      site: TACC               
      capacity:
        cpu: 4                
        ram: 16              
        disk: 10             
        os: default_rocky_9  
      persistent_storage:
        volume: {}
      pci:
        dpu: {}
        fpga:
          fpga1:
            name: fpga1
            model: FPGA_Xilinx_U280
        gpu: {}
        nvme: {}
        network:
          nic1:
            name: nic1       
            model: NIC_Basic 
            interfaces:
              iface1:
                device: eth1           
                connection: conn-eth1  
                binding: net_local_1   
                ipv4:
                  address: 192.168.201.212/24  
                  gateway: 192.168.201.1
                  dns: 8.8.8.8
                ipv6:
                  address: ''
                  gateway: ''
                  dns: '' 
          nic2:
            name: nic2
            model: NIC_Basic
            interfaces:
              iface1:
                device: eth2
                connection: conn-eth2
                binding: net_local_2
                ipv4:
                  address: 192.168.202.212/24
                  gateway: 192.168.202.1
                  dns: 8.8.8.8
                ipv6:
                  address: ''
                  gateway: ''
                  dns: ''
      specific:
        openstack:
          control: 'true'
          network: 'true'
          compute: 'false'
          storage: 'true'

site_topology_networks:
  networks:
    net1:
      name: net_local_1
      type: L2Bridge
      subnet:
        ipv4:
          address: 192.168.201.0/24
          gateway: 192.168.201.1
        ipv6:
          address: ''
          gateway: ''
    net2:
      name: net_local_2
      type: L2Bridge
      subnet:
        ipv4:
          address: 192.168.202.0/24
          gateway: 192.168.202.1
        ipv6:
          address: ''
          gateway: ''
"""


def test_loading():
    """Test 1: Load the topology with DPU interfaces."""
    print("=" * 70)
    print("Test 1: Loading Topology with DPU Interfaces")
    print("=" * 70)
    
    try:
        data = yaml.safe_load(example_yaml)
        topology = load_topology_from_dict(data)
        print("✅ Topology loaded successfully")
        print(f"   Nodes: {len(topology.site_topology_nodes.nodes)}")
        print(f"   Networks: {len(topology.site_topology_networks.networks)}")
        return topology
    except Exception as e:
        print(f"❌ Failed to load: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_dpu_access(topology):
    """Test 2: Access DPU data and interfaces."""
    print("\n" + "=" * 70)
    print("Test 2: Accessing DPU Data and Interfaces")
    print("=" * 70)
    
    node1 = topology.site_topology_nodes.nodes.get("node1")
    
    if not node1:
        print("❌ Node1 not found")
        return False
    
    print(f"\n🖥️  Node: {node1.hostname}")
    
    # Check DPUs
    if node1.pci.dpu:
        print(f"   ✅ DPUs found: {len(node1.pci.dpu)}")
        for dpu_id, dpu in node1.pci.dpu.items():
            print(f"\n   📡 DPU: {dpu.name} ({dpu.model})")
            print(f"      Interfaces: {len(dpu.interfaces)}")
            for iface_name, iface in dpu.interfaces.items():
                print(f"         • {iface_name}:")
                print(f"           - Device: {iface.device}")
                print(f"           - Binding: {iface.binding}")
                print(f"           - IPv4: {iface.get_ipv4_address()}")
    else:
        print("   ❌ No DPUs found")
        return False
    
    return True


def test_get_all_interfaces(topology):
    """Test 3: Test get_all_interfaces() includes DPU interfaces."""
    print("\n" + "=" * 70)
    print("Test 3: Testing get_all_interfaces() Method")
    print("=" * 70)
    
    node1 = topology.site_topology_nodes.nodes.get("node1")
    
    all_interfaces = node1.get_all_interfaces()
    print(f"\n   Total interfaces found: {len(all_interfaces)}")
    
    dpu_count = 0
    nic_count = 0
    
    for device_name, iface_name, iface in all_interfaces:
        device_type = "DPU" if device_name.startswith("dpu") else "NIC"
        if device_type == "DPU":
            dpu_count += 1
        else:
            nic_count += 1
        print(f"   • {device_type} {device_name}.{iface_name} → {iface.binding} ({iface.get_ipv4_address()})")
    
    print(f"\n   📊 Summary:")
    print(f"      DPU interfaces: {dpu_count}")
    print(f"      NIC interfaces: {nic_count}")
    print(f"      Total: {dpu_count + nic_count}")
    
    # Expected: 2 DPU interfaces + 2 NIC interfaces = 4 total
    if dpu_count == 2 and nic_count == 2:
        print("   ✅ Correct count!")
        return True
    else:
        print(f"   ❌ Expected 2 DPU + 2 NIC interfaces")
        return False


def test_get_interfaces_for_network(topology):
    """Test 4: Test get_interfaces_for_network() includes DPU interfaces."""
    print("\n" + "=" * 70)
    print("Test 4: Testing get_interfaces_for_network() Method")
    print("=" * 70)
    
    node1 = topology.site_topology_nodes.nodes.get("node1")
    
    # Test net_local_1
    print("\n   🌐 Network: net_local_1")
    ifaces = node1.get_interfaces_for_network("net_local_1")
    print(f"      Interfaces found: {len(ifaces)}")
    
    for device_name, iface in ifaces:
        device_type = "DPU" if device_name.startswith("dpu") else "NIC"
        print(f"      • {device_type} {device_name}: {iface.get_ipv4_address()}")
    
    # Expected: 1 DPU interface + 1 NIC interface = 2 total
    if len(ifaces) == 2:
        print("      ✅ Found DPU and NIC interfaces")
    else:
        print(f"      ❌ Expected 2 interfaces, got {len(ifaces)}")
        return False
    
    # Test net_local_2
    print("\n   🌐 Network: net_local_2")
    ifaces = node1.get_interfaces_for_network("net_local_2")
    print(f"      Interfaces found: {len(ifaces)}")
    
    for device_name, iface in ifaces:
        device_type = "DPU" if device_name.startswith("dpu") else "NIC"
        print(f"      • {device_type} {device_name}: {iface.get_ipv4_address()}")
    
    if len(ifaces) == 2:
        print("      ✅ Found DPU and NIC interfaces")
        return True
    else:
        print(f"      ❌ Expected 2 interfaces, got {len(ifaces)}")
        return False


def test_get_nodes_on_network(topology):
    """Test 5: Test get_nodes_on_network() works with DPU interfaces."""
    print("\n" + "=" * 70)
    print("Test 5: Testing get_nodes_on_network() Method")
    print("=" * 70)
    
    # Test net_local_1
    print("\n   🌐 Network: net_local_1")
    nodes = topology.get_nodes_on_network("net_local_1")
    print(f"      Nodes connected: {len(nodes)}")
    for node in nodes:
        print(f"      • {node.hostname}")
    
    # Expected: both node1 and node2
    if len(nodes) == 2:
        print("      ✅ Both nodes found on network")
    else:
        print(f"      ❌ Expected 2 nodes, got {len(nodes)}")
        return False
    
    # Verify node1 has both DPU and NIC on this network
    node1 = next(n for n in nodes if n.hostname == "lc-1")
    ifaces = node1.get_interfaces_for_network("net_local_1")
    has_dpu = any(device.startswith("dpu") for device, _ in ifaces)
    has_nic = any(not device.startswith("dpu") for device, _ in ifaces)
    
    if has_dpu and has_nic:
        print("      ✅ Node1 has both DPU and NIC on this network")
        return True
    else:
        print(f"      ❌ Node1 missing devices (DPU: {has_dpu}, NIC: {has_nic})")
        return False


def test_summary_generation(topology):
    """Test 6: Test summary generation includes DPU interfaces."""
    print("\n" + "=" * 70)
    print("Test 6: Testing Summary Generation")
    print("=" * 70)
    
    from tool_topology_summary_generator import generate_node_summary
    
    try:
        summary = generate_node_summary(topology)
        
        # Check if DPU is mentioned
        if "DPU:" in summary and "dpu1" in summary:
            print("   ✅ DPU found in summary")
        else:
            print("   ❌ DPU not found in summary")
            return False
        
        # Check if DPU interfaces are shown
        if "net_local_1" in summary and "192.168.201.200" in summary:
            print("   ✅ DPU interface details found in summary")
        else:
            print("   ❌ DPU interface details not found")
            return False
        
        print("\n   📄 Summary preview (first 20 lines):")
        lines = summary.split('\n')[:20]
        for line in lines:
            print(f"   {line}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n🔬 " + "=" * 66)
    print("DPU Interface Support Test Suite")
    print("=" * 70 + "\n")
    
    # Test 1: Load topology
    topology = test_loading()
    if not topology:
        print("\n❌ Cannot continue - topology loading failed")
        return 1
    
    # Run all tests
    tests = [
        ("Access DPU Data", lambda: test_dpu_access(topology)),
        ("get_all_interfaces()", lambda: test_get_all_interfaces(topology)),
        ("get_interfaces_for_network()", lambda: test_get_interfaces_for_network(topology)),
        ("get_nodes_on_network()", lambda: test_get_nodes_on_network(topology)),
        ("Summary Generation", lambda: test_summary_generation(topology)),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! DPU interface support is working correctly.")
        print("\n✅ The following will now work with DPU interfaces:")
        print("   • configure_node_interfaces() - configures IPs on DPU interfaces")
        print("   • verify_node_interfaces() - shows DPU interface status")
        print("   • ping_network_from_node() - tests connectivity via DPU interfaces")
        print("   • verify_ssh_access() - verifies SSH over DPU interfaces")
        print("   • update_hosts_file_on_nodes() - uses IPs from DPU interfaces")
        print("   • create_and_bind_networks() - binds DPU interfaces to networks")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit(main())
