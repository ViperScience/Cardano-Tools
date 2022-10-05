import json
import os

import pytest
import requests

from cardano_tools import cli_tools


@pytest.fixture
def network() -> str:
    # Override network with env var if it is set
    if network := os.getenv("CARDANO_NETWORK"):
        print(f"Using CARDANO_NETWORK env var for cardano-node: {network}")
    else:
        network = "--mainnet"
        print("CARDANO_NETWORK env var not set, defaulting to --mainnet")
    return network


@pytest.fixture
def is_testnet(network) -> bool:
    """Returns True if cardano-node is running on the testnet rather than mainnet"""
    return "testnet" in network


@pytest.fixture
def era(is_testnet) -> str:
    return "babbage" if is_testnet else "alonzo"


@pytest.fixture
def working_dir() -> str:
    path = "./config"
    if not os.path.exists(path):
        os.makedirs(path)
    return path


@pytest.fixture
def shelley_genesis(is_testnet, working_dir) -> str:
    filename = "shelley-genesis.json"
    filepath = f"{working_dir}/{filename}"
    if is_testnet:
        environment = "preview"
    else:
        environment = "mainnet"
    url = f"https://book.world.dev.cardano.org/environments/{environment}/{filename}"
    r = requests.get(url)
    with open(filepath, "wb") as gen_file:
        gen_file.write(r.content)
    return filepath


@pytest.fixture
def cli_node(network, era, working_dir):
    yield cli_tools.NodeCLI(
        binary_path=os.path.abspath(os.getenv("CARDANO_NODE_CLI_PATH")).replace("\\", "/"),
        socket_path=os.path.abspath(os.getenv("CARDANO_NODE_SOCKET_PATH")).replace("\\", "/"),
        working_dir=working_dir,
        ttl_buffer=1000,
        network=network,
        era=f"--{era}-era",
    )

    # After test, remove temporary test files
    test_files = ["protocol.json"]
    for test_file in test_files:
        filepath = os.path.join(working_dir, test_file)
        if os.path.exists(filepath):
            os.remove(filepath)


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


def test_get_protocol_parameters(cli_node):
    params = cli_node.get_protocol_parameters()
    assert "protocolVersion" in params


def test_get_min_utxo(cli_node):
    min_utxo = cli_node.get_min_utxo()
    assert min_utxo > 0


def test_days2slots(cli_node, working_dir, shelley_genesis):
    cli_node.days2slots(1, shelley_genesis)


def test_days2epochs(cli_node):
    pass


def test_make_address(cli_node):
    pass


def test_get_key_hash(cli_node):
    pass


def test_get_utxos(cli_node):
    pass


def test_query_balance(cli_node):
    pass


def test_calc_min_fee(cli_node):
    pass


def test_send_payment(cli_node):
    pass


def test_register_stake_address(cli_node):
    pass


def test_generate_kes_keys(cli_node):
    pass


def test_create_block_producing_keys(cli_node):
    pass


def test_update_kes_keys(cli_node):
    pass


def test_create_metadata_file(cli_node):
    pass


def test_generate_stake_pool_cert(cli_node):
    pass


def test_generate_delegation_cert(cli_node):
    pass


def test_build_raw_transaction(cli_node):
    pass


def test_build_multisignature_scripts(cli_node):
    pass


def test_witness_transaction(cli_node):
    pass


def test_sign_transaction(cli_node):
    pass


def test_submit_transaction(cli_node):
    pass


def test_register_stake_pool(cli_node):
    pass


def test_update_stake_pool_registration(cli_node):
    pass


def test_retire_stake_pool(cli_node):
    pass


def test_get_stake_pool_id(cli_node):
    pass


def test_convert_itn_keys(cli_node):
    pass


def test_get_rewards_balance(cli_node):
    pass


def test_empty_account(cli_node):
    pass


def test_generate_policy(cli_node):
    pass


def test_build_send_tx(cli_node):
    pass


def test_build_mint_transaction(cli_node):
    pass


def test_build_burn_transaction(cli_node):
    pass
