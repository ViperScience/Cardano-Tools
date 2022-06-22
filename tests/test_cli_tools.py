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


def test_load_protocol_parameters(cli_node):
    pass


def test_calc_min_utxo(cli_node):
    pass


def test_days2slots(cli_node):
    pass


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
