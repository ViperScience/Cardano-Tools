import json
import os
import pdb

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
def new_mnemonic(cli_api):
    return cli_api.recovery_phrase_generate()


@pytest.fixture
def passphrase() -> str:
    return "$3cur3p@$$ph@$3"


@pytest.fixture
def w1_seed() -> str:
    return "fragile pottery wolf snack wet dolphin wish guard step track second rally panda desk because hollow route carpet ghost worry address ecology frown join"


@pytest.fixture
def w1_name() -> str:
    return "TestWallet1"


@pytest.fixture
def w2_seed() -> str:
    return "evoke pull giraffe enhance beach ripple alien pottery beach bubble rail hold finish slice power parade brief rough fame type hungry guilt tail cabbage"


@pytest.fixture
def w2_name() -> str:
    return "TestWallet2"


@pytest.fixture
def wallet1(http_api, passphrase, w1_seed, w1_name) -> dict:
    # Restore test wallets if they don't already exist
    if not http_api.get_wallet_by_name(w1_name):
        http_api.create_wallet(w1_name, w1_seed.split(" "), passphrase)
    return http_api.get_wallet_by_name(w1_name)


@pytest.fixture
def w1_id(wallet1) -> str:
    return wallet1.get("id")


@pytest.fixture
def wallet2(http_api, passphrase, w2_seed, w2_name) -> dict:
    # Restore test wallets if they don't already exist
    if not http_api.get_wallet_by_name(w2_name):
        http_api.create_wallet(w2_name, w2_seed.split(" "), passphrase)
    return http_api.get_wallet_by_name(w2_name)


@pytest.fixture
def w2_id(wallet2) -> str:
    return wallet2.get("id")


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
def wallets_have_ada(wallet1, wallet2) -> bool:
    if (
        wallet1.get("balance").get("total").get("quantity") > 10
        and wallet2.get("balance").get("total").get("quantity") > 10
    ):
        return True
    return False


@pytest.fixture
def wallets_have_tokens(wallet1, wallet2) -> bool:
    if (
        len(wallet1.get("assets").get("available")) > 0
        and len(wallet2.get("assets").get("available")) > 0
    ):
        return True
    return False


# Custom pytest decorator to only run these tests if the host has cardano-wallet running
def wallet_server_exists():
    try:
        requests.get("http://localhost:8090/v2/network/information")
    except:
        return False
    return True


wallet_running = pytest.mark.skipif(
    not wallet_server_exists(),
    reason="These tests require cardano-wallet to be running",
)


@wallet_running
class TestWalletTools:
    # Wallets tests
    def test_create_wallet(self, wallet1, w1_name, wallet2, w2_name):
        # We've already tested this function in the fixture
        assert wallet1.get("name") == w1_name
        assert wallet2.get("name") == w2_name

    def test_create_wallet_from_key(self, http_api):
        pytest.skip()

    def test_rename_wallet(self, http_api, wallet1, w1_name, w1_id):
        new_name = "Changed Name"
        updated_w1 = http_api.rename_wallet(w1_id, new_name)
        assert updated_w1.get("name") == new_name
        # Change back to old name
        updated_w1 = http_api.rename_wallet(w1_id, w1_name)

    def test_update_passphrase(self, http_api, passphrase, w1_id):
        new_passphrase = "This Is A New Passphrase 12345"
        updated_w1 = http_api.update_passphrase(w1_id, passphrase, new_passphrase)
        assert updated_w1
        # Change back to original passphrase
        updated_w1 = http_api.update_passphrase(w1_id, new_passphrase, passphrase)

    def test_delete_wallet(self, http_api, new_mnemonic, w1_id):
        # Create a new wallet for us to delete
        http_api.create_wallet("TempWallet", new_mnemonic.split(" "), "passphrase")
        temp_wallet = http_api.get_wallet_by_name("TempWallet")
        assert temp_wallet.get("id") != {}
        http_api.delete_wallet(temp_wallet.get("id"))
        assert http_api.get_wallet(temp_wallet.get("id")) == {}

    def test_get_all_wallets(self, http_api):
        wallets = http_api.get_all_wallets()
        assert len(wallets) >= 2

    def test_get_wallet(self, http_api, wallet1, w1_id):
        w1_by_id = http_api.get_wallet(w1_id)
        assert w1_by_id.get("id") == w1_id

    def test_get_wallet_by_name(self, http_api, wallet1, w1_name):
        w1_by_name = http_api.get_wallet_by_name(w1_name)
        assert w1_by_name == wallet1

    def test_get_balance(self, http_api, w1_id):
        lovelace_balance_dict, token_balance = http_api.get_balance(w1_id)
        ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        assert isinstance(ada_balance, float)
        assert isinstance(token_balance, list)

    def test_get_utxo_stats(self, http_api, w1_id):
        stats = http_api.get_utxo_stats(w1_id)
        assert stats.get("distribution")

    def test_get_utxo_snapshot(self, http_api, w1_id):
        snapshot = http_api.get_utxo_snapshot(w1_id)
        assert snapshot.get("entries")

    # Assets tests
    def test_get_assets(self, wallets_have_tokens, http_api, w1_id):
        if not wallets_have_tokens:
            pytest.skip(reason="No tokens in test wallets.")
        for token in http_api.get_assets(w1_id):
            assert isinstance(token.get("policy_id"), str)
            assert isinstance(token.get("asset_name"), str)

    def test_get_asset(self, wallets_have_tokens, http_api, w1_id):
        if not wallets_have_tokens:
            pytest.skip(reason="No tokens in test wallets.")
        # Get first token in wallet
        tokens = http_api.get_assets(w1_id)
        token = tokens[0]
        test_token = http_api.get_asset(w1_id, token.get("policy_id"), token.get("asset_name"))
        assert test_token.get("policy_id") == token.get("policy_id")
        assert test_token.get("asset_name") == token.get("asset_name")

    # Addresses tests
    def test_get_addresses(self, http_api, w1_id):
        addrs = http_api.get_addresses(w1_id)
        assert len(addrs) > 0
        assert isinstance(addrs[0], str)
        assert addrs[0].startswith("addr")

    def test_inspect_address(self, http_api, w1_id):
        addr = http_api.get_addresses(w1_id)[0]
        inspect = http_api.inspect_address(addr)
        assert isinstance(inspect.get("spending_key_hash"), str)
        assert isinstance(inspect.get("address_style"), str)
        assert isinstance(inspect.get("address_type"), int)

    def test_get_transaction(self, http_api, w1_id):
        txs = http_api.get_transactions(w1_id)
        assert len(txs) > 0
        assert isinstance(txs[0].get("id"), str)
        tx = http_api.get_transaction(w1_id, txs[0].get("id"))
        assert tx == txs[0]

    def test_get_transactions(self, http_api, w1_id):
        txs = http_api.get_transactions(w1_id)
        assert len(txs) > 0
        assert isinstance(txs[0].get("id"), str)

    def test_forget_transaction(self, http_api, w1_id):
        """Note: This function cannot be tested reliably.
        forget_transaction tries to forget a pending transaction.
        For this test, we'll just make sure the function runs on an
        existing transaction"""
        tx = http_api.get_transactions(w1_id)[0]
        http_api.forget_transaction(w1_id, tx.get("id"))
        assert True

    def test_confirm_tx(self, http_api, w1_id):
        tx = http_api.get_transactions(w1_id)[0]
        assert http_api.confirm_tx(w1_id, tx.get("id"))

    # Transactions tests
    @pytest.mark.skip(reason="Skipping for now to speed up test execution")
    def test_estimate_tx_fee(self, wallets_have_ada, http_api, w1_id, w2_id):
        if not wallets_have_ada:
            pytest.skip(reason="Wallets must have an ada balance")
        addr = http_api.get_addresses(w2_id)[0]
        result = http_api.estimate_tx_fee(w1_id, addr, 10e6)
        fee = result.get("estimated_max").get("quantity")
        assert 150000 < fee < 200000

    @pytest.mark.skip(reason="Skipping for now to speed up test execution")
    def test_send_lovelace(self, wallets_have_ada, http_api, w1_id, w2_id, passphrase):
        if not wallets_have_ada:
            pytest.skip(reason="Wallets must have an ada balance")
        addr = http_api.get_addresses(w2_id)[0]
        lovelace_balance_dict, token_balance = http_api.get_balance(w2_id)
        orig_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        # Send 1 ada from wallet 1 to wallet 2
        http_api.send_lovelace(w1_id, addr, 1e6, passphrase, wait=True)
        lovelace_balance_dict, token_balance = http_api.get_balance(w2_id)
        new_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        assert int(new_ada_balance - orig_ada_balance) == 1

    @pytest.mark.skip(reason="Skipping for now to speed up test execution")
    def test_send_ada(self, wallets_have_ada, http_api, w1_id, w2_id, passphrase):
        if not wallets_have_ada:
            pytest.skip(reason="Wallets must have an ada balance")
        addr = http_api.get_addresses(w2_id)[0]
        lovelace_balance_dict, token_balance = http_api.get_balance(w2_id)
        orig_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        # Send 1 ada from wallet 1 to wallet 2
        http_api.send_ada(w1_id, addr, 1, passphrase, wait=True)
        lovelace_balance_dict, token_balance = http_api.get_balance(w2_id)
        new_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        assert int(new_ada_balance - orig_ada_balance) == 1

    def test_send_tokens(self, wallets_have_tokens, http_api, w1_id, w2_id, passphrase):
        if not wallets_have_tokens:
            pytest.skip(reason="Wallets must have an token balance")
        # TODO: Need to mint tokens to test with
        pdb.set_trace()
        assert False

    @pytest.mark.skip(reason="Skipping for now to speed up test execution")
    def test_send_batch_tx(self, wallets_have_ada, http_api, w1_id, w2_id, passphrase):
        if not wallets_have_ada:
            pytest.skip(reason="Wallets must have an ada balance")
        addr1 = http_api.get_addresses(w1_id)[0]
        addr2 = http_api.get_addresses(w1_id)[1]
        lovelace_balance_dict, token_balance = http_api.get_balance(w1_id)
        orig_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        # Send 2 ada from wallet 2 to wallet 1
        payments = [
            {"address": addr1, "amount": {"quantity": 1e6, "unit": "lovelace"}},
            {"address": addr2, "amount": {"quantity": 1e6, "unit": "lovelace"}},
        ]
        http_api.send_batch_tx(w2_id, payments, passphrase, wait=True)
        lovelace_balance_dict, token_balance = http_api.get_balance(w1_id)
        new_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        assert int(new_ada_balance - orig_ada_balance) == 2

    # Transactions (new) tests
    @pytest.mark.skip(reason="Skipping for now to speed up test execution")
    def test_new_transactions(self, wallets_have_ada, http_api, w1_id, w2_id, passphrase):
        if not wallets_have_ada:
            pytest.skip(reason="Wallets must have an ada balance")
        addr = http_api.get_addresses(w2_id)[0]
        payload = json.loads(
            f"""{{
                "payments": [
                    {{
                        "address": "{addr}",
                        "amount": {{
                            "quantity": 1e6,
                            "unit": "lovelace"
                        }}
                    }}
                ],
                "withdrawal": "self",
                "validity_interval": {{
                    "invalid_hereafter": {{
                        "quantity": 3600,
                        "unit": "second"
                    }}
                }},
                "encoding": "base16"
            }}"""
        )
        # Test construct_transaction
        tx = http_api.construct_transaction(w1_id, payload)
        encoded_tx = tx.get("transaction")
        assert isinstance(encoded_tx, str)
        # Test sign_transaction
        signed_tx = http_api.sign_transaction(w1_id, passphrase, encoded_tx)
        assert isinstance(signed_tx.get("transaction"), str)
        # Test decode_transaction
        decoded_tx = http_api.decode_transaction(w1_id, signed_tx.get("transaction"))
        assert decoded_tx.get("outputs")[0].get("address") == addr
        tx_id = decoded_tx.get("id")
        # Test submit_transaction
        lovelace_balance_dict, token_balance = http_api.get_balance(w2_id)
        orig_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        tx_output = http_api.submit_transaction(w1_id, signed_tx.get("transaction"))
        http_api.confirm_tx(w1_id, tx_id)
        lovelace_balance_dict, token_balance = http_api.get_balance(w2_id)
        new_ada_balance = lovelace_balance_dict.get("quantity") / 1e6
        assert int(new_ada_balance - orig_ada_balance) == 1

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
        assert isinstance(health.get("health"), str)

    # Network tests
    def test_get_network_info(self, http_api):
        info = http_api.get_network_info()
        assert isinstance(info.get("network_info"), dict)

    def test_get_network_clock(self, http_api):
        clock = http_api.get_network_clock()
        assert isinstance(clock.get("status"), str)

    def test_get_network_params(self, http_api):
        params = http_api.get_network_params()
        assert isinstance(params.get("genesis_block_hash"), str)

    # Settings tests
    def test_get_settings(self, http_api):
        settings = http_api.get_settings()
        assert isinstance(settings.get("pool_metadata_source"), str)

    def test_update_settings(self, http_api):
        smash_source = "direct"
        http_api.update_settings(smash_source)
        new_settings = http_api.get_settings()
        assert new_settings.get("pool_metadata_source") == smash_source

    # Node tests
    def test_get_latest_block_header(self, http_api):
        block_header = http_api.get_latest_block_header()
        pytest.skip(reason="This endpoint doesn't exist in the current cardano-wallet release")
