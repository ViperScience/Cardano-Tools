from cardano_tools import WalletCLI
import logging


if __name__ == "__main__":

    cw_cli = WalletCLI(path_to_cli="cardano-wallet")

    logging.basicConfig(level=logging.DEBUG)

    phrase = cw_cli.recovery_phrase_generate()

    # Create wallet
    cw_cli.create_wallet("TestWallet3", phrase, "$3cur3p@$$ph@$3", address_pool_gap=10)

    # Find wallet
    wallet = cw_cli.get_wallet_by_name("TestWallet3")
    # print(cw_cli.get_all_wallets())

    # Print the balance (ADA)
    # print(int(wallet["balance"]["total"]["quantity"]) / 1_000_000)

    # # Use the built-in method
    # print(cw_cli.get_wallet_balance(wallet["id"]))
