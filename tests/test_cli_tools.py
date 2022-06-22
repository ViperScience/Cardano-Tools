import pytest
import os

from cardano_tools import cli_tools

@pytest.fixture
def cli_node():
    return cli_tools.NodeCLI(
        binary_path=os.path.abspath(os.getenv('CARDANO_NODE_CLI_PATH')).replace("\\","/"),
        socket_path=os.path.abspath(os.getenv('CARDANO_NODE_SOCKET_PATH')).replace("\\","/"),
        working_dir=os.getcwd(),
        ttl_buffer=1000,
        network="--mainnet",
        era="--mary-era",
    )

def test_get_tip(cli_node):
    assert(cli_node.get_tip() > 64e6)