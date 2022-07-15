import logging
import math

from cardano_tools import WalletCLI, WalletHTTP

logging.basicConfig(level=logging.INFO)


def generate_mnemonic():
    print("Generating new mnemonic phrase")
    cw_cli = WalletCLI(path_to_cli="cardano-wallet")
    return cw_cli.recovery_phrase_generate()


def cli_demo(wallet_name: str, mnemonic: str, cleanup: bool = False):
    cw_cli = WalletCLI(path_to_cli="cardano-wallet")

    print("CLI: Creating new wallet")
    cw_cli.create_wallet(wallet_name, mnemonic, "$3cur3p@$$ph@$3")

    print("CLI: Getting wallet by name")
    wallet: dict = cw_cli.get_wallet_by_name(wallet_name)

    print("CLI: Getting wallet by ID")
    wallet_by_id: dict = cw_cli.get_wallet(wallet.get("id"))
    assert wallet_by_id.get("id") == wallet.get("id")

    print("CLI: Getting ADA balance from metadata")
    balance = wallet.get("balance").get("total").get("quantity") / 1_000_000

    print("CLI: Getting ADA balance using builtin method")
    balance_builtin = cw_cli.get_balance(wallet.get("id"))
    assert math.isclose(balance, balance_builtin)

    if cleanup:
        print("CLI: Deleting wallet")
        cw_cli.delete_wallet(wallet.get("id"))


def http_demo(wallet_name: str, mnemonic: str, cleanup: bool = False):
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

    if cleanup:
        print("HTTP: Deleting wallet")
        cw_api.delete_wallet(wallet.get("id"))


if __name__ == "__main__":
    mnemonic = generate_mnemonic()
    # cli_demo("CliRandomWallet", mnemonic, cleanup=True)
    http_demo("HttpTestWallet", mnemonic, cleanup=True)
