# fabric-generic-cluster

A comprehensive, type-safe Python framework for managing FABRIC testbed slices with support for complex network topologies, DPU interfaces, multi-OS configurations, and various hardware components.

[![PyPI version](https://badge.fury.io/py/fabric-generic-cluster.svg)](https://badge.fury.io/py/fabric-generic-cluster)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Pydantic V2](https://img.shields.io/badge/pydantic-v2-orange.svg)](https://docs.pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 Features

### Core Capabilities
- ✅ **Type-Safe Data Models** - Pydantic-based topology definitions with automatic validation
- ✅ **DPU Interface Support** - Full support for DPU network interfaces alongside traditional NICs
- ✅ **Multi-OS Support** - Automatic detection and configuration for Rocky Linux, Ubuntu, and Debian
- ✅ **Hardware Components** - Full support for GPUs, FPGAs, DPUs, NVMe, and custom NICs
- ✅ **Network Management** - L2/L3 network configuration with IPv4/IPv6 support
- ✅ **SSH Automation** - Passwordless SSH setup across all nodes
- ✅ **Visualization** - Multiple output formats (text, ASCII, graphs, tables)
- ✅ **Easy Installation** - Available on PyPI via `pip install`
- ✅ **Modular Design** - Separated concerns for better maintainability

### Hardware Support
- **GPUs** - NVIDIA RTX series, Tesla T4, A30, A40
- **FPGAs** - Xilinx Alveo U280, U50, U250
- **DPUs** - ConnectX-7 100G/400G Data Processing Units with network interfaces
- **NVMe** - Intel P4510, P4610 NVMe storage
- **NICs** - Basic, ConnectX-5, ConnectX-6, SharedNICs, SmartNICs
- **Persistent Storage** - Volume management

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Package Structure](#package-structure)
- [Usage Examples](#usage-examples)
- [API Reference](#api-reference)
- [Command-Line Tools](#command-line-tools)
- [Development](#development)
- [Documentation](#documentation)
- [Contributing](#contributing)

## 🚀 Installation

### From PyPI (Recommended)

```bash
pip install fabric-generic-cluster
```

### From Source

```bash
git clone https://github.com/mcevik0/fabric-generic-cluster.git
cd fabric-generic-cluster
pip install -e .
```

### Prerequisites

- Python 3.9 or higher
- Access to FABRIC testbed
- `fabrictestbed-extensions>=1.4.0` (installed automatically)

### Verify Installation

```python
import fabric_generic_cluster
print(fabric_generic_cluster.__version__)
```

## 🎯 Quick Start

### Option 1: Python Script

```python
from fabric_generic_cluster import (
    load_topology_from_yaml_file,
    deploy_topology_to_fabric,
    configure_l3_networks,
    configure_node_interfaces,
    setup_passwordless_ssh,
)

# Load topology
topology = load_topology_from_yaml_file("topology.yaml")

# Deploy to FABRIC
slice = deploy_topology_to_fabric(topology, "my-cluster")

# Configure networks (if using L3 networks)
configure_l3_networks(slice, topology)

# Configure interfaces
configure_node_interfaces(slice, topology)

# Setup SSH
setup_passwordless_ssh(slice)

print("✅ Cluster deployed and configured!")
```

### Option 2: Using the Example Script

```bash
# Clone the repository for examples
git clone https://github.com/mcevik0/fabric-generic-cluster.git
cd fabric-generic-cluster

# Run the complete deployment example
python examples/complete-deployment-example.py \
    --yaml path/to/topology.yaml \
    --slice-name my-test-slice
```

### Option 3: Jupyter Notebooks

For interactive workflows, check out the [fabric-generic-cluster-notebooks](https://github.com/mcevik0/fabric-generic-cluster-notebooks) repository:

```bash
git clone https://github.com/mcevik0/fabric-generic-cluster-notebooks.git
cd fabric-generic-cluster-notebooks
jupyter notebook
```

## 📦 Package Structure

```
fabric-generic-cluster/
├── fabric_generic_cluster/          # Main package
│   ├── __init__.py                  # Package exports
│   ├── models.py                    # Pydantic models for topology
│   ├── deployment.py                # Slice deployment functions
│   ├── network_config.py            # Network configuration
│   ├── ssh_setup.py                 # SSH management
│   ├── topology_viewer.py           # Visualization tools
│   ├── builder_compat.py            # Backward compatibility
│   └── tools/                       # Command-line tools
│       ├── __init__.py
│       └── topology_summary.py      # Topology summary generator
│
├── examples/                        # Usage examples
│   └── complete-deployment-example.py
│
├── tests/                          # Test suite
│   ├── test-dpu-support.py
│   └── test-fpga-support.py
│
├── pyproject.toml                  # Package metadata
├── setup.py                        # Setup configuration
├── MANIFEST.in                     # Package data
├── LICENSE                         # MIT License
└── README.md                       # This file
```

## 📚 Usage Examples

### Example 1: Load and Explore Topology

```python
from fabric_generic_cluster import (
    load_topology_from_yaml_file,
    print_topology_summary,
    draw_topology_graph,
)

# Load topology
topology = load_topology_from_yaml_file("topology.yaml")

# Print summary
print_topology_summary(topology)

# Create visualization
draw_topology_graph(topology, show_ip=True, save_path="topology.png")
```

### Example 2: Deploy Multi-Site Cluster

```python
from fabric_generic_cluster import (
    load_topology_from_yaml_file,
    deploy_topology_to_fabric,
    configure_node_interfaces,
    verify_node_interfaces,
)

# Load topology with nodes at multiple sites
topology = load_topology_from_yaml_file("multi-site-topology.yaml")

# Deploy
slice = deploy_topology_to_fabric(topology, "multi-site-cluster")

# Configure all nodes
configure_node_interfaces(slice, topology)

# Verify configuration
verify_node_interfaces(slice, topology)
```

### Example 3: Access Type-Safe Data

```python
from fabric_generic_cluster import load_topology_from_yaml_file

topology = load_topology_from_yaml_file("topology.yaml")

# Get specific node
node = topology.get_node_by_hostname("node-1")

print(f"Node: {node.hostname}")
print(f"Site: {node.site}")
print(f"CPU: {node.capacity.cpu} cores")
print(f"RAM: {node.capacity.ram} GB")

# Check hardware components
if node.pci.dpu:
    print(f"DPUs: {len(node.pci.dpu)}")
    for dpu_name, dpu in node.pci.dpu.items():
        print(f"  - {dpu_name}: {dpu.model}")
        print(f"    Interfaces: {len(dpu.interfaces)}")

if node.pci.fpga:
    print(f"FPGAs: {len(node.pci.fpga)}")
    for fpga_name, fpga in node.pci.fpga.items():
        print(f"  - {fpga_name}: {fpga.model}")

# Get all interfaces (NIC + DPU)
all_interfaces = node.get_all_interfaces()
print(f"\nTotal interfaces: {len(all_interfaces)}")

for device_name, iface_name, iface in all_interfaces:
    device_type = "DPU" if device_name.startswith("dpu") else "NIC"
    print(f"{device_type} {device_name}.{iface_name}: {iface.binding}")
```

### Example 4: Test Network Connectivity

```python
from fabric_generic_cluster import (
    get_slice,
    load_topology_from_yaml_file,
    ping_network_from_node,
    verify_ssh_access,
)

# Get existing slice
slice = get_slice("my-cluster")
topology = load_topology_from_yaml_file("topology.yaml")

# Test ping connectivity
ping_results = ping_network_from_node(
    slice, 
    topology, 
    source_hostname="node-1", 
    network_name="network1",
    count=3
)

if all(ping_results.values()):
    print("✅ All ping tests passed!")

# Test SSH access
ssh_results = verify_ssh_access(
    slice,
    topology,
    source_hostname="node-1",
    network_name="network1"
)

if all(ssh_results.values()):
    print("✅ All SSH connections successful!")
```

### Example 5: Using Module-Style Imports

For compatibility with existing code:

```python
from fabric_generic_cluster import deployment as sd
from fabric_generic_cluster import network_config as snc
from fabric_generic_cluster import ssh_setup as ssh
from fabric_generic_cluster import load_topology_from_yaml_file

# Load topology
topology = load_topology_from_yaml_file("topology.yaml")

# Deploy
slice = sd.deploy_topology_to_fabric(topology, "my-slice")

# Configure
snc.configure_node_interfaces(slice, topology)
ssh.setup_passwordless_ssh(slice)
```

## 🔧 API Reference

### Models and Loaders

```python
from fabric_generic_cluster import (
    SiteTopology,              # Main topology model
    Node,                      # Node model
    Network,                   # Network model
    load_topology_from_yaml_file,   # Load from YAML file
    load_topology_from_dict,        # Load from dictionary
)
```

### Deployment Functions

```python
from fabric_generic_cluster import (
    deploy_topology_to_fabric,   # Deploy slice to FABRIC
    configure_l3_networks,        # Configure L3 networks
    get_slice,                    # Get existing slice
    delete_slice,                 # Delete slice
    check_slices,                 # List all slices
)

# Usage
slice = deploy_topology_to_fabric(topology, "slice-name")
configure_l3_networks(slice, topology)
```

### Network Configuration

```python
from fabric_generic_cluster import (
    configure_node_interfaces,    # Configure all interfaces
    verify_node_interfaces,       # Verify configuration
    ping_network_from_node,       # Test connectivity
    update_hosts_file_on_nodes,   # Update /etc/hosts
)

# Usage
configure_node_interfaces(slice, topology)
verify_node_interfaces(slice, topology)
```

### SSH Setup

```python
from fabric_generic_cluster import (
    setup_passwordless_ssh,       # Complete SSH setup
    verify_ssh_access,            # Verify SSH connectivity
)

# Usage
setup_passwordless_ssh(slice)
results = verify_ssh_access(slice, topology, "node-1", "network1")
```

### Visualization

```python
from fabric_generic_cluster import (
    print_topology_summary,       # Detailed summary
    print_compact_summary,        # Brief summary
    draw_topology_graph,          # Visual graph
)

# Usage
print_topology_summary(topology)
draw_topology_graph(topology, show_ip=True, save_path="topology.png")
```

## 🛠️ Command-Line Tools

### Topology Summary Generator

The package includes a command-line tool for generating topology summaries:

```bash
# Generate summary for a YAML file
fabric-topology-summary input.yaml --output output.yaml

# Just print summary without modifying file
fabric-topology-summary input.yaml --dry-run

# Include ASCII diagram
fabric-topology-summary input.yaml --ascii --output output.yaml
```

This tool is automatically installed when you install the package.

## 💻 Development

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/mcevik0/fabric-generic-cluster.git
cd fabric-generic-cluster

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run test suite
pytest tests/

# Run specific test
python tests/test-dpu-support.py
python tests/test-fpga-support.py
```

### Building the Package

```bash
# Install build tools
pip install build twine

# Build distribution
python -m build

# Check package
twine check dist/*

# Test upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

### Code Style

```bash
# Format code
black fabric_generic_cluster/

# Check style
flake8 fabric_generic_cluster/
```

## 📖 Documentation

### Comprehensive Guides

- **Getting Started**: See [Quick Start](#quick-start) above
- **Jupyter Notebooks**: [fabric-generic-cluster-notebooks](https://github.com/mcevik0/fabric-generic-cluster-notebooks)
- **YAML Format**: Detailed topology format documentation in notebooks repository
- **API Reference**: See [API Reference](#api-reference) above

### Example Topologies

Example YAML topology files are available in the [notebooks repository](https://github.com/mcevik0/fabric-generic-cluster-notebooks/tree/main/model):

- Basic 2-node cluster
- Multi-site deployment
- Storage cluster with NVMe
- DPU/SmartNIC configurations
- FPGA-enabled topologies
- OpenStack deployment variants

### YAML Topology Format

```yaml
site_topology:
  nodes:
    node-1:
      hostname: node-1
      site: SITE1
      capacity:
        cpu: 8
        ram: 32
        disk: 100
        os: default_rocky_9
      nics:
        nic1:
          interfaces:
            iface1:
              binding: network1
              ipv4_address: 10.0.1.1
              ipv4_netmask: 255.255.255.0
      pci:
        dpu:
          dpu1:
            model: NIC_ConnectX_7_100
            interfaces:
              iface1:
                binding: network1
                ipv4_address: 10.0.1.10

  networks:
    network1:
      name: network1
      type: L2Bridge
      subnet: 10.0.1.0/24
```

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Report bugs**: Open an issue on GitHub
2. **Suggest features**: Open an issue with your idea
3. **Submit PRs**: Fork, make changes, and submit a pull request

### Contribution Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Workflow

1. Update code in `fabric_generic_cluster/`
2. Add tests in `tests/`
3. Update documentation
4. Run tests: `pytest tests/`
5. Build package: `python -m build`
6. Test locally: `pip install dist/*.whl`

## 📊 Performance

- **Validation Speed**: ~10ms for typical topology (3-10 nodes)
- **Deployment Time**: Depends on FABRIC (typically 5-10 minutes)
- **Network Config**: ~30 seconds per node
- **SSH Setup**: ~1-2 minutes for 3-node cluster

## 🗺️ Roadmap

- [x] Type-safe Pydantic models
- [x] DPU interface support
- [x] Multi-distro support (Rocky/Ubuntu/Debian)
- [x] L2/L3 network configuration
- [x] Automated SSH setup
- [x] PyPI package distribution
- [ ] Web-based topology editor
- [ ] Ansible playbook integration
- [ ] Monitoring and metrics collection
- [ ] REST API endpoint

## 🐛 Troubleshooting

### Import Issues

**Problem**: `ModuleNotFoundError: No module named 'fabric_generic_cluster'`

**Solution**: 
```bash
pip install fabric-generic-cluster
```

### YAML File Not Found

**Problem**: `FileNotFoundError` when loading topology

**Solution**: Use absolute paths or ensure YAML file is in current directory:
```python
from pathlib import Path

yaml_file = Path("path/to/topology.yaml")
topology = load_topology_from_yaml_file(str(yaml_file))
```

### DPU Interfaces Not Detected

**Problem**: DPU interfaces not showing up

**Solution**: Verify DPU configuration in YAML:
```python
node = topology.get_node_by_hostname("node-1")
print(f"DPUs: {node.pci.dpu}")

# Check all interfaces
all_ifaces = node.get_all_interfaces()
print(f"Total interfaces: {len(all_ifaces)}")
```

### Network Configuration Fails

**Problem**: Interface configuration errors

**Solution**: 
1. Check L3 networks are configured first: `configure_l3_networks(slice, topology)`
2. Ensure nodes are active: `slice.wait()`
3. Verify OS detection: Check logs for supported distro

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for the [FABRIC Testbed](https://fabric-testbed.net/)
- Uses [Pydantic](https://docs.pydantic.dev/) for data validation
- Network visualization with [NetworkX](https://networkx.org/) and [Matplotlib](https://matplotlib.org/)

## 📞 Support

- 📧 **Issues**: [GitHub Issues](https://github.com/mcevik0/fabric-generic-cluster/issues)
- 📚 **Documentation**: [fabric-generic-cluster-notebooks](https://github.com/mcevik0/fabric-generic-cluster-notebooks)
- 💬 **FABRIC Slack**: [FABRIC Workspace](https://fabric-testbed.slack.com)
- 🌐 **FABRIC Help**: [FABRIC Learn](https://learn.fabric-testbed.net/)

## 📦 Related Repositories

- **Jupyter Notebooks**: [fabric-generic-cluster-notebooks](https://github.com/mcevik0/fabric-generic-cluster-notebooks) - Example notebooks and topology files
- **PyPI Package**: [fabric-generic-cluster](https://pypi.org/project/fabric-generic-cluster/) - Install via pip

## 🔗 Links

- **GitHub**: https://github.com/mcevik0/fabric-generic-cluster
- **PyPI**: https://pypi.org/project/fabric-generic-cluster/
- **Documentation**: https://github.com/mcevik0/fabric-generic-cluster-notebooks
- **FABRIC Testbed**: https://fabric-testbed.net/

---

**Made with ❤️ for the FABRIC Community**

**Author**: Mert Cevik ([@mcevik0](https://github.com/mcevik0))
