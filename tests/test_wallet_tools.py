import json
import os

import pytest
import requests

from cardano_tools import WalletCLI, WalletHTTP, wallet_tools


@pytest.fixture
def http_api() -> WalletHTTP:
    return WalletHTTP()


@pytest.fixture
def cli_api() -> WalletCLI:
    # This fixture requires the cardano-wallet binary to be on the system PATH
    return WalletCLI(path_to_cli="cardano-wallet")


@pytest.fixture
def wallets(http_api) -> tuple:
    """Test wallet #1"""
    w1_seed = "fragile pottery wolf snack wet dolphin wish guard step track second rally panda desk because hollow route carpet ghost worry address ecology frown join"
    w1_name = "TestWallet1"
    w2_seed = "evoke pull giraffe enhance beach ripple alien pottery beach bubble rail hold finish slice power parade brief rough fame type hungry guilt tail cabbage"
    w2_name = "TestWallet2"
    passphrase = "$3cur3p@$$ph@$3"

    # Restore test wallets if they don't already exist
    if not http_api.get_wallet_by_name(w1_name):
        print(f"Creating wallet: {w1_name}")
        http_api.create_wallet(w1_name, w1_seed.split(" "), passphrase)

    if not http_api.get_wallet_by_name(w2_name):
        print(f"Creating wallet: {w2_name}")
        http_api.create_wallet(w2_name, w2_seed.split(" "), passphrase)

    return http_api.get_wallet_by_name(w1_name), http_api.get_wallet_by_name(w2_name)


@pytest.fixture
def is_testnet(http_api) -> bool:
    """Returns True if cardano-node is running on the testnet rather than mainnet"""
    network_info = http_api.get_network_info()
    return network_info.get("network_info").get("network_id") == "testnet"


@pytest.fixture
def era(http_api) -> str:
    network_info = http_api.get_network_info()
    return network_info.get("node_era")


@pytest.fixture
def wallets_have_balance(wallets) -> bool:
    if (
        wallets[0].get("balance").get("total").get("quantity") > 10
        and wallets[1].get("balance").get("total").get("quantity") > 10
    ):
        return True
    return False


# Setup a pytest decorator to only run these tests if the host has cardano-wallet running
def wallet_server_exists():
    try:
        requests.get("http://localhost:8090/v2/network/information")
    except:
        return False
    return True


wallet_running = pytest.mark.skipif(
    not wallet_server_exists(),
    reason="Requires cardano-wallet to be running",
)

import pdb


@wallet_running
class TestWalletTools:
    # Wallets tests
    def test_create_wallet(self, http_api):
        pytest.skip()

    def test_create_wallet_from_key(self, http_api):
        pytest.skip()

    def test_rename_wallet(self, http_api):
        pytest.skip()

    def test_update_passphrase(self, http_api):
        pytest.skip()

    def test_delete_wallet(self, http_api):
        pytest.skip()

    def test_get_all_wallets(self, http_api):
        pytest.skip()

    def test_get_wallet(self, http_api):
        pytest.skip()

    def test_get_wallet_by_name(self, http_api):
        pytest.skip()

    def test_get_balance(self, http_api):
        pytest.skip()

    def test_get_utxo_stats(self, http_api):
        pytest.skip()

    def test_get_utxo_snapshot(self, http_api):
        pytest.skip()

    # Assets tests
    def test_get_assets(self, http_api):
        pytest.skip()

    def test_get_asset(self, http_api):
        pytest.skip()

    # Addresses tests
    def test_get_addresses(self, http_api):
        pytest.skip()

    def test_inspect_address(self, http_api):
        pytest.skip()

    def test_get_transaction(self, http_api):
        pytest.skip()

    def test_get_transactions(self, http_api):
        pytest.skip()

    def test_forget_transaction(self, http_api):
        pytest.skip()

    def test_confirm_tx(self, http_api):
        pytest.skip()

    # Transactions tests
    def test_estimate_tx_fee(self, http_api):
        pytest.skip()

    def test_send_lovelace(self, http_api):
        pytest.skip()

    def test_send_ada(self, http_api):
        pytest.skip()

    def test_send_tokens(self, http_api):
        pytest.skip()

    def test_send_batch_tx(self, http_api):
        pytest.skip()

    # Transactions (new) tests
    def test_construct_transaction(self, http_api):
        pytest.skip()

    def test_sign_transaction(self, http_api):
        pytest.skip()

    def test_decode_transaction(self, http_api):
        pytest.skip()

    def test_submit_transaction(self, http_api):
        pytest.skip()

    def test_(self, http_api):
        pytest.skip()

    # Migrations tests
    def test_create_migration_plan(self, http_api):
        pytest.skip()

    def test_migrate_wallet(self, http_api):
        pytest.skip()

    # Stake Pools tests
    def test_list_stake_keys(self, http_api):
        pytest.skip()

    def test_list_stake_pools(self, http_api):
        pytest.skip()

    def test_pool_maintenance_actions(self, http_api):
        pytest.skip()

    def test_trigger_pool_maintenance(self, http_api):
        pytest.skip()

    def test_estimate_delegation_fee(self, http_api):
        pytest.skip()

    def test_join_stake_pool(self, http_api):
        pytest.skip()

    def test_quit_staking(self, http_api):
        pytest.skip()

    # Keys tests
    def test_create_account_public_key(self, http_api):
        pytest.skip()

    def test_get_account_public_key(self, http_api):
        pytest.skip()

    def test_get_public_key(self, http_api):
        pytest.skip()

    def test_create_policy_id(self, http_api):
        pytest.skip()

    def test_create_policy_key(self, http_api):
        pytest.skip()

    def test_(self, http_api):
        pytest.skip()

    # Utils tests
    def test_get_smash_health(self, http_api):
        health = http_api.get_smash_health()
        assert health.get("health")

    # Network tests
    def test_get_network_info(self, http_api):
        info = http_api.get_network_info()
        assert info.get("network_info")

    def test_get_network_clock(self, http_api):
        clock = http_api.get_network_clock()
        assert clock.get("status")

    def test_get_network_params(self, http_api):
        params = http_api.get_network_params()
        assert params.get("genesis_block_hash")

    # Settings tests
    def test_get_settings(self, http_api):
        settings = http_api.get_settings()
        assert settings.get("pool_metadata_source")

    def test_update_settings(self, http_api):
        smash_source = "direct"
        http_api.update_settings(smash_source)
        new_settings = http_api.get_settings()
        assert new_settings.get("pool_metadata_source") == smash_source

    # Node tests
    def test_get_latest_block_header(self, http_api):
        block_header = http_api.get_latest_block_header()
        pytest.skip(reason="This endpoint doesn't exist in the current cardano-wallet release")
