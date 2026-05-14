"""
resources.py — FABRIC resource discovery utilities

Provides site-level and host-level resource queries, and topology
validation / host-matching functions for use with the FABRIC testbed.

Public API
----------
Section 11 — General resource queries:
    get_sites_dataframe(fablib, force_refresh)
    find_sites_with_resources(fablib, ...)
    find_hosts_with_resources(fablib, ...)

Section 12 — Topology-aware validation:
    validate_topology(fablib, topology, sites_prefer, return_data)
    find_hosts_for_topology(fablib, topology, sites_prefer, sites_avoid, ...)
"""

import uuid
import pandas as pd
from typing import List

# ── Site / host DataFrame helper ─────────────────────────────────────────────

def get_sites_dataframe(fablib, force_refresh=False):
    """
    Get all FABRIC sites with their resources as a DataFrame.
    
    Args:
        fablib: FablibManager instance
        
    Returns:
        pandas.DataFrame with site information and resources
    """
    resources = fablib.get_resources(force_refresh=force_refresh)
    sites_list = []

    for site_name in resources.sites:
        site = resources.sites[site_name]
        
        # Build site dictionary
        site_dict = {'name': site_name}
        
        # Basic attributes
        try:
            site_dict['state'] = site.get_state()
        except:
            site_dict['state'] = None
        
        # Get location info
        try:
            location = site.get_location_postal()
            site_dict['address'] = location
        except:
            site_dict['address'] = None
        
        # Get basic resources
        try:
            site_dict['cores_available'] = site.get_core_available()
            site_dict['cores_capacity'] = site.get_core_capacity()
            site_dict['cores_allocated'] = site.get_core_allocated()
            
            site_dict['ram_available'] = site.get_ram_available()
            site_dict['ram_capacity'] = site.get_ram_capacity()
            site_dict['ram_allocated'] = site.get_ram_allocated()
            
            site_dict['disk_available'] = site.get_disk_available()
            site_dict['disk_capacity'] = site.get_disk_capacity()
            site_dict['disk_allocated'] = site.get_disk_allocated()
        except:
            pass
        
        # Get component info from site_info (NICs, GPUs, FPGAs, NVMe, etc.)
        try:
            site_info = site.site_info
            for component_name, component_data in site_info.items():
                if isinstance(component_data, dict) and 'capacity' in component_data:
                    # Create columns for each component
                    site_dict[f'{component_name}_capacity'] = component_data.get('capacity', 0)
                    site_dict[f'{component_name}_allocated'] = component_data.get('allocated', 0)
                    site_dict[f'{component_name}_available'] = (
                        component_data.get('capacity', 0) - component_data.get('allocated', 0)
                    )
        except Exception as e:
            pass
        
        sites_list.append(site_dict)

    return pd.DataFrame(sites_list)

# ── Shared resource field map (Section 11) ───────────────────────────────────

# ── Shared resource field map ─────────────────────────────────────────────────
# Single source of truth for every resource type understood by the finder
# functions.  Each row is:
#   (param_name, display_label, site_field, host_field)
#
# site_field  : column name produced by get_sites_dataframe()
# host_field  : field name used by fablib.list_hosts()
#
# NOTE: GPU names differ between the two levels — the map makes that explicit.
# ─────────────────────────────────────────────────────────────────────────────

_RESOURCE_FIELD_MAP = [
    # param_name               label                  site_field                           host_field
    ('min_cores',               'Cores',               'cores_available',                   'cores_available'),
    ('min_ram',                 'RAM (GB)',             'ram_available',                     'ram_available'),
    ('min_disk',                'Disk (GB)',            'disk_available',                    'disk_available'),
    ('smartnic_connectx_5',     'SmartNIC ConnectX-5', 'smartnic-connectx-5_available',     'smartnic-connectx-5_available'),
    ('smartnic_connectx_6',     'SmartNIC ConnectX-6', 'smartnic-connectx-6_available',     'smartnic-connectx-6_available'),
    ('smartnic_connectx_7_100', 'SmartNIC CX7-100G',   'smartnic-connectx-7-100_available', 'smartnic-connectx-7-100_available'),
    ('smartnic_connectx_7_400', 'SmartNIC CX7-400G',   'smartnic-connectx-7-400_available', 'smartnic-connectx-7-400_available'),
    ('sharednic_connectx_6',    'SharedNIC ConnectX-6','sharednic-connectx-6_available',    'sharednic-connectx-6_available'),
    ('gpu_rtx6000',             'RTX6000',             'gpu-rtx6000_available',             'rtx6000_available'),
    ('gpu_a30',                 'A30',                 'gpu-a30_available',                 'a30_available'),
    ('gpu_a40',                 'A40',                 'gpu-a40_available',                 'a40_available'),
    ('gpu_tesla_t4',            'Tesla T4',            'gpu-tesla t4_available',            'tesla_t4_available'),
    ('fpga_u280',               'U280 FPGA',           'fpga-xilinx-u280_available',        'fpga-xilinx-u280_available'),
    ('nvme',                    'NVMe',                'nvme-p4510_available',              'nvme-p4510_available'),
]

# Quick lookup: param_name -> (label, site_field, host_field)
_FIELD_LOOKUP = {p: (lbl, sf, hf) for p, lbl, sf, hf in _RESOURCE_FIELD_MAP}


def _print_criteria(level, criteria):
    """Print a formatted search-criteria header (shared by both finder functions)."""
    print(f"\U0001f50e Searching for {level} with:")
    for param, (label, *_) in _FIELD_LOOKUP.items():
        val = criteria.get(param, 0)
        if val:
            print(f"   \u2022 {label}: >= {val}")
    print()

def find_sites_with_resources(
    fablib,
    min_cores=0,
    min_ram=0,
    min_disk=0,
    smartnic_connectx_5=0,
    smartnic_connectx_6=0,
    smartnic_connectx_7_100=0,
    smartnic_connectx_7_400=0,
    sharednic_connectx_6=0,
    gpu_rtx6000=0,
    gpu_a30=0,
    gpu_a40=0,
    gpu_tesla_t4=0,
    fpga_u280=0,
    nvme=0,
    verbose=True,
    force_refresh=False,
    return_data=False
):
    """
    Find FABRIC sites matching resource criteria.

    Each returned row represents one site whose *aggregate* available
    resources satisfy all specified thresholds.

    Args:
        fablib: FablibManager instance
        min_cores / min_ram / min_disk: minimum compute resources
        smartnic_connectx_5/6/7_100/7_400: minimum SmartNIC counts
        sharednic_connectx_6: minimum SharedNIC count
        gpu_rtx6000 / gpu_a30 / gpu_a40 / gpu_tesla_t4: minimum GPU counts
        fpga_u280: minimum FPGA count
        nvme: minimum NVMe device count
        verbose: print search criteria header
        force_refresh: bypass the cache and fetch live data from the testbed
        return_data: if True, return the filtered DataFrame for programmatic use

    Returns:
        pandas.DataFrame if return_data=True, else None
    """
    # Collect criteria into a dict keyed by param name
    criteria = {p: v for p, v in locals().items() if p in _FIELD_LOOKUP}

    if verbose:
        _print_criteria('sites', criteria)

    sites_df = get_sites_dataframe(fablib, force_refresh=force_refresh)

    def safe_get(row, col, default=0):
        val = row.get(col, default)
        return default if pd.isna(val) else val

    def filter_func(row):
        return all(
            safe_get(row, site_field) >= criteria[param]
            for param, (_, site_field, _hf) in _FIELD_LOOKUP.items()
        )

    result_df = sites_df[sites_df.apply(filter_func, axis=1)]

    # Build display columns: always show name + state, then requested resources
    display_cols = ['name', 'state'] + [
        site_field
        for param, (_, site_field, _hf) in _FIELD_LOOKUP.items()
        if criteria[param] and site_field in result_df.columns
    ]

    print(f"\u2705 Found {len(result_df)} matching site(s):\n")
    if len(result_df) > 0:
        print(result_df[display_cols].to_string(index=False))
    else:
        print("No sites match the specified criteria.")

    if return_data:
        return result_df

def find_hosts_with_resources(
    fablib,
    min_cores=0,
    min_ram=0,
    min_disk=0,
    smartnic_connectx_5=0,
    smartnic_connectx_6=0,
    smartnic_connectx_7_100=0,
    smartnic_connectx_7_400=0,
    sharednic_connectx_6=0,
    gpu_rtx6000=0,
    gpu_a30=0,
    gpu_a40=0,
    gpu_tesla_t4=0,
    fpga_u280=0,
    nvme=0,
    verbose=True,
    force_refresh=False,
    return_data=False
):
    """
    Find individual FABRIC worker hosts matching resource criteria.

    Each result is a single physical host that satisfies ALL specified
    thresholds on its own (not aggregate across the site).

    Note: GPU field names differ between site-level and host-level APIs;
          _RESOURCE_FIELD_MAP captures both so the caller never needs to
          worry about the difference.

    Args:
        fablib: FablibManager instance
        min_cores / min_ram / min_disk: minimum compute resources
        smartnic_connectx_5/6/7_100/7_400: minimum SmartNIC counts
        sharednic_connectx_6: minimum SharedNIC count
        gpu_rtx6000 / gpu_a30 / gpu_a40 / gpu_tesla_t4: minimum GPU counts
        fpga_u280: minimum FPGA count
        nvme: minimum NVMe device count
        verbose: print search criteria header
        force_refresh: bypass the cache and fetch live data from the testbed
        return_data: if True, return the list of host dicts for programmatic use

    Returns:
        list of dicts if return_data=True, else None
    """
    criteria = {p: v for p, v in locals().items() if p in _FIELD_LOOKUP}

    if verbose:
        _print_criteria('hosts', criteria)

    # Always fetch name + state + compute; add requested resource fields
    host_fields = ['name', 'state', 'cores_available', 'ram_available', 'disk_available'] + [
        host_field
        for param, (_, _sf, host_field) in _FIELD_LOOKUP.items()
        if criteria[param] and host_field not in ('cores_available', 'ram_available', 'disk_available')
    ]

    def host_filter(row):
        return all(
            row.get(host_field, 0) >= criteria[param]
            for param, (_, _sf, host_field) in _FIELD_LOOKUP.items()
        )

    try:
        matching_hosts = fablib.list_hosts(
            fields=host_fields,
            pretty_names=False,
            filter_function=host_filter,
            output='list',
            quiet=True,
            force_refresh=force_refresh
        )
    except Exception as e:
        print(f"\u274c Error querying hosts: {e}")
        return []

    print(f"\u2705 Found {len(matching_hosts)} matching host(s):\n")
    if matching_hosts:
        for host in matching_hosts:
            parts = [f"  {host.get('name', 'N/A')}  |"]
            parts.append(f"cores: {host.get('cores_available', 'N/A')}")
            parts.append(f"ram: {host.get('ram_available', 'N/A')} GB")
            parts.append(f"disk: {host.get('disk_available', 'N/A')} GB")
            for param, (label, _sf, host_field) in _FIELD_LOOKUP.items():
                if criteria[param] and host_field not in ('cores_available', 'ram_available', 'disk_available'):
                    parts.append(f"{label}: {host.get(host_field, 0)}")
            print("  ".join(parts))
    else:
        print("  No individual hosts match the specified criteria.")

    if return_data:
        return matching_hosts

# ── Component model map & topology helpers (Section 12) ─────────────────────

# ── Component model normalisation ─────────────────────────────────────────────
# Maps upper-cased topology model strings to the exact strings that
# fablib's add_component() expects.
_COMPONENT_MODEL_MAP = {
    # GPUs
    'GPU_RTX6000':        'GPU_RTX6000',
    'GPU_TESLAT4':        'GPU_TeslaT4',
    'GPU_TESLA_T4':       'GPU_TeslaT4',
    'GPU_A30':            'GPU_A30',
    'GPU_A40':            'GPU_A40',
    # NICs / DPUs
    'NIC_BASIC':          'NIC_Basic',
    'NIC_CONNECTX_5':     'NIC_ConnectX_5',
    'NIC_CONNECTX_6':     'NIC_ConnectX_6',
    'NIC_CONNECTX_7_100': 'NIC_ConnectX_7_100',
    'NIC_CONNECTX_7_400': 'NIC_ConnectX_7_400',
    # FPGAs
    'FPGA_XILINX_U280':   'FPGA_Xilinx_U280',
    # NVMe
    'NVME_P4510':         'NVME_P4510',
}

def _normalize_model(model_str):
    """Return the canonical fablib component model string."""
    return _COMPONENT_MODEL_MAP.get(
        model_str.upper().replace('-', '_'), model_str
    )


def _build_probe_slice(fablib, topology, sites_prefer):
    """
    Build a temporary (never submitted) slice from a topology model.
    Used exclusively as input to slice.validate().
    """
    probe = fablib.new_slice(name=f'_probe_{uuid.uuid4().hex[:8]}')
    for node in topology.site_topology_nodes.iter_nodes():
        site = node.site if node.site else (sites_prefer[0] if sites_prefer else None)
        fab_node = probe.add_node(
            name=node.hostname,
            site=site,
            cores=node.capacity.cpu,
            ram=node.capacity.ram,
            disk=node.capacity.disk,
        )
        for comp_name, gpu  in node.pci.gpu.items():
            fab_node.add_component(model=_normalize_model(gpu.model),  name=comp_name)
        for comp_name, fpga in node.pci.fpga.items():
            fab_node.add_component(model=_normalize_model(fpga.model), name=comp_name)
        for comp_name, nic  in node.pci.network.items():
            fab_node.add_component(model=_normalize_model(nic.model),  name=comp_name)
        for comp_name, dpu  in node.pci.dpu.items():
            fab_node.add_component(model=_normalize_model(dpu.model),  name=comp_name)
        for comp_name, nvme in node.pci.nvme.items():
            fab_node.add_component(model=_normalize_model(nvme.model), name=comp_name)
    return probe


def _node_host_requirements(node):
    """
    Extract host-level resource requirements from a topology node as a
    dict keyed by list_hosts() field names.
    """
    req = {
        'cores_available': node.capacity.cpu,
        'ram_available':   node.capacity.ram,
        'disk_available':  node.capacity.disk,
    }
    for _, gpu in node.pci.gpu.items():
        m = gpu.model.upper().replace('-', '_')
        if   'RTX6000'  in m or 'RTX_6000' in m: req['rtx6000_available']   = req.get('rtx6000_available',   0) + 1
        elif 'TESLAT4'  in m or 'TESLA_T4' in m:  req['tesla_t4_available'] = req.get('tesla_t4_available', 0) + 1
        elif 'A30'      in m:                      req['a30_available']      = req.get('a30_available',      0) + 1
        elif 'A40'      in m:                      req['a40_available']      = req.get('a40_available',      0) + 1
    for _, fpga in node.pci.fpga.items():
        if 'U280' in fpga.model.upper():
            req['fpga-xilinx-u280_available'] = req.get('fpga-xilinx-u280_available', 0) + 1
    for _, nvme in node.pci.nvme.items():
        req['nvme-p4510_available'] = req.get('nvme-p4510_available', 0) + 1
    for _, nic in node.pci.network.items():
        m = nic.model.upper().replace('-', '_')
        if   'CONNECTX_7_400' in m: req['smartnic-connectx-7-400_available'] = req.get('smartnic-connectx-7-400_available', 0) + 1
        elif 'CONNECTX_7_100' in m: req['smartnic-connectx-7-100_available'] = req.get('smartnic-connectx-7-100_available', 0) + 1
        elif 'CONNECTX_6'     in m:
            if 'SHARED' in m:       req['sharednic-connectx-6_available']    = req.get('sharednic-connectx-6_available',    0) + 1
            else:                   req['smartnic-connectx-6_available']      = req.get('smartnic-connectx-6_available',      0) + 1
        elif 'CONNECTX_5'     in m: req['smartnic-connectx-5_available']      = req.get('smartnic-connectx-5_available',      0) + 1
    for _, dpu in node.pci.dpu.items():
        m = dpu.model.upper().replace('-', '_')
        if   'CONNECTX_7_400' in m: req['smartnic-connectx-7-400_available'] = req.get('smartnic-connectx-7-400_available', 0) + 1
        elif 'CONNECTX_7_100' in m: req['smartnic-connectx-7-100_available'] = req.get('smartnic-connectx-7-100_available', 0) + 1
    return req


def _make_host_filter(node_site, req, sites_prefer, sites_avoid):
    """Return a list_hosts() filter function scoped to a single topology node."""
    def host_filter(row):
        host_site = row.get('name', '').split('-')[0].upper()
        if node_site and host_site != node_site:
            return False
        if not node_site and sites_prefer:
            if not any(s.upper() == host_site for s in sites_prefer):
                return False
        if sites_avoid:
            if any(s.upper() == host_site for s in sites_avoid):
                return False
        if row.get('state') != 'Active':
            return False
        for field, min_val in req.items():
            if min_val > 0 and row.get(field, 0) < min_val:
                return False
        return True
    return host_filter


# ─────────────────────────────────────────────────────────────────────────────

def validate_topology(
    fablib,
    topology,
    sites_prefer: List[str] = None,
    return_data:  bool = False,
):
    """
    Validate a topology against current FABRIC resources using the native
    slice.validate() API — the same check FABRIC runs before actual deployment.

    Builds a temporary probe slice (never submitted) from the topology model
    and calls validate() to get a per-node pass/fail result with FABRIC's
    own error messages.

    Args:
        fablib:       FablibManager instance
        topology:     SiteTopology model or dict
        sites_prefer: Preferred site names for nodes with no fixed site
        return_data:  Return result dict; False (default) suppresses
                      Jupyter auto-display

    Returns:
        dict if return_data=True, else None
        {
          'can_deploy':        bool,
          'validation_errors': {node_name: error_str},
        }
    """
    from .models import load_topology_from_dict  # relative import within package

    if isinstance(topology, dict):
        topology = load_topology_from_dict(topology)

    sites_prefer   = sites_prefer or []
    topology_nodes = list(topology.site_topology_nodes.iter_nodes())

    print(f'📊 Topology: {len(topology_nodes)} node(s)\n')
    print('🔎 Validating with FABRIC resource manager...\n')

    try:
        probe = _build_probe_slice(fablib, topology, sites_prefer)
        is_valid, errors = probe.validate(raise_exception=False)
    except Exception as e:
        print(f'❌ Validation call failed: {e}')
        result = {'can_deploy': False, 'validation_errors': {}}
        return result if return_data else None

    # Per-node summary
    for node in topology_nodes:
        err      = errors.get(node.hostname)
        status   = '✅' if not err else '❌'
        site_lbl = f' @ {node.site}' if node.site else ''
        comps    = (
            [g.model for _, g in node.pci.gpu.items()]     +
            [f.model for _, f in node.pci.fpga.items()]    +
            [n.model for _, n in node.pci.network.items()] +
            [d.model for _, d in node.pci.dpu.items()]     +
            [v.model for _, v in node.pci.nvme.items()]
        )
        comp_str = f'  [{", ".join(comps)}]' if comps else ''
        print(f'  {status} {node.hostname}{site_lbl} — '
              f'{node.capacity.cpu} cores, {node.capacity.ram} GB RAM, '
              f'{node.capacity.disk} GB disk{comp_str}')
        if err:
            print(f'       ↳ {err}')
    print()

    print('=' * 70)
    if is_valid:
        print('✅ ✅ ✅  TOPOLOGY CAN BE DEPLOYED  ✅ ✅ ✅')
    else:
        failed = list(errors.keys())
        print('❌  TOPOLOGY CANNOT BE DEPLOYED')
        print(f'    {len(failed)} node(s) failed: {", ".join(failed)}')
    print('=' * 70)

    result = {'can_deploy': is_valid, 'validation_errors': errors}
    return result if return_data else None

def find_hosts_for_topology(
    fablib,
    topology,
    sites_prefer:  List[str] = None,
    sites_avoid:   List[str] = None,
    force_refresh: bool = False,
    return_data:   bool = False,
):
    """
    Find candidate worker hosts for each node in a topology.

    Calls fablib.list_hosts() per topology node and lists every worker host
    that individually satisfies the node's resource requirements.
    All candidates are shown — no random selection.

    Run validate_topology() first to confirm resources are available before
    calling this function.

    Args:
        fablib:        FablibManager instance
        topology:      SiteTopology model or dict
        sites_prefer:  Preferred site names for nodes with no fixed site
        sites_avoid:   Sites to exclude
        force_refresh: Bypass resource cache
        return_data:   Return result dict; False (default) suppresses
                       Jupyter auto-display

    Returns:
        dict if return_data=True, else None
        {
          'matches': [{'topology_node', 'site', 'candidate_hosts',
                       'requirements_met'}, ...]
        }
    """
    from .models import load_topology_from_dict  # relative import within package

    if isinstance(topology, dict):
        topology = load_topology_from_dict(topology)

    sites_prefer   = sites_prefer or []
    sites_avoid    = sites_avoid  or []
    topology_nodes = list(topology.site_topology_nodes.iter_nodes())

    print(f'📊 Topology: {len(topology_nodes)} node(s)\n')
    print('🔍 Finding candidate worker hosts per node...\n')

    host_fields = [
        'name', 'state',
        'cores_available', 'ram_available', 'disk_available',
        'rtx6000_available', 'tesla_t4_available', 'a30_available', 'a40_available',
        'nvme-p4510_available',
        'smartnic-connectx-5_available', 'smartnic-connectx-6_available',
        'smartnic-connectx-7-100_available', 'smartnic-connectx-7-400_available',
        'sharednic-connectx-6_available',
        'fpga-xilinx-u280_available',
    ]

    all_matches = []

    for idx, node in enumerate(topology_nodes, 1):
        node_site = node.site.upper() if node.site else None
        req       = _node_host_requirements(node)

        print(f'  Node {idx}/{len(topology_nodes)}: {node.hostname}')

        try:
            candidates = fablib.list_hosts(
                fields=host_fields,
                pretty_names=False,
                filter_function=_make_host_filter(node_site, req, sites_prefer, sites_avoid),
                output='list',
                quiet=True,
                force_refresh=force_refresh,
            )
        except Exception as e:
            print(f'    ❌ list_hosts error: {e}')
            candidates = []

        if candidates:
            host_site = candidates[0]['name'].split('-')[0].upper()
            print(f'    ✅ {len(candidates)} candidate host(s) at {host_site}:')
            for h in candidates:
                line = (f'       • {h["name"]}'
                        f'  |  cores: {h.get("cores_available")}'
                        f'  ram: {h.get("ram_available")} GB'
                        f'  disk: {h.get("disk_available")} GB')
                for _param, (label, _sf, hf) in _FIELD_LOOKUP.items():
                    if hf not in ('cores_available', 'ram_available', 'disk_available'):
                        if h.get(hf, 0) > 0:
                            line += f'  {label}: {h[hf]}'
                print(line)
            all_matches.append({
                'topology_node':   node.hostname,
                'site':            host_site,
                'candidate_hosts': [h['name'] for h in candidates],
                'requirements_met': True,
            })
        else:
            assigned_site = node_site or (sites_prefer[0].upper() if sites_prefer else 'any')
            print(f'    ⚠️  No specific worker found for {node.hostname}')
            all_matches.append({
                'topology_node':   node.hostname,
                'site':            assigned_site,
                'candidate_hosts': [],
                'requirements_met': False,
            })
        print()

    # Summary
    successful = [m for m in all_matches if m['requirements_met']]
    failed     = [m for m in all_matches if not m['requirements_met']]

    print('=' * 70)
    if failed:
        print(f'⚠️  {len(failed)} node(s) had no matching host: '
              f'{", ".join(m["topology_node"] for m in failed)}')
    else:
        sites_used = {}
        for m in all_matches:
            sites_used[m['site']] = sites_used.get(m['site'], 0) + 1
        print('📍 Sites:')
        for site, count in sites_used.items():
            print(f'   {site}: {count} node(s)')
        print()
        print('📋 Candidate hosts per node:')
        for m in all_matches:
            hosts = m['candidate_hosts']
            shown = ', '.join(hosts[:3])
            if len(hosts) > 3:
                shown += f' (+{len(hosts) - 3} more)'
            print(f'   {m["topology_node"]} → {shown}')
    print('=' * 70)

    result = {'matches': all_matches}
    return result if return_data else None
