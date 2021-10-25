#!/usr/bin/env python3
# Cardano-Tools Example: Check wallet balance.
import logging
import os

#### Using the dev version of the package ####
import sys
sys.path.append('../')
from cardano_tools import WalletToolsHTTP


if __name__ == "__main__":

    cw_http = WalletToolsHTTP(
        wallet_server="http://127.0.0.1",
        wallet_server_port=8090
    )

    logging.basicConfig(level=logging.DEBUG)

    pmts = [
        {
            "address": "addr1....",
            "amount": {
                "quantity": int(310.23*1_000_000),
                "unit": "lovelace"
            },
            "assets": []
        },
        {
            "address": "addr1....",
            "amount": {
                "quantity": int(212.34*1_000_000),
                "unit": "lovelace"
            },
            "assets": []
        }
    ]

    wallet = cw_http.get_wallet_by_name("ExampleWallet")

    # Get the passphrase from an env variable. DO NOT store in script.
    # Example ZSH shell command to save the password in a local variable
    # without it being stored in the command history:
    #
    #     $ read "?Enter passphrase: " WALLET_PASSPHRASE
    #     $ export WALLET_PASSPHRASE
    #
    passphrase = os.getenv('WALLET_PASSPHRASE')

    cw_http.send_batch_tx(
        wallet.get("id"),
        pmts,
        passphrase,
        wait=True
    )
