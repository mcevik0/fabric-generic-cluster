"""Offline contracts for FABlib 1.9.x and ResourcesV2 resource discovery."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from fabric_generic_cluster import resources as r

# Keep expectations independent of the implementation's compatibility map.
COMPONENTS = [
    ("sharednic_connectx_6", "SharedNIC-ConnectX-6", "nic_basic"),
    ("smartnic_connectx_5", "SmartNIC-ConnectX-5", "nic_connectx_5"),
    ("smartnic_connectx_6", "SmartNIC-ConnectX-6", "nic_connectx_6"),
    (
        "smartnic_connectx_7_100",
        "SmartNIC-ConnectX-7-100",
        "nic_connectx_7_100",
    ),
    (
        "smartnic_connectx_7_400",
        "SmartNIC-ConnectX-7-400",
        "nic_connectx_7_400",
    ),
    ("gpu_rtx6000", "GPU-RTX6000", "rtx6000"),
    ("gpu_a30", "GPU-A30", "a30"),
    ("gpu_a40", "GPU-A40", "a40"),
    ("gpu_tesla_t4", "GPU-Tesla T4", "tesla_t4"),
    ("fpga_u280", "FPGA-Xilinx-U280", "fpga_u280"),
    ("nvme", "NVME-P4510", "nvme"),
]
COMPUTE = [("min_cores", "cores"), ("min_ram", "ram"), ("min_disk", "disk")]
LABELS = {
    "sharednic_connectx_6": "SharedNIC ConnectX-6",
    "smartnic_connectx_5": "SmartNIC ConnectX-5",
    "smartnic_connectx_6": "SmartNIC ConnectX-6",
    "smartnic_connectx_7_100": "SmartNIC CX7-100G",
    "smartnic_connectx_7_400": "SmartNIC CX7-400G",
    "gpu_rtx6000": "RTX6000",
    "gpu_a30": "A30",
    "gpu_a40": "A40",
    "gpu_tesla_t4": "Tesla T4",
    "fpga_u280": "U280 FPGA",
    "nvme": "NVMe",
}


def set_counts(data, prefix, capacity, allocated):
    data.update(
        {
            f"{prefix}_capacity": capacity,
            f"{prefix}_allocated": allocated,
            f"{prefix}_available": capacity - allocated,
        }
    )


def site_data(name="TEST", hardware=True):
    data = {"name": name, "state": "Active", "address": "Test address"}
    for resource in ("cores", "ram", "disk"):
        set_counts(data, resource, capacity=100, allocated=20)
    data["components"] = (
        {model: {"capacity": 5, "allocated": 2} for _, model, _ in COMPONENTS}
        if hardware
        else {}
    )
    return data


def host_data(name="test-worker", hardware=True):
    data = {"name": name, "state": "Active", "custom_field": "retained"}
    for prefix in ("cores", "ram", "disk"):
        set_counts(data, prefix, capacity=100, allocated=20)
    if hardware:
        for _, _, native in COMPONENTS:
            set_counts(data, native, capacity=5, allocated=2)
    return data


class LegacySite:
    """Public FABlib 1.9.x Site APIs, deliberately without site_info."""

    def __init__(self, data):
        self.data = data
        self.components = {
            name: deepcopy(counts)
            for name, counts in (data.get("components") or {}).items()
            if name != "P4-Switch"
        }

    def get_hosts(self):
        return {
            "test-worker": SimpleNamespace(
                get_components=lambda: self.components
            )
        }

    def get_component_capacity(self, component_model_name):
        return self.components[component_model_name].get("capacity", 0)

    def get_component_allocated(self, component_model_name):
        return self.components[component_model_name].get("allocated", 0)

    def to_dict(self):
        # Legacy serialization only includes a fixed set of component types,
        # using table aliases rather than all original component model names.
        serialized = {}
        for model, native in [(m, n) for _, m, n in COMPONENTS] + [
            ("FPGA-Xilinx-SN1022", "fpga_sn1022"),
            ("P4-Switch", "p4-switch"),
        ]:
            counts = (self.data.get("components") or {}).get(model) or {}
            set_counts(
                serialized,
                native,
                capacity=counts.get("capacity", 0),
                allocated=counts.get("allocated", 0),
            )
        return serialized

    def get_state(self):
        return self.data.get("state")

    def get_location_postal(self):
        return self.data.get("address")


# The legacy API uses singular 'core' in its getter names.
for _resource, _getter in [
    ("cores", "core"),
    ("ram", "ram"),
    ("disk", "disk"),
]:
    for _count in ("available", "capacity", "allocated"):

        def getter(self, key=f"{_resource}_{_count}"):
            return self.data.get(key)

        setattr(LegacySite, f"get_{_getter}_{_count}", getter)


class Snapshot:
    """ResourcesV2 has no .sites; both versions expose these public methods."""

    def __init__(self, shape, sites, hosts):
        self.shape = shape
        self.site_data = sites
        self.host_data = hosts
        self.updates = []
        self.reads = 0
        self.on_update = None

    def get_site_names(self):
        return list(self.site_data)

    def get_site(self, name):
        data = self.site_data.get(name)
        if data is None or self.shape == "v2":
            return data
        return LegacySite(data)

    def list_hosts(self, *, output, pretty_names, quiet):
        assert (output, pretty_names, quiet) == ("list", False, True)
        self.reads += 1
        return self.host_data

    def update(self, *, force_refresh):
        self.updates.append(force_refresh)
        if self.on_update:
            self.on_update(self)


class Manager:
    def __init__(self, shape="v2", sites=None, hosts=None):
        self.snapshot = Snapshot(
            shape,
            {"TEST": site_data()} if sites is None else sites,
            [host_data()] if hosts is None else hosts,
        )
        self.calls = []

    def get_resources(self, update=False, force_refresh=False):
        self.calls.append((update, force_refresh))
        if update:
            self.snapshot.update(force_refresh=force_refresh)
        return self.snapshot


@pytest.fixture(params=["legacy", "v2"])
def manager(request):
    return Manager(request.param)


def topology(*nodes):
    return SimpleNamespace(
        site_topology_nodes=SimpleNamespace(iter_nodes=lambda: iter(nodes))
    )


def node(name="node1", site="TEST", **components):
    pci = {kind: {} for kind in ("gpu", "network", "dpu", "fpga", "nvme")}
    for kind, models in components.items():
        pci[kind] = {
            str(i): SimpleNamespace(model=model)
            for i, model in enumerate(models)
        }
    return SimpleNamespace(
        hostname=name,
        site=site,
        capacity=SimpleNamespace(cpu=8, ram=16, disk=20),
        pci=SimpleNamespace(**pci),
    )


def test_site_shapes_and_all_legacy_columns(manager):
    before = deepcopy(manager.snapshot.site_data)
    frame = r.get_sites_dataframe(manager)
    assert isinstance(frame, pd.DataFrame)
    row = frame.iloc[0]
    assert row["name"] == "TEST"
    assert row["state"] == "Active"
    assert row["address"] == "Test address"
    for _, resource in COMPUTE:
        assert row[f"{resource}_available"] == 80
        assert row[f"{resource}_capacity"] == 100
        assert row[f"{resource}_allocated"] == 20
    for _, model, _ in COMPONENTS:
        assert row[f"{model.lower()}_available"] == 3
        assert row[f"{model.lower()}_capacity"] == 5
        assert row[f"{model.lower()}_allocated"] == 2
    assert manager.snapshot.site_data == before


@pytest.mark.parametrize("criterion,prefix", COMPUTE)
def test_compute_filtering(manager, criterion, prefix):
    manager.snapshot.site_data["OTHER"] = site_data("OTHER")
    set_counts(manager.snapshot.site_data["OTHER"], prefix, 100, 96)
    manager.snapshot.host_data.append(host_data("other-worker"))
    set_counts(manager.snapshot.host_data[1], prefix, 100, 96)
    kwargs = {criterion: 8, "verbose": False, "return_data": True}
    assert r.find_sites_with_resources(manager, **kwargs)["name"].tolist() == [
        "TEST"
    ]
    assert [
        h["name"] for h in r.find_hosts_with_resources(manager, **kwargs)
    ] == ["test-worker"]


@pytest.mark.parametrize("criterion,model,native", COMPONENTS)
def test_each_hardware_filter_and_label(
    manager, criterion, model, native, capsys
):
    manager.snapshot.site_data["BARE"] = site_data("BARE", hardware=False)
    manager.snapshot.host_data.append(host_data("bare-worker", hardware=False))
    kwargs = {criterion: 1, "return_data": True}
    sites = r.find_sites_with_resources(manager, **kwargs)
    site_output = capsys.readouterr().out
    hosts = r.find_hosts_with_resources(manager, **kwargs)
    host_output = capsys.readouterr().out
    assert sites["name"].tolist() == ["TEST"]
    assert [h["name"] for h in hosts] == ["test-worker"]
    prefix = native if criterion.startswith("gpu_") else model.lower()
    assert hosts[0][f"{prefix}_available"] == 3
    assert hosts[0][f"{prefix}_capacity"] == 5
    assert hosts[0][f"{prefix}_allocated"] == 2
    # Preserve native and extra upstream fields in returned dictionaries.
    assert hosts[0][f"{native}_available"] == 3
    assert hosts[0]["custom_field"] == "retained"
    assert f"{LABELS[criterion]}: >= 1" in site_output
    assert f"{LABELS[criterion]}: >= 1" in host_output
    assert f"{LABELS[criterion]}: 3" in host_output
    assert (
        "sharednic-connectx-6_available" not in manager.snapshot.host_data[0]
    )


def test_missing_hardware_and_stable_empty_schema(manager):
    full_columns = list(r.get_sites_dataframe(manager).columns)
    manager.snapshot.site_data = {"BARE": site_data("BARE", hardware=False)}
    bare = r.get_sites_dataframe(manager)
    assert list(bare.columns) == full_columns
    for _, model, _ in COMPONENTS:
        assert bare.iloc[0][f"{model.lower()}_available"] == 0
    filtered = r.find_sites_with_resources(
        manager, gpu_a40=1, return_data=True, verbose=False
    )
    assert filtered.empty and list(filtered.columns) == full_columns
    manager.snapshot.site_data = {}
    empty = r.get_sites_dataframe(manager)
    assert empty.empty and list(empty.columns) == full_columns
    for criteria in ({}, {"nvme": 1}):
        result = r.find_sites_with_resources(
            manager, **criteria, return_data=True, verbose=False
        )
        assert result.empty and list(result.columns) == full_columns
    manager.snapshot.host_data = []
    assert r.find_hosts_with_resources(manager, return_data=True) == []
    assert r.find_hosts_with_resources(manager) is None
    assert r.find_sites_with_resources(manager) is None


def test_missing_site_and_nullable_fields(manager):
    manager.snapshot.site_data = {
        "GONE": None,
        "BARE": {"components": None},
    }
    row = r.get_sites_dataframe(manager).iloc[0]
    assert row["name"] == "BARE"
    assert pd.isna(row["state"]) and pd.isna(row["address"])
    assert row["cores_available"] == 0
    assert row["gpu-a30_available"] == 0


def test_v2_explicit_availability_and_nulls():
    manager = Manager(
        sites={
            "TEST": {
                "cores_capacity": 100,
                "cores_allocated": 20,
                "cores_available": 7,
                "ram_capacity": 10,
                "ram_allocated": None,
                "components": {
                    "GPU-A30": {"capacity": 5, "allocated": 1, "available": 2},
                    "NVME-P4510": {
                        "capacity": None,
                        "allocated": float("nan"),
                    },
                    "FPGA-Xilinx-U280": None,
                },
            }
        }
    )
    row = r.get_sites_dataframe(manager).iloc[0]
    assert row["cores_available"] == 7
    assert row["ram_available"] == 10
    assert row["gpu-a30_available"] == 2
    assert row["nvme-p4510_available"] == 0
    assert row["fpga-xilinx-u280_available"] == 0


def test_extra_component_columns_are_preserved_and_ordered(manager):
    manager.snapshot.site_data = {
        "ONE": {"components": {"FPGA-Xilinx-SN1022": {"capacity": 2}}},
        "TWO": {
            "components": {
                "P4-Switch": {"capacity": 2, "allocated": 1},
                "GPU-Future": {"capacity": 4, "allocated": 1},
            }
        },
    }
    first = r.get_sites_dataframe(manager)
    assert first.iloc[0]["fpga-xilinx-sn1022_available"] == 2
    assert first.iloc[1]["fpga-xilinx-sn1022_available"] == 0
    assert first.iloc[0]["p4-switch_available"] == 0
    assert first.iloc[1]["p4-switch_available"] == 1
    assert first.iloc[1]["p4-switch_capacity"] == 2
    assert first.iloc[1]["p4-switch_allocated"] == 1
    assert first.iloc[1]["gpu-future_available"] == 3
    assert first.iloc[1]["gpu-future_capacity"] == 4
    assert first.iloc[1]["gpu-future_allocated"] == 1
    assert "fpga_sn1022_available" not in first.columns
    manager.snapshot.site_data = dict(
        reversed(list(manager.snapshot.site_data.items()))
    )
    assert list(r.get_sites_dataframe(manager).columns) == list(first.columns)


@pytest.mark.parametrize("model,native", [(m, n) for _, m, n in COMPONENTS])
def test_host_normalization_accepts_old_and_native_names(model, native):
    prefix = native if model.startswith("GPU-") else model.lower()
    for source in (prefix, native):
        host = {f"{source}_capacity": 4, f"{source}_allocated": 1}
        row = r._normalize_host(host)
        assert row[f"{prefix}_available"] == 3
        assert row[f"{prefix}_capacity"] == 4
        assert row[f"{prefix}_allocated"] == 1
    # An explicit zero is authoritative; null falls back to the native value.
    row = r._normalize_host(
        {
            f"{native}_available": 2,
            f"{prefix}_available": 0,
        }
    )
    assert row[f"{prefix}_available"] == 0
    row = r._normalize_host({"cores_available": None, "a40_available": pd.NA})
    assert row["cores_available"] == row["a40_available"] == 0


@pytest.mark.parametrize(
    "query", ["sites", "site_finder", "hosts", "topology"]
)
def test_force_refresh_changes_cached_results(manager, query):
    manager.snapshot.site_data = {}
    manager.snapshot.host_data = []

    def refresh(snapshot):
        # The service cache only changes on a forced refresh in this scenario.
        if snapshot.updates[-1]:
            snapshot.site_data = {"TEST": site_data()}
            snapshot.host_data = [host_data()]

    manager.snapshot.on_update = refresh

    def run(force):
        kwargs = {"force_refresh": force}
        if query == "sites":
            return len(r.get_sites_dataframe(manager, **kwargs))
        if query == "site_finder":
            return len(
                r.find_sites_with_resources(
                    manager, return_data=True, **kwargs
                )
            )
        if query == "hosts":
            return len(
                r.find_hosts_with_resources(
                    manager, return_data=True, **kwargs
                )
            )
        result = r.find_hosts_for_topology(
            manager,
            topology(node(), node("node2")),
            return_data=True,
            **kwargs,
        )
        return len(result["matches"][0]["candidate_hosts"])

    assert run(False) == 0
    host_query = query in ("hosts", "topology")
    assert manager.snapshot.updates == ([False] if host_query else [])
    assert run(True) == 1
    assert manager.calls == [(host_query, False), (True, True)]
    assert manager.snapshot.updates == (
        [False, True] if host_query else [True]
    )
    assert run(False) == 1
    assert manager.calls[-1] == (host_query, False)
    assert manager.snapshot.updates == (
        [False, True, False] if host_query else [True]
    )
    if host_query:
        assert manager.snapshot.reads == 3


@pytest.mark.parametrize("query", ["hosts", "topology"])
def test_normal_host_query_preserves_1_9_x_freshness(manager, query):
    # In 1.9.x list_hosts(update=True) reloaded the local snapshot even when
    # force_refresh=False. Keep service allocations separate from that cache.
    service_host = host_data()
    service_allocations = {"cores": 96, "ram": 20, "disk": 20}

    def refresh(snapshot):
        refreshed = deepcopy(service_host)
        for prefix, allocated in service_allocations.items():
            set_counts(refreshed, prefix, capacity=100, allocated=allocated)
        snapshot.host_data = [refreshed]

    manager.snapshot.on_update = refresh

    def run():
        if query == "hosts":
            return [
                host["name"]
                for host in r.find_hosts_with_resources(
                    manager, min_cores=8, return_data=True, force_refresh=False
                )
            ]
        result = r.find_hosts_for_topology(
            manager,
            topology(node(), node("node2")),
            return_data=True,
            force_refresh=False,
        )
        matches = result["matches"]
        assert len(matches) == 2
        assert matches[0]["candidate_hosts"] == matches[1]["candidate_hosts"]
        return matches[0]["candidate_hosts"]

    assert run() == []
    service_allocations["cores"] = 20
    assert manager.snapshot.host_data[0]["cores_available"] == 4
    assert run() == ["test-worker"]
    service_allocations["cores"] = 99
    assert run() == []
    assert manager.calls == [(True, False)] * 3
    assert manager.snapshot.updates == [False] * 3
    assert manager.snapshot.reads == 3


def test_topology_filters_normalized_hardware_and_sites(manager):
    manager.snapshot.host_data = [
        host_data("test-worker"),
        host_data("other-worker"),
        host_data("test-bare", hardware=False),
        host_data("test-offline"),
    ]
    manager.snapshot.host_data[-1]["state"] = "Maintenance"
    required = node(
        site=None,
        network=["NIC_ConnectX_5", "NIC_ConnectX_6"],
        dpu=["NIC_ConnectX_7_100", "NIC_ConnectX_7_400"],
        gpu=["GPU_RTX6000", "GPU_A30", "GPU_A40", "GPU_TeslaT4"],
        fpga=["FPGA_Xilinx_U280"],
        nvme=["NVME_P4510"],
    )
    result = r.find_hosts_for_topology(
        manager,
        topology(required),
        sites_prefer=["test", "other"],
        sites_avoid=["other"],
        return_data=True,
    )
    assert result["matches"][0]["candidate_hosts"] == ["test-worker"]
    assert result["matches"][0]["requirements_met"] is True
    assert manager.snapshot.reads == 1
    result = r.find_hosts_for_topology(
        manager, topology(node(site="OTHER")), return_data=True
    )
    assert result["matches"][0]["candidate_hosts"] == ["other-worker"]
    assert r.find_hosts_for_topology(
        manager, topology(), return_data=True
    ) == {"matches": []}


def test_site_api_failures_propagate(manager):
    manager.get_resources = Mock(side_effect=RuntimeError("API failed"))
    with pytest.raises(RuntimeError, match="API failed"):
        r.get_sites_dataframe(manager)


@pytest.mark.parametrize("stage", ["get_resources", "list_hosts"])
@pytest.mark.parametrize("return_data", [False, True])
@pytest.mark.parametrize("error", [RuntimeError, TypeError])
def test_host_query_failures_return_empty_list(
    manager, stage, return_data, error, capsys
):
    target = manager if stage == "get_resources" else manager.snapshot
    setattr(target, stage, Mock(side_effect=error("host query failed")))
    assert r.find_hosts_with_resources(manager, return_data=return_data) == []
    assert "Error querying hosts: host query failed" in capsys.readouterr().out


@pytest.mark.parametrize("stage", ["get_resources", "list_hosts"])
@pytest.mark.parametrize("return_data", [False, True])
def test_topology_host_failures_preserve_unsuccessful_matches(
    manager, stage, return_data, capsys
):
    target = manager if stage == "get_resources" else manager.snapshot
    query = Mock(side_effect=RuntimeError("host query failed"))
    setattr(target, stage, query)
    result = r.find_hosts_for_topology(
        manager,
        topology(node(), node("node2", site=None)),
        sites_prefer=["other"],
        return_data=return_data,
    )
    expected = {
        "matches": [
            {
                "topology_node": "node1",
                "site": "TEST",
                "candidate_hosts": [],
                "requirements_met": False,
            },
            {
                "topology_node": "node2",
                "site": "OTHER",
                "candidate_hosts": [],
                "requirements_met": False,
            },
        ]
    }
    assert result == (expected if return_data else None)
    query.assert_called_once()
    output = capsys.readouterr().out
    assert "list_hosts error: host query failed" in output
    assert "2 node(s) had no matching host: node1, node2" in output


def test_topology_continues_after_node_filter_failure(monkeypatch, manager):
    good_filter = r._make_host_filter("TEST", {}, [], [])
    monkeypatch.setattr(
        r,
        "_make_host_filter",
        Mock(side_effect=[RuntimeError("filter failed"), good_filter]),
    )
    matches = r.find_hosts_for_topology(
        manager, topology(node(), node("node2")), return_data=True
    )["matches"]
    assert matches[0]["requirements_met"] is False
    assert matches[0]["candidate_hosts"] == []
    assert matches[1]["requirements_met"] is True
    assert matches[1]["candidate_hosts"] == ["test-worker"]
    assert manager.snapshot.reads == 1


def test_site_and_internal_normalization_failures_propagate(manager):
    manager.snapshot.get_site = Mock(side_effect=ValueError("bad site"))
    with pytest.raises(ValueError, match="bad site"):
        r.get_sites_dataframe(manager)
    with pytest.raises(TypeError):
        r._normalize_host({"cores_capacity": "not a number"})


def test_validation_errors_remain_diagnosable(monkeypatch, manager):
    probe = SimpleNamespace(
        validate=Mock(return_value=(False, {"node1": "full"}))
    )
    monkeypatch.setattr(r, "_build_probe_slice", lambda *args: probe)
    assert r.validate_topology(
        manager, topology(node()), return_data=True
    ) == {
        "can_deploy": False,
        "validation_errors": {"node1": "full"},
    }
    probe.validate.assert_called_once_with(raise_exception=False)


@pytest.mark.parametrize("stage", ["build_probe", "validate"])
@pytest.mark.parametrize("return_data", [False, True])
def test_validation_exceptions_preserve_failed_result(
    monkeypatch, manager, stage, return_data, capsys
):
    failure = RuntimeError("validation service failed")
    if stage == "build_probe":
        manager.new_slice = Mock(side_effect=failure)
    else:
        probe = SimpleNamespace(validate=Mock(side_effect=failure))
        monkeypatch.setattr(r, "_build_probe_slice", lambda *args: probe)
    result = r.validate_topology(
        manager, topology(node()), return_data=return_data
    )
    expected = {"can_deploy": False, "validation_errors": {}}
    assert result == (expected if return_data else None)
    assert (
        "Validation call failed: validation service failed"
        in capsys.readouterr().out
    )
