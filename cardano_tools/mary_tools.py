from datetime import datetime
from pathlib import Path
import sys

# Cardano-Tools components
from .shelley_tools import ShelleyTools


class MaryError(Exception):
    pass


class MaryTools:
    def __init__(self, shelley_tools):
        self._debug = False
        self.shelley = shelley_tools

    @property
    def debug(self):
        return self._debug

    @debug.setter
    def debug(self, d):
        self._debug = d
        self.shelley.debug = d

    def send_asset(self, amt, to_addr, from_addr, policy_id, asset_name=None):
        """Send integer number of assets from one address to another.

        Parameters
        ----------
        amt : float
            Amount of ADA to send (before fee).
        to_addr : str
            Address to send the ADA to.
        from_addr : str
            Address to send the ADA from.
        key_file : str or Path
            Path to the send address signing key file.
        offline: bool, optional
            Flag to indicate if the transactions is being generated offline.
            If true (defaults to false), the transaction file is signed but
            not sent.
        cleanup : bool, optional
            Flag that indicates if the temporary transaction files should be
            removed when finished (defaults to True).
        """

        # Get a list of UTXOs
        utxos = self.shelley.get_utxos(from_addr)
        print(utxos)
        # Filter the UTXOs that have the asset
        # utxos = [u in utxos if ]

        # Sort the UTXOs (by decending value)
        # utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

    def generate_policy(self, script_path) -> str:
        """Generate a minting policy ID.

        Parameters
        ----------
        script_path : str or Path
            Path to the minting policy definition script.
        
        Returns
        -------
        str
            The minting policy id (script hash). 
        """

        # Submit the transaction
        result = self.shelley.run_cli(
            f"{self.shelley.cli} transaction policyid "
            f" --script-file {script_path}"
        )
        return result.stdout

    def build_mint_transaction(
        self,
        quantity,
        policy_id,
        asset_name,
        payment_addr,
        witness_count,
        tx_metadata=None,
        folder=None,
        cleanup=True,
    ) -> str:
        """Build the transaction for minting a new native asset.

        Requires a running and synced node.

        Parameters
        ----------
        quantity : int
            The number of the assets to mint.
        policy_id : str
            The minting policy ID (generated from the signature script).
        asset_name : str
            The name of the asset.
        payment_addr : str
            The address paying the minting fees. Will also own the tokens.
        witness_count : int
            The number of signing keys.
        tx_metadata : str or Path, optional
            Path to the metadata stored in a JSON file.
        folder : str or Path, optional
            The working directory for the function. Will use the Shelley
            object's working directory if node is given.
        cleanup : bool, optional
            Flag that indicates if the temporary transaction files should be
            removed when finished (defaults to True).

        Return
        ------
        str
            Path to the mint transaction file generated.
        """

        # Get a working directory to store the generated files and make sure
        # the directory exists.
        if folder is None:
            folder = self.shelley.working_dir
        else:
            folder = Path(folder)
            if self.shelley.ssh is None:
                folder.mkdir(parents=True, exist_ok=True)
            else:
                self.shelley._ShelleyTools__run(f'mkdir -p "{folder}"')

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.shelley.get_utxos(
            payment_addr,
            filter="Lovelace"
        )
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()

        # Create minting string
        mint_str = f"{quantity} {policy_id}.{asset_name}"

        # Create a metadata string
        meta_str = ""
        if tx_metadata is not None:
            meta_str = f"--metadata-json-file {tx_metadata}"

        # Iterate through the UTXOs until we have enough funds to cover the
        # transaction. Also, create the tx_in string for the transaction.
        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")
        utxo_total = 0
        min_fee = 1  # make this start greater than utxo_total
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            utxo_count = idx + 1
            utxo_total += int(utxo["Lovelace"])
            tx_in_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

            # Build a transaction draft to use for the min fee calculation
            self.shelley.run_cli(
                f'{self.shelley.cli} transaction build-raw {tx_in_str}'
                f'--tx-out "{payment_addr}+{utxo_total}+{mint_str}" '
                f'--ttl 0 --fee 0 --mint "{mint_str}" {meta_str} ' 
                f'{self.shelley.era} --out-file {tx_draft_file}'
            )

            # Calculate the minimum fee
            min_fee = self.shelley.calc_min_fee(
                tx_draft_file, utxo_count, tx_out_count=1, witness_count=witness_count
            )

            # If we have enough Lovelaces to cover the transaction can stop
            # iterating through the UTXOs.
            if utxo_total > min_fee:
                break

        # Handle the error case where there is not enough inputs for the output
        if utxo_total < min_fee:
            if utxo_total == 0:
                # This is the case where the sending wallet has no UTXOs to spend.
                # The above for loop didn't run at all which is why the
                # utxo_total is zero.
                raise MaryError(
                    f"Transaction failed due to insufficient funds. Account "
                    f"{payment_addr} is empty."
                )
            cost_ada = min_fee / 1_000_000
            utxo_total_ada = utxo_total / 1_000_000
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{payment_addr} cannot pay tranction costs of {cost_ada} "
                f"ADA because it only contains {utxo_total_ada} ADA."
            )

        # Setup the new UTXO
        min_fee = min_fee
        utxo_amt = utxo_total - min_fee
        if utxo_amt < self.shelley.protocol_parameters["minUTxOValue"]:
            # Verify that the UTXO is larger than the minimum.
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{payment_addr} cannot pay tranction costs of {cost_ada} "
                f"ADA because it only contains {utxo_total_ada} ADA."
            )

        # Build the transaction to the blockchain.
        tx_raw_file = Path(self.shelley.working_dir) / (tx_name + ".raw")
        self.shelley.run_cli(
                f'{self.shelley.cli} transaction build-raw {tx_in_str}'
                f'--tx-out "{payment_addr}+{utxo_amt}+{mint_str}" '
                f'--ttl {ttl} --fee {min_fee} --mint "{mint_str}" {meta_str} ' 
                f'{self.shelley.era} --out-file {tx_raw_file}'
            )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file

    def build_multi_mint_transaction(
        self,
        quantities,
        policy_id,
        asset_names,
        payment_addr,
        witness_count,
        tx_metadata=None,
        folder=None,
        cleanup=True,
    ) -> str:
        """Build the transaction for minting a new native asset.

        Requires a running and synced node.

        Parameters
        ----------
        Parameters
        ----------
        quantity : list
            List of the numbers of each asset to mint.
        policy_id : str
            The minting policy ID generated from the signature script--the 
            same for all assets.
        asset_name : list
            List of asset names (same size as quantity list).
        payment_addr : str
            The address paying the minting fees. Will also own the tokens.
        witness_count : int
            The number of signing keys.
        tx_metadata : str or Path, optional
            Path to the metadata stored in a JSON file.
        folder : str or Path, optional
            The working directory for the function. Will use the Shelley
            object's working directory if node is given.
        cleanup : bool, optional
            Flag that indicates if the temporary transaction files should be
            removed when finished (defaults to True).

        Return
        ------
        str
            Path to the mint transaction file generated.
        """

        # Get a working directory to store the generated files and make sure
        # the directory exists.
        if folder is None:
            folder = self.shelley.working_dir
        else:
            folder = Path(folder)
            if self.shelley.ssh is None:
                folder.mkdir(parents=True, exist_ok=True)
            else:
                self.shelley._ShelleyTools__run(f'mkdir -p "{folder}"')

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.shelley.get_utxos(
            payment_addr,
            filter="Lovelace"
        )
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()

        # Create minting string
        for i, name in enumerate(asset_names):
            if i == 0:
                mint_str = f"{quantities[i]} {policy_id}.{name}"
            else:
                mint_str += f" + {quantities[i]} {policy_id}.{name}"

        # Create a metadata string
        meta_str = ""
        if tx_metadata is not None:
            meta_str = f"--metadata-json-file {tx_metadata}"

        # Iterate through the UTXOs until we have enough funds to cover the
        # transaction. Also, create the tx_in string for the transaction.
        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")
        utxo_total = 0
        min_fee = 1  # make this start greater than utxo_total
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            utxo_count = idx + 1
            utxo_total += int(utxo["Lovelace"])
            tx_in_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

            # Build a transaction draft
            self.shelley.run_cli(
                f'{self.shelley.cli} transaction build-raw {tx_in_str}'
                f'--tx-out "{payment_addr}+{utxo_total}+{mint_str}" '
                f'--ttl 0 --fee 0 --mint "{mint_str}" {meta_str} ' 
                f'{self.shelley.era} --out-file {tx_draft_file}'
            )

            # Calculate the minimum fee
            min_fee = self.shelley.calc_min_fee(
                tx_draft_file, utxo_count, tx_out_count=1, witness_count=witness_count
            )

            # If we have enough Lovelaces to cover the transaction can stop
            # iterating through the UTXOs.
            if utxo_total > min_fee:
                break

        # Handle the error case where there is not enough inputs for the output
        if utxo_total < min_fee:
            if utxo_total == 0:
                # This is the case where the sending wallet has no UTXOs to spend.
                # The above for loop didn't run at all which is why the
                # utxo_total is zero.
                raise MaryError(
                    f"Transaction failed due to insufficient funds. Account "
                    f"{payment_addr} is empty."
                )
            cost_ada = min_fee / 1_000_000
            utxo_total_ada = utxo_total / 1_000_000
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{payment_addr} cannot pay tranction costs of {cost_ada} "
                f"ADA because it only contains {utxo_total_ada} ADA."
            )

        # Setup the new UTXO
        utxo_amt = utxo_total - min_fee
        print(utxo_amt)
        if utxo_amt < self.shelley.protocol_parameters["minUTxOValue"]:
            # Verify that the UTXO is larger than the minimum.
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{payment_addr} cannot pay tranction costs of {cost_ada} "
                f"ADA because it only contains {utxo_total_ada} ADA."
            )

        # Build the transaction to the blockchain.
        tx_raw_file = Path(self.shelley.working_dir) / (tx_name + ".raw")
        self.shelley.run_cli(
                f'{self.shelley.cli} transaction build-raw {tx_in_str}'
                f'--tx-out "{payment_addr}+{utxo_amt}+{mint_str}" '
                f'--ttl {ttl} --fee {min_fee} --mint "{mint_str}" {meta_str} ' 
                f'{self.shelley.era} --out-file {tx_raw_file}'
            )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file
