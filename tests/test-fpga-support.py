#!/usr/bin/env python3
"""
Test script to verify FPGA support in the refactored framework.
"""
import sys
sys.path.insert(0, '..')  # Add parent directory to path


from slice_utils_models import load_topology_from_yaml_file
import slice_topology_viewer as viewer
from pathlib import Path


def test_fpga_loading():
    """Test loading topology with FPGA devices."""
    print("="*70)
    print("Test 1: Load Topology with FPGA")
    print("="*70)
    
    yaml_file = "../model/_slice_topology.yaml"
    
    if not Path(yaml_file).exists():
        print(f"❌ Test file not found: {yaml_file}")
        return False
    
    try:
        topology = load_topology_from_yaml_file(yaml_file)
        print(f"✅ Topology loaded successfully")
        print(f"   Nodes: {len(topology.site_topology_nodes.nodes)}")
        print(f"   Networks: {len(topology.site_topology_networks.networks)}")
        return True
    except Exception as e:
        print(f"❌ Failed to load topology: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fpga_access():
    """Test accessing FPGA data from model."""
    print("\n" + "="*70)
    print("Test 2: Access FPGA Data")
    print("="*70)
    
    try:
        topology = load_topology_from_yaml_file("../model/_slice_topology.yaml")
        
        # Check node1 which has FPGA
        node1 = topology.site_topology_nodes.nodes.get("node1")
        
        if not node1:
            print("❌ Node1 not found in topology")
            return False
        
        print(f"\n🖥️  Node: {node1.hostname}")
        print(f"   Site: {node1.site}")
        
        # Check for FPGAs
        if node1.pci.fpga:
            print(f"\n   FPGAs found: {len(node1.pci.fpga)}")
            for fpga_id, fpga in node1.pci.fpga.items():
                print(f"   ✅ FPGA ID: {fpga_id}")
                print(f"      Name: {fpga.name}")
                print(f"      Model: {fpga.model}")
        else:
            print("   ⚠️  No FPGAs found on node1")
            return False
        
        # Check node2 which has no FPGA
        node2 = topology.site_topology_nodes.nodes.get("node2")
        if node2:
            print(f"\n🖥️  Node: {node2.hostname}")
            if not node2.pci.fpga:
                print(f"   ✅ No FPGAs (as expected)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error accessing FPGA data: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_topology_summary_with_fpga():
    """Test topology summary generation with FPGA."""
    print("\n" + "="*70)
    print("Test 3: Generate Topology Summary with FPGA")
    print("="*70)
    
    try:
        topology = load_topology_from_yaml_file("../model/_slice_topology.yaml")
        
        # Test compact summary
        print("\n📋 Compact Summary:")
        viewer.print_compact_summary(topology)
        
        # Test detailed summary
        print("\n📋 Detailed Summary (first node only):")
        node1 = list(topology.site_topology_nodes.nodes.values())[0]
        print(f"\n🔸 Node: {node1.hostname}")
        print(f"   Resources: {node1.capacity.cpu}c/{node1.capacity.ram}G/{node1.capacity.disk}G")
        
        if node1.pci.fpga:
            print(f"   FPGAs:")
            for fpga_id, fpga in node1.pci.fpga.items():
                print(f"      └─ {fpga.name} ({fpga.model})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_yaml_summary_generation():
    """Test YAML summary generation with FPGA."""
    print("\n" + "="*70)
    print("Test 4: Generate YAML Summary with FPGA")
    print("="*70)
    
    try:
        topology = load_topology_from_yaml_file("../model/_slice_topology.yaml")
        
        # Generate summary
        summary = viewer.generate_yaml_summary(topology, include_ascii=False)
        
        # Check if FPGA is mentioned in summary
        if "FPGA" in summary or "fpga" in summary:
            print("✅ FPGA information included in YAML summary")
            print("\n📄 Summary preview (first 50 lines):")
            lines = summary.split('\n')[:50]
            print('\n'.join(lines))
        else:
            print("⚠️  FPGA not found in generated summary")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating YAML summary: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_model_validation():
    """Test that FPGA validation works."""
    print("\n" + "="*70)
    print("Test 5: FPGA Model Validation")
    print("="*70)
    
    from slice_utils_models import FPGA, PCIDevices
    
    try:
        # Valid FPGA
        fpga = FPGA(name="fpga1", model="FPGA_Xilinx_U280")
        print(f"✅ Valid FPGA created: {fpga.name} ({fpga.model})")
        
        # FPGA in PCIDevices
        pci = PCIDevices(
            fpga={"fpga1": fpga},
            gpu={},
            nvme={},
            network={}
        )
        print(f"✅ PCIDevices with FPGA created successfully")
        print(f"   FPGAs: {len(pci.fpga)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all FPGA tests."""
    print("\n" + "🔬 " + "="*66)
    print("FPGA Support Test Suite")
    print("="*70 + "\n")
    
    tests = [
        ("Load Topology with FPGA", test_fpga_loading),
        ("Access FPGA Data", test_fpga_access),
        ("Topology Summary with FPGA", test_topology_summary_with_fpga),
        ("YAML Summary Generation", test_yaml_summary_generation),
        ("Model Validation", test_model_validation),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! FPGA support is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit(main())
