import pytest
import os

from cardano_tools import cli_tools


@pytest.fixture
def era():
    return "alonzo"


@pytest.fixture
def cli_node(era):
    print(f"Working dir = {os.getcwd()}")
    return cli_tools.NodeCLI(
        binary_path=os.path.abspath(os.getenv("CARDANO_NODE_CLI_PATH")).replace("\\", "/"),
        socket_path=os.path.abspath(os.getenv("CARDANO_NODE_SOCKET_PATH")).replace("\\", "/"),
        working_dir=os.getcwd(),
        ttl_buffer=1000,
        network="--mainnet",
        era=f"--{era}-era",
    )


def test_get_tip(cli_node):
    assert cli_node.get_tip() > 0


def test_get_sync_progress(cli_node):
    assert cli_node.get_sync_progress() > 0.0


def test_get_epoch(cli_node):
    assert cli_node.get_epoch() > 0


def test_get_slot(cli_node):
    assert cli_node.get_slot() > 0


def test_get_era(cli_node, era):
    assert cli_node.get_era().lower() == era
