"""Package version follows metadata and supports uninstalled checkouts."""

import importlib
from importlib import metadata
from unittest.mock import Mock

import pytest

import fabric_generic_cluster


@pytest.fixture
def metadata_version(monkeypatch):
    with monkeypatch.context() as patch:
        lookup = Mock()
        patch.setattr(metadata, "version", lookup)
        yield lookup
    # Restore the runtime version so other tests see the real metadata.
    importlib.reload(fabric_generic_cluster)


def test_version_matches_installed_metadata():
    try:
        expected = metadata.version("fabric-generic-cluster")
    except metadata.PackageNotFoundError:
        pytest.skip("Distribution metadata is unavailable in this checkout")

    assert fabric_generic_cluster.__version__ == expected


def test_version_uses_distribution_metadata(metadata_version):
    metadata_version.return_value = "2.3.4.dev5"

    importlib.reload(fabric_generic_cluster)

    metadata_version.assert_called_once_with("fabric-generic-cluster")
    assert fabric_generic_cluster.__version__ == metadata_version.return_value


def test_version_without_distribution_metadata(metadata_version):
    metadata_version.side_effect = metadata.PackageNotFoundError(
        "fabric-generic-cluster"
    )

    importlib.reload(fabric_generic_cluster)

    metadata_version.assert_called_once_with("fabric-generic-cluster")
    assert fabric_generic_cluster.__version__ == "0+unknown"
