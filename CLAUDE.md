# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`fabric-generic-cluster` is a Python library (published on PyPI) for managing [FABRIC testbed](https://fabric-testbed.net/) slices. It provides type-safe Pydantic models for topology definitions and functions for deploying, configuring, and managing clusters on the FABRIC testbed.

## Development Setup

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

## Common Commands

```bash
# Format code
black fabric_generic_cluster/

# Lint
flake8 fabric_generic_cluster/

# Run tests
pytest tests/

# Run a specific test
python tests/test-dpu-support.py

# Build distribution package
python -m build

# Check built package
twine check dist/*

# CLI tool (installed with the package)
fabric-topology-summary input.yaml --output output.yaml
fabric-topology-summary input.yaml --dry-run
fabric-topology-summary input.yaml --ascii --output output.yaml
```

## Architecture

The package is structured into focused modules under `fabric_generic_cluster/`:

### Data Flow

1. **YAML topology file** → `models.load_topology_from_yaml_file()` → **`SiteTopology` Pydantic model**
2. **`SiteTopology`** → `deployment.deploy_topology_to_fabric()` → **FABRIC slice object** (from `fabrictestbed-extensions`)
3. **FABRIC slice** + **`SiteTopology`** → `network_config` / `ssh_setup` / `ansible_setup` functions → **configured cluster**

### Key Modules

- **`models.py`** — All Pydantic v2 data models. The hierarchy is `SiteTopology → SiteTopologyNodes/Networks/FacilityPorts → Node/Network/FacilityPort → PCIDevices/NIC/DPU/FPGA/GPU/NVMe → Interface`. `Node.get_all_interfaces()` returns interfaces from NICs, DPUs, and FPGAs uniformly.

- **`deployment.py`** — Creates FABRIC slices from topology models. Handles node provisioning, hardware component attachment (GPU, DPU, FPGA, NVMe, NICs), and facility port setup. Wraps `fabrictestbed-extensions` (`FablibManager`).

- **`network_config.py`** — Configures IP addresses on node interfaces after slice is active. Handles L2 (manual IP) and L3/orchestrator-managed (IPv4/IPv6/Ext) network types differently. Detects and supports Rocky Linux, Ubuntu, and Debian.

- **`ssh_setup.py`** — Sets up passwordless SSH between nodes and verifies connectivity.

- **`ansible_setup.py`** — Installs Ansible on the control node (detected via `node.specific.is_ansible_control()`), generates inventory files from topology models, and runs connectivity tests.

- **`selinux_management.py`** — Checks and sets SELinux mode (enforcing/permissive/disabled) across nodes. Primarily relevant for Rocky Linux nodes used in OpenStack deployments.

- **`topology_viewer.py`** — Visualization using NetworkX + Matplotlib. Provides text summaries and graph rendering.

- **`builder_compat.py`** — Backward-compatibility shim that accepts either raw dicts or `SiteTopology` objects and delegates to the main modules. Allows legacy code that passes topology as a dict to keep working.

- **`tools/topology_summary.py`** — Implements the `fabric-topology-summary` CLI entrypoint. Generates a descriptive comment header and optionally injects it into the YAML file.

### Network Types

- **L2Bridge / L2PTP / L2STS** — Manual IP configuration required (`network_config` handles this)
- **IPv4 / IPv6 / IPv4Ext / IPv6Ext** — Orchestrator-managed; IPs are assigned automatically by FABRIC, not configured by the library

### YAML Topology Format

The YAML structure maps directly to the Pydantic models:

```yaml
site_topology_nodes:
  nodes:
    node-1:
      name: node-1
      hostname: node-1
      site: MGHPCC
      capacity:
        cpu: 8
        ram: 32
        disk: 100
        os: default_rocky_9
      pci:
        network:
          nic1:
            name: nic1
            model: NIC_Basic
            interfaces:
              iface1:
                device: eth1
                connection: con1
                binding: network1
                ipv4:
                  address: 10.0.1.1/24
        dpu:
          dpu1:
            name: dpu1
            model: NIC_ConnectX_7_100
            interfaces:
              iface1:
                device: eth0
                connection: con0
                binding: network1
      specific:
        ansible:
          control: "true"
          role: controller
          management_network: fabnetv4-mgmt
        selinux:
          mode: permissive

site_topology_networks:
  networks:
    network1:
      name: network1
      type: L2Bridge
      subnet:
        ipv4:
          address: 10.0.1.0/24
          gateway: 10.0.1.254

site_topology_facility_ports:
  facility_ports:
    fp1:
      name: SENSE-MGHPCC
      site: MGHPCC
      vlan: 100
      binding: network1
```

### Public API (`__init__.py`)

All user-facing functions are re-exported from `__init__.py`. The `__all__` list is the authoritative public API surface. When adding new public functions, export them here.
