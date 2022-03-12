from cardano_tools import WalletCLI
import logging


if __name__ == "__main__":

    cw_cli = WalletCLI(
        path_to_cli="/usr/local/bin/cardano-wallet"
    )

    logging.basicConfig(level=logging.DEBUG)

    # Find the wallet
    wallet = cw_cli.get_wallet_by_name("ADDER_Rewards")
  
    # Print the balance (ADA)
    print(int(wallet["balance"]["total"]["quantity"])/1_000_000)

    # Use the built-in method
    print(cw_cli.get_wallet_balance(wallet["id"]))
