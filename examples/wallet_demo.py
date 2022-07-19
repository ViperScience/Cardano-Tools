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

    print("HTTP: Creating wallet")
    cw_api.create_wallet(wallet_name, mnemonic.split(" "), "$3cur3p@$$ph@$3")

    print("HTTP: Getting wallet by name")
    wallet: dict = cw_api.get_wallet_by_name(wallet_name)

    print("HTTP: Getting wallet by ID")
    wallet_by_id: dict = cw_api.get_wallet(wallet.get("id"))
    assert wallet_by_id.get("id") == wallet.get("id")

    print("HTTP: Getting ADA balance from metadata")
    balance = wallet.get("balance").get("total").get("quantity") / 1_000_000

    print("HTTP: Getting ADA balance using builtin method")
    balance_builtin = cw_api.get_balance(wallet.get("id"))[0].get("quantity")
    assert math.isclose(balance, balance_builtin)

    print("HTTP: Getting UTxO stats")
    print(cw_api.get_utxo_stats(wallet.get("id")))

    print("HTTP: Getting UTxO snapshot")
    print(cw_api.get_utxo_snapshot(wallet.get("id")))

    if cleanup:
        print("HTTP: Deleting wallet")
        cw_api.delete_wallet(wallet.get("id"))


if __name__ == "__main__":
    mnemonic = generate_mnemonic()
    wallet_demo("TestWallet", mnemonic, cleanup=True)
