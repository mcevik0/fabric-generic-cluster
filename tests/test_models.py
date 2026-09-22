"""Validation contracts preserved when migrating to Pydantic V2 validators."""

from pathlib import Path
import subprocess
import sys
import textwrap

import pytest
from pydantic import ValidationError

from fabric_generic_cluster import models
from fabric_generic_cluster.models import (
    DPU,
    FPGA,
    NIC,
    FacilityPort,
    Interface,
    IPv4Config,
    IPv6Config,
    Network,
    NodeSpecific,
    OpenStackRoles,
    PCIDevices,
    SiteTopology,
    SiteTopologyFacilityPorts,
    SiteTopologyNetworks,
    SiteTopologyNodes,
    SubnetConfig,
    load_topology_from_dict,
)

IP_MODELS = [IPv4Config, IPv6Config]
ROLE_FIELDS = ["control", "network", "compute", "storage"]
NETWORK_TYPES = ["L2Bridge", "L2PTP", "L2STS", "IPv4", "IPv6", "IPv4Ext", "IPv6Ext"]
PORT_FIELDS = {"name": "SENSE-MGHPCC", "site": "MGHPCC", "binding": "lan"}


def assert_field_error(exc_info, field, value, error_type, message):
    """Pin the public error details without version-specific help URLs."""
    errors = exc_info.value.errors(include_url=False)
    assert len(errors) == 1
    error = errors[0]
    context = error.pop("ctx", {})
    assert error == {
        "loc": (field,),
        "input": value,
        "type": error_type,
        "msg": message,
    }
    if error_type == "value_error":
        # Pydantic 2.0 stores the error text; later releases store the exception.
        assert str(context["error"]) == message.removeprefix("Value error, ")


@pytest.mark.parametrize(
    "model,address",
    [
        (IPv4Config, "192.0.2.1/24"),
        (IPv4Config, "192.0.2.1"),
        (IPv6Config, "2001:db8::1/64"),
        (IPv6Config, "2001:db8::1"),
    ],
)
def test_ip_accepts_cidr_and_bare_addresses(model, address):
    assert model(address=address).address == address


@pytest.mark.parametrize("model", IP_MODELS)
@pytest.mark.parametrize("address", ["", " ", "\t\n "])
def test_ip_preserves_empty_and_whitespace_strings(model, address):
    assert model(address=address).address == address


@pytest.mark.parametrize("model", IP_MODELS)
def test_ip_defaults(model):
    assert model().model_dump() == {"address": "", "gateway": "", "dns": ""}


@pytest.mark.parametrize(
    "model,address,detail",
    [
        (IPv4Config, "2001:db8::1", "Expected 4 octets in '2001:db8::1'"),
        (IPv4Config, "bad", "Expected 4 octets in 'bad'"),
        (IPv4Config, "192.0.2.1/33", "'33' is not a valid netmask"),
        (IPv4Config, "192.0.2.1/-1", "'-1' is not a valid netmask"),
        (
            IPv4Config,
            " 192.0.2.1/24 ",
            "Only decimal digits permitted in ' 192' in ' 192.0.2.1'",
        ),
        (IPv6Config, "192.0.2.1", "At least 3 parts expected in '192.0.2.1'"),
        (IPv6Config, "bad", "At least 3 parts expected in 'bad'"),
        (IPv6Config, "2001:db8::1/129", "'129' is not a valid netmask"),
        (IPv6Config, "2001:db8::1/-1", "'-1' is not a valid netmask"),
        (
            IPv6Config,
            " 2001:db8::1/64 ",
            "Only hex digits permitted in ' 2001' in ' 2001:db8::1'",
        ),
    ],
)
def test_ip_rejects_invalid_addresses_with_original_message(model, address, detail):
    with pytest.raises(ValidationError) as exc_info:
        model(address=address)
    family = "IPv4" if model is IPv4Config else "IPv6"
    assert_field_error(
        exc_info,
        "address",
        address,
        "value_error",
        f"Value error, Invalid {family} address: {address} - {detail}",
    )


@pytest.mark.parametrize("model", IP_MODELS)
@pytest.mark.parametrize("address", [None, 123, 1.5, True, False, [], {}])
def test_ip_rejects_non_strings_during_field_parsing(model, address):
    with pytest.raises(ValidationError) as exc_info:
        model(address=address)
    assert_field_error(
        exc_info, "address", address, "string_type", "Input should be a valid string"
    )


@pytest.mark.parametrize(
    "model,address", [(IPv4Config, "192.0.2.1/24"), (IPv6Config, "2001:db8::1/64")]
)
def test_ip_bytes_are_decoded_before_validation(model, address):
    assert model(address=address.encode()).address == address


@pytest.mark.parametrize("field", ROLE_FIELDS)
@pytest.mark.parametrize("value", ["true", "false"])
def test_role_strings(field, value):
    roles = OpenStackRoles(**{field: value})
    assert getattr(roles, field) == value
    assert getattr(roles, f"is_{field}")() is (value == "true")


@pytest.mark.parametrize("field", ROLE_FIELDS)
@pytest.mark.parametrize("value", ["True", "FALSE", " true", "false ", "", "yes"])
def test_role_strings_are_case_and_whitespace_sensitive(field, value):
    with pytest.raises(ValidationError) as exc_info:
        OpenStackRoles(**{field: value})
    assert_field_error(
        exc_info,
        field,
        value,
        "value_error",
        f"Value error, Value must be 'true' or 'false', got: {value}",
    )


@pytest.mark.parametrize("field", ROLE_FIELDS)
@pytest.mark.parametrize("value", [True, False, None, 1])
def test_roles_reject_non_strings_during_field_parsing(field, value):
    with pytest.raises(ValidationError) as exc_info:
        OpenStackRoles(**{field: value})
    assert_field_error(
        exc_info, field, value, "string_type", "Input should be a valid string"
    )


def test_role_defaults():
    roles = OpenStackRoles()
    assert roles.model_dump() == {field: "false" for field in ROLE_FIELDS}
    assert all(getattr(roles, f"is_{field}")() is False for field in ROLE_FIELDS)


def test_roles_report_multiple_invalid_fields():
    values = {"control": "TRUE", "network": True, "compute": " false", "storage": None}
    with pytest.raises(ValidationError) as exc_info:
        OpenStackRoles(**values)
    assert exc_info.value.errors(include_url=False, include_context=False) == [
        {
            "loc": (field,),
            "input": value,
            "type": "value_error" if isinstance(value, str) else "string_type",
            "msg": (
                f"Value error, Value must be 'true' or 'false', got: {value}"
                if isinstance(value, str)
                else "Input should be a valid string"
            ),
        }
        for field, value in values.items()
    ]


@pytest.mark.parametrize(
    "value,expected",
    [(1, 1), (4094, 4094), ("1", 1), ("4094", 4094), (2.0, 2), (True, 1)],
)
def test_vlan_boundaries_and_coercion(value, expected):
    port = FacilityPort(**PORT_FIELDS, vlan=value)
    assert port.vlan == expected
    assert type(port.vlan) is int


@pytest.mark.parametrize(
    "value,parsed",
    [(0, 0), (-1, -1), (4095, 4095), ("0", 0), ("4095", 4095), (False, 0)],
)
def test_vlan_range_is_checked_after_coercion(value, parsed):
    with pytest.raises(ValidationError) as exc_info:
        FacilityPort(**PORT_FIELDS, vlan=value)
    assert_field_error(
        exc_info,
        "vlan",
        value,
        "value_error",
        f"Value error, VLAN must be between 1 and 4094, got: {parsed}",
    )


@pytest.mark.parametrize(
    "value,error_type,message",
    [
        (None, "int_type", "Input should be a valid integer"),
        (
            1.5,
            "int_from_float",
            "Input should be a valid integer, got a number with a fractional part",
        ),
        (
            "bad",
            "int_parsing",
            "Input should be a valid integer, unable to parse string as an integer",
        ),
    ],
)
def test_vlan_field_parsing_errors(value, error_type, message):
    with pytest.raises(ValidationError) as exc_info:
        FacilityPort(**PORT_FIELDS, vlan=value)
    assert_field_error(exc_info, "vlan", value, error_type, message)


def test_vlan_is_required():
    with pytest.raises(ValidationError) as exc_info:
        FacilityPort(**PORT_FIELDS)
    assert_field_error(exc_info, "vlan", PORT_FIELDS, "missing", "Field required")


@pytest.mark.parametrize("network_type", NETWORK_TYPES)
def test_network_accepts_existing_types(network_type):
    network = Network(name="lan", type=network_type)
    assert network.type == network_type
    assert network.subnet is None


@pytest.mark.parametrize("value", ["unknown", "ipv4", "l2bridge", "IPv4 "])
def test_network_rejects_invalid_types(value):
    with pytest.raises(ValidationError) as exc_info:
        Network(name="lan", type=value)
    assert_field_error(
        exc_info,
        "type",
        value,
        "value_error",
        f"Value error, Network type must be one of {NETWORK_TYPES}, got: {value}",
    )


def test_network_type_is_required():
    with pytest.raises(ValidationError) as exc_info:
        Network(name="lan")
    assert_field_error(exc_info, "type", {"name": "lan"}, "missing", "Field required")


def test_network_type_rejects_none():
    with pytest.raises(ValidationError) as exc_info:
        Network(name="lan", type=None)
    assert_field_error(
        exc_info, "type", None, "string_type", "Input should be a valid string"
    )


@pytest.mark.parametrize("network_type", NETWORK_TYPES)
@pytest.mark.parametrize("subnet", [None, {}, {"ipv4": {"address": "192.0.2.0/24"}}])
def test_network_optional_subnet(network_type, subnet):
    network = Network(name="lan", type=network_type, subnet=subnet)
    if subnet is None:
        assert network.subnet is None
    else:
        assert isinstance(network.subnet, SubnetConfig)
        assert network.ipv4_subnet == subnet.get("ipv4", {}).get("address", "")
        assert network.ipv6_subnet == ""


@pytest.fixture
def topology_data():
    return {
        "site_topology_nodes": {
            "nodes": {
                "node1": {
                    "name": "node1",
                    "hostname": "node1",
                    "capacity": {
                        "cpu": 2,
                        "ram": 4,
                        "disk": 10,
                        "os": "default_rocky_9",
                    },
                    "pci": {
                        "network": {
                            "nic1": {
                                "name": "nic1",
                                "model": "NIC_Basic",
                                "interfaces": {
                                    "if1": {
                                        "device": "eth1",
                                        "connection": "con1",
                                        "binding": "lan",
                                        "ipv4": {"address": "192.0.2.1/24"},
                                        "ipv6": {"address": "2001:db8::1/64"},
                                    }
                                },
                            }
                        }
                    },
                    "specific": {"openstack": {"control": "true"}},
                }
            }
        },
        "site_topology_networks": {
            "networks": {
                "lan": {
                    "name": "lan",
                    "type": "L2Bridge",
                    "subnet": {"ipv4": {"address": "192.0.2.0/24"}},
                }
            }
        },
        "site_topology_facility_ports": {
            "facility_ports": {"fp1": {**PORT_FIELDS, "vlan": "100"}}
        },
    }


def test_nested_topology_validation_and_round_trip(topology_data):
    topology = load_topology_from_dict(topology_data)
    node = topology.get_node_by_hostname("node1")
    interface = node.pci.network["nic1"].interfaces["if1"]
    assert isinstance(interface, Interface)
    assert interface.get_ipv4_address() == "192.0.2.1/24"
    assert interface.get_ipv6_address(strip_cidr=True) == "2001:db8::1"
    assert node.specific.openstack.is_control() is True
    assert node.specific.openstack.compute == "false"
    assert topology.get_nodes_on_network("lan") == [node]
    assert topology.get_network_by_name("lan").ipv4_subnet == "192.0.2.0/24"
    assert topology.get_facility_ports_for_network("lan")[0].vlan == 100
    assert SiteTopology.from_yaml_dict(topology.to_dict()) == topology


def test_nested_error_locations_and_messages(topology_data):
    node = topology_data["site_topology_nodes"]["nodes"]["node1"]
    interface = node["pci"]["network"]["nic1"]["interfaces"]["if1"]
    interface["ipv4"]["address"] = "bad"
    interface["ipv6"]["address"] = "bad"
    node["specific"]["openstack"]["storage"] = "TRUE"
    network = topology_data["site_topology_networks"]["networks"]["lan"]
    network["type"] = "unknown"
    network["subnet"]["ipv4"]["address"] = "bad"
    topology_data["site_topology_facility_ports"]["facility_ports"]["fp1"]["vlan"] = 0
    with pytest.raises(ValidationError) as exc_info:
        load_topology_from_dict(topology_data)

    node_path = ("site_topology_nodes", "nodes", "node1")
    interface_path = (*node_path, "pci", "network", "nic1", "interfaces", "if1")
    network_path = ("site_topology_networks", "networks", "lan")
    ipv4_message = "Value error, Invalid IPv4 address: bad - Expected 4 octets in 'bad'"
    ipv6_message = (
        "Value error, Invalid IPv6 address: bad - At least 3 parts expected in 'bad'"
    )
    expected = [
        ((*interface_path, "ipv4", "address"), "bad", ipv4_message),
        ((*interface_path, "ipv6", "address"), "bad", ipv6_message),
        (
            (*node_path, "specific", "openstack", "storage"),
            "TRUE",
            "Value error, Value must be 'true' or 'false', got: TRUE",
        ),
        (
            (*network_path, "type"),
            "unknown",
            f"Value error, Network type must be one of {NETWORK_TYPES}, got: unknown",
        ),
        ((*network_path, "subnet", "ipv4", "address"), "bad", ipv4_message),
        (
            ("site_topology_facility_ports", "facility_ports", "fp1", "vlan"),
            0,
            "Value error, VLAN must be between 1 and 4094, got: 0",
        ),
    ]
    assert exc_info.value.errors(include_url=False, include_context=False) == [
        {"loc": loc, "input": value, "type": "value_error", "msg": message}
        for loc, value, message in expected
    ]


@pytest.mark.parametrize("model", [SubnetConfig, Interface])
def test_ip_default_factories_are_independent(model):
    kwargs = {"device": "eth1", "connection": "con1"} if model is Interface else {}
    first, second = model(**kwargs), model(**kwargs)
    for field, address in [("ipv4", "192.0.2.1"), ("ipv6", "2001:db8::1")]:
        assert getattr(first, field) is not getattr(second, field)
        setattr(getattr(first, field), "address", address)
        assert getattr(second, field).address == ""


def test_role_default_factory_is_independent():
    first, second = NodeSpecific(), NodeSpecific()
    assert first.openstack is not second.openstack
    first.openstack.control = "true"
    assert second.openstack.control == "false"


@pytest.mark.parametrize(
    "model,kwargs,field",
    [
        (SiteTopologyNodes, {}, "nodes"),
        (SiteTopologyNetworks, {}, "networks"),
        (SiteTopologyFacilityPorts, {}, "facility_ports"),
        (PCIDevices, {}, "network"),
        (NIC, {"name": "nic1", "model": "NIC_Basic"}, "interfaces"),
        (DPU, {"name": "dpu1", "model": "BlueField"}, "interfaces"),
        (FPGA, {"name": "fpga1", "model": "U280"}, "interfaces"),
    ],
)
def test_collection_default_factories_are_independent(model, kwargs, field):
    first, second = model(**kwargs), model(**kwargs)
    assert getattr(first, field) == getattr(second, field) == {}
    assert getattr(first, field) is not getattr(second, field)
    getattr(first, field)["sentinel"] = object()
    assert getattr(second, field) == {}


def test_topology_default_factory_is_independent():
    data = {"site_topology_nodes": {}, "site_topology_networks": {}}
    first, second = SiteTopology(**data), SiteTopology(**data)
    assert first.site_topology_facility_ports is not second.site_topology_facility_ports
    first.site_topology_facility_ports.facility_ports["fp1"] = FacilityPort(
        **PORT_FIELDS, vlan=1
    )
    assert second.site_topology_facility_ports.facility_ports == {}


def test_fresh_import_has_no_v1_validator_deprecations():
    # A new process avoids import caching and existing warning registries.
    # Target only validator warnings: Network.gateway's deprecated Field
    # keyword emits a separate warning in early Pydantic 2.x releases.
    code = textwrap.dedent("""
        import runpy
        import sys
        import warnings

        warnings.filterwarnings(
            "error",
            message=r"Pydantic V1 style `@validator` validators are deprecated",
            category=DeprecationWarning,
        )
        runpy.run_path(sys.argv[1])
        """)
    result = subprocess.run(
        [sys.executable, "-c", code, str(Path(models.__file__).resolve())],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
