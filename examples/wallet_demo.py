import logging
import math

from cardano_tools import WalletCLI, WalletHTTP

logging.basicConfig(level=logging.INFO)


def cli_demo(wallet_name: str, cleanup: bool = False):
    cw_cli = WalletCLI(path_to_cli="cardano-wallet")

    # Generate a seed phrase
    phrase = cw_cli.recovery_phrase_generate()

    # Create wallet from seed phrase
    cw_cli.create_wallet(wallet_name, phrase, "$3cur3p@$$ph@$3")

    # Find wallet by name
    wallet: dict = cw_cli.get_wallet_by_name(wallet_name)

    # Find wallet by id
    wallet_by_id: dict = cw_cli.get_wallet(wallet.get("id"))
    assert wallet_by_id.get("id") == wallet.get("id")

    # Print the balance (ADA)
    balance = wallet.get("balance").get("total").get("quantity") / 1_000_000

    # Use the built-in method
    balance_builtin = cw_cli.get_balance(wallet.get("id"))
    assert math.isclose(balance, balance_builtin)

    if cleanup:
        # Delete wallet
        cw_cli.delete_wallet(wallet.get("id"))


def api_demo(wallet_name: str, cleanup: bool = False):
    cw_api = WalletHTTP()

    # Find wallet by name
    wallet: dict = cw_api.get_wallet_by_name(wallet_name)

    # Find wallet by id
    wallet_by_id: dict = cw_api.get_wallet(wallet.get("id"))
    assert wallet_by_id.get("id") == wallet.get("id")

    # Print the balance (ADA)
    balance = wallet.get("balance").get("total").get("quantity") / 1_000_000

    # Use the built-in method
    balance_builtin = cw_api.get_balance(wallet.get("id"))[0].get("quantity")
    assert math.isclose(balance, balance_builtin)


if __name__ == "__main__":
    cli_demo("TestWallet1")
    api_demo("TestWallet1")
