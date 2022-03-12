from cardano_tools import WalletCLI
import logging
import json


if __name__ == "__main__":

    cw_cli = WalletCLI(path_to_cli="/usr/local/bin/cardano-wallet")

    logging.basicConfig(level=logging.DEBUG)

    # Find the ID of the wallet to delete
    wallet_to_delete = cw_cli.get_wallet_by_name("experimental_wallet")
    wallet_to_delete_id = wallet_to_delete["id"]

    # Remove the wallet specified by the ID
    cw_cli.delete_wallet(wallet_to_delete_id)
