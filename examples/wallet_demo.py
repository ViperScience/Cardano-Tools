import logging
import math

from cardano_tools import WalletCLI, WalletHTTP

logging.basicConfig(level=logging.INFO)


def generate_mnemonic():
    """We need to use the CLI API to generate the mnemonmic, as it is not supported
    by the HTTP API. We use HTTP for everything else.
    """
    print("Generating new mnemonic phrase")
    cw_cli = WalletCLI(path_to_cli="cardano-wallet")
    return cw_cli.recovery_phrase_generate()


def wallet_demo(wallet_name: str, mnemonic: str, cleanup: bool = False):
    cw_api = WalletHTTP()

    print("Creating wallet")
    cw_api.create_wallet(wallet_name, mnemonic.split(" "), "$3cur3p@$$ph@$3")

    print("Getting wallet by name")
    wallet: dict = cw_api.get_wallet_by_name(wallet_name)
    wallet_id: str = wallet.get("id")

    print("Getting wallet by ID")
    wallet_by_id: dict = cw_api.get_wallet(wallet_id)
    assert wallet_by_id.get("id") == wallet_id

    balance = wallet.get("balance").get("total").get("quantity") / 1_000_000
    print(f"Getting ADA balance from metadata: {balance}")

    balance_builtin = cw_api.get_balance(wallet_id)[0].get("quantity")
    print(f"Getting ADA balance using builtin method: {balance_builtin}")
    assert math.isclose(balance, balance_builtin)

    print(f"First address of wallet: {cw_api.get_addresses(wallet_id)[0]}")

    print("Getting UTxO stats")
    print(cw_api.get_utxo_stats(wallet_id))

    print("Getting UTxO snapshot")
    print(cw_api.get_utxo_snapshot(wallet_id))

    if cleanup:
        print("Deleting wallet")
        cw_api.delete_wallet(wallet_id)


if __name__ == "__main__":
    mnemonic = generate_mnemonic()
    wallet_demo("TestWallet", mnemonic, cleanup=True)
