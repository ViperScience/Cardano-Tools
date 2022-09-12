import os

import pytest

from cardano_tools import WalletCLI, WalletHTTP, wallet_tools


# Test requirements: testnet, wallets, nonzero ADA balance, nonzero token balance
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


def test_stub(wallets_have_balance, era, is_testnet):
    assert wallets_have_balance
    assert is_testnet
    assert era == "babbage"
