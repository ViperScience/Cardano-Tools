#!/usr/bin/env python3
# Cardano-Tools Example: Delete a wallet.
import logging
import json

#### Use the dev version of the package ####
import sys
sys.path.append('../')
from cardano_tools import WalletToolsCLI


if __name__ == "__main__":

    cw_cli = WalletToolsCLI(
        path_to_cli="/usr/local/bin/cardano-wallet"
    )

    logging.basicConfig(level=logging.DEBUG)

    # Find the ID of the wallet to delete
    wallet_to_delete = cw_cli.get_wallet_by_name("experimental_wallet")
    wallet_to_delete_id = wallet_to_delete["id"]

    # Remove the wallet specified by the ID
    cw_cli.delete_wallet(wallet_to_delete_id)
