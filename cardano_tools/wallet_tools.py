from collections import namedtuple
from pathlib import Path
import subprocess
import requests
import logging
import shlex
import json
import time

# Cardano-Tools components
from .utils import minimum_utxo


class WalletError(Exception):
    pass


class WalletCLI:
    def __init__(
        self,
        path_to_cli,
        port=8090,
        network="--mainnet",
    ):
        self.cli = path_to_cli
        self.network = network
        self.port = port
        self.logger = logging.getLogger(__name__)

    def run_cli(self, cmd):
        # Execute the commands locally
        # For network instances use the HTTP class.
        cmd = f"{self.cli} {cmd}"
        result = subprocess.run(shlex.split(cmd), capture_output=True)
        stdout = result.stdout.decode().strip()
        stderr = result.stderr.decode().strip()
        self.logger.debug(f'CMD: "{cmd}"')
        self.logger.debug(f'stdout: "{stdout}"')
        self.logger.debug(f'stderr: "{stderr}"')
        ResultType = namedtuple("Result", "stdout, stderr")
        return ResultType(stdout, stderr)

    def recovery_phrase_generate(self, size: int = 24) -> str:
        """Generate a recovery or seed phrase (mnemonic)."""
        result = self.run_cli(f"recovery-phrase generate --size={size}")
        return result.stdout

    def get_all_wallets(self):
        """Get a list of all created wallets known to the wallet service.

        Returns
        ----------
        list
            List of dicts each representing the wallet info.
        """
        wallet_list = []
        res = self.run_cli("wallet list")
        if len(res.stdout) > 0:
            wallet_list = json.loads(res.stdout)
        return wallet_list

    def get_wallet(self, wallet_id: str):
        """Find the wallet specified by the ID.

        Parameters
        ----------
        wallet_id : str
            The wallet ID.
        """

        res = self.run_cli(f"wallet get --port={self.port} {wallet_id}")
        if "ok" in res.stderr.lower():
            return json.loads(res.stdout)
        return None

    def get_wallet_by_name(self, name: str) -> str:
        """Find the wallet from the supplied name (case insensitive).

        Parameters
        ----------
        name : str
            The arbitrary name of the wallet supplied during creation.
        """

        # First get a list of all wallets known to the local install.
        all_wallets = self.get_all_wallets()
        for wallet in all_wallets:
            if wallet.get("name").lower() == name.lower():
                return wallet
        return None

    def delete_wallet(self, wallet_id: str):
        """Delete a wallet from cardano-wallet data by ID.

        Parameters
        ----------
        wallet_id : str
            The wallet ID.

        Raises
        ------
        WalletError
            If the wallet ID is not found.
        """
        res = self.run_cli(f"wallet delete --port {self.port} {wallet_id}")
        if len(res.stderr) > 3:  # stderr is "Ok." on success
            raise WalletError(res.stderr)

    def get_wallet_balance(self, wallet_id: str) -> float:
        """Get the wallet balance in ADA.

        Parameters
        ----------
        wallet_id : str
            The wallet ID.

        Returns
        ----------
        float
            The total wallet balance (including rewards) in ADA.
        """
        wallet = self.get_wallet(wallet_id)
        bal = float(wallet.get("balance").get("total").get("quantity"))
        return bal / 1_000_000  # Return the value in units of ADA


class WalletHTTP:
    def __init__(self, wallet_server, wallet_server_port):
        self.wallet_url = f"{wallet_server}:{wallet_server_port}/"
        self.logger = logging.getLogger(__name__)

    def get_network_params(self):
        """Returns the set of network parameters for the current epoch."""
        url = f"{self.wallet_url}v2/network/parameters"
        self.logger.debug(f"URL: {url}")
        r = requests.get(url)
        if r.status_code != 200:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        self.logger.debug(r.text)
        return payload

    def get_all_wallets(self):
        """Get a list of all created wallets known to the wallet service.

        Returns
        ----------
        list
            List of dicts each representing the wallet info.
        """
        url = f"{self.wallet_url}v2/wallets"
        self.logger.debug(f"URL: {url}")
        r = requests.get(url)
        if r.status_code != 200:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        self.logger.debug(r.text)
        return payload

    def get_wallet(self, wallet_id: str):
        """Find the wallet specified by the ID.

        Parameters
        ----------
        wallet_id : str
            The wallet ID.
        """
        url = f"{self.wallet_url}v2/wallets/{wallet_id}"
        self.logger.debug(f"URL: {url}")
        r = requests.get(url)
        if r.status_code != 200:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        self.logger.debug(r.text)
        return payload

    def get_wallet_by_name(self, name: str):
        """Find the wallet from the supplied name (case insensitive).

        Parameters
        ----------
        name : str
            The arbitrary name of the wallet supplied during creation.
        """

        # First get a list of all wallets known to the local install.
        all_wallets = self.get_all_wallets()
        for wallet in all_wallets:
            if wallet.get("name").lower() == name.lower():
                return wallet
        return None

    def get_balance(self, wallet_id: str):
        """Get balances of wallet"""
        url = f"{self.wallet_url}v2/wallets/{wallet_id}"
        self.logger.debug(f"URL: {url}")
        r = requests.get(url)
        if r.status_code != 200:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        lovelace_balance = payload.get("balance").get("total")
        asset_balances = payload.get("assets").get("total")
        return lovelace_balance, asset_balances

    def get_addresses(self, wallet_id: str):
        """Returns a list of addresses tracked by the provided wallet"""
        url = f"{self.wallet_url}v2/wallets/{wallet_id}/addresses"
        self.logger.debug(f"URL: {url}")
        r = requests.get(url)
        if r.status_code != 200:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        addresses = [elem.get("id") for elem in payload]
        return addresses

    def get_transacton(self, wallet_id: str, tx_id: str):
        """Pull information about the specified transaction."""
        self.logger.info(f"Querying information for transaction {tx_id}")
        url = f"{self.wallet_url}v2/wallets/{wallet_id}/transactions/{tx_id}"
        self.logger.debug(f"URL: {url}")
        r = requests.get(url)
        if not r.ok:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        self.logger.debug(r.text)
        return payload

    def confirm_tx(self, wallet_id: str, tx_id: str, timeout: float = 600, pause: float = 5):
        """Checks the given transaction and waits until it's submitted."""
        start_time = time.time()
        while True:
            tx_data = self.get_transacton(wallet_id, tx_id)
            self.logger.info(f"TX status: {tx_data.get('status')}")
            if tx_data.get("status") == "in_ledger":
                return True
            if tx_data.get("status") == "expired":
                return False
            if time.time() - start_time > timeout:
                raise WalletError("Timeout waiting for transaction confirmation.")
            self.logger.info("Transaction not yet confirmed, pausing before next check...")
            time.sleep(pause)

    def send_lovelace(
        self,
        wallet_id: str,
        rx_address: str,
        quantity: int,
        passphrase: str,
        wait: bool = False,
    ):
        """Sends the specified amount of lovelace to the provided address"""
        url = f"{self.wallet_url}v2/wallets/{wallet_id}/transactions"
        self.logger.debug(f"URL: {url}")
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
        }
        tx_body = {
            "passphrase": passphrase,
            "payments": [
                {
                    "address": rx_address,
                    "amount": {"quantity": quantity, "unit": "lovelace"},
                }
            ],
            "withdrawal": "self",
        }
        self.logger.debug(
            f"Sending {quantity:,} lovelace ({quantity / 1e6} ADA) to address {rx_address}..."
        )
        r = requests.post(url, json=tx_body, headers=headers)
        if not r.ok:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None
        payload = json.loads(r.text)
        if wait:
            tx_id = payload.get("id")
            self.confirm_tx(wallet_id, tx_id)
            return self.get_transacton(wallet_id, tx_id)
        return payload

    def send_ada(
        self,
        wallet_id: str,
        rx_address: str,
        quantity_ada: int,
        passphrase: str,
        wait: bool = False,
    ):
        """Sends the specified amount of ADA to the provided address"""
        return self.send_lovelace(wallet_id, rx_address, quantity_ada * 1_000_000, passphrase, wait)

    def send_tokens(
        self,
        wallet_id: str,
        rx_address: str,
        assets: list,
        passphrase: str,
        lovelace_amount: int = 0,
        wait: bool = False,
    ):
        """Sends the specified amount of tokens to the provided address

        assets is a list of dicts comprised of the following:
          {
              "policy_id": str, # unique mint value
              "asset_name": str, # token_id
              "quantity": int # 1
          }

        Note: There is a minimum amount of lovelace that must be included with
              token transactions. If the specified amount is less than this
              minimum value, it will be automatically calculated.
        """

        # Make sure we send at least the minimum lovelace amount
        min_lovelace = minimum_utxo(
            [f"{asset.get('policy_id')}.{asset.get('asset_name')}" for asset in assets],
            {
                "utxoCostPerWord": 34482,  # Const. from Alonzo genesis file
            },
        )
        if lovelace_amount < min_lovelace:
            lovelace_amount = min_lovelace

        url = f"{self.wallet_url}v2/wallets/{wallet_id}/transactions"
        self.logger.debug(f"URL: {url}")
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
        }
        tx_body = {
            "passphrase": passphrase,
            "payments": [
                {
                    "address": rx_address,
                    "amount": {"quantity": lovelace_amount, "unit": "lovelace"},
                    "assets": assets,
                }
            ],
            "withdrawal": "self",
        }
        self.logger.info(
            f"Sending {len(assets)} unique tokens and {lovelace_amount:,} lovelace ({lovelace_amount / 1e6} ADA) to address {rx_address}..."
        )
        r = requests.post(url, json=tx_body, headers=headers)
        if not r.ok:
            self.logger.error(f"Bad status code received: {r.status_code}, {r.text}")
            return None

        payload = json.loads(r.text)
        self.logger.debug(f"Tokens sent! Payload {payload}")
        if wait:
            tx_id = payload.get("id")
            self.confirm_tx(wallet_id, tx_id)
            return self.get_transacton(wallet_id, tx_id)
        return payload

    def send_batch_tx(
        self,
        wallet_id: str,
        payments: list,
        passphrase: str,
        wait: bool = False,
    ):
        """Sends a batch of transactions. Takes in a list of payments dicts of the following format:
        [
            {
                "address": "addr...",
                "amount": {
                    "quantity": <int>,
                    "unit": "lovelace"
                },
                "assets": [
                    {
                        "policy_id": <hex string>,
                        "asset_name": <str>, # ASCII-formatted hex string
                        "quantity": <int>
                    }
                ]
            }
        ]
        """

        for payment in payments:
            # Make sure we send at least the minimum lovelace amount
            assets = payment.get("assets")
            lovelace_amount = payment.get("amount").get("quantity")
            min_lovelace = minimum_utxo(
                [f"{asset.get('policy_id')}.{asset.get('asset_name')}" for asset in assets],
                {
                    "utxoCostPerWord": 34482,  # Const. from Alonzo genesis file
                },
            )
            if lovelace_amount < min_lovelace:
                payment["amount"]["quantity"] = min_lovelace

        url = f"{self.wallet_url}v2/wallets/{wallet_id}/transactions"
        self.logger.debug(f"URL: {url}")
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
        }
        tx_body = {
            "passphrase": passphrase,
            "payments": payments,
            "withdrawal": "self",
        }
        self.logger.debug(f"Sending batch of {len(payments)} payments...")
        r = requests.post(url, json=tx_body, headers=headers)
        if not r.ok:
            self.logger.error(f"ERROR: Bad status code received: {r.status_code}, {r.text}")
            return None

        payload = json.loads(r.text)
        self.logger.debug(f"Tokens sent! Payload {payload}")
        if wait:
            tx_id = payload.get("id")
            self.confirm_tx(wallet_id, tx_id)
            return self.get_transacton(wallet_id, tx_id)
        return payload


if __name__ == "__main__":
    # Not used as a script
    pass
