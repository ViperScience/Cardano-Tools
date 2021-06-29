from datetime import datetime
from os import rmdir
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

    def calc_min_utxo(
        self,
        assets,
    ) -> int:
        """Calculate the minimum UTxO value when assets are part of the
        transaction.

        The assets dictionary must be of the form:

            {
                "PLOICYID123": [
                    "assetname1",
                    "assetname2"
                ]
                "PLOICYID124": [
                    "assetname1"
                ]
            }

        Parameters
        ----------
        assets : dict
            A dictionary of assets with the Policy ID as the key.

        Returns
        -------
        int
            The minimum transaction output (Lovelace).
        """

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()

        # Get the minimum UTxO parameter
        min_utxo = self.shelley.protocol_parameters["minUTxOValue"]

        # Round the number of bytes to the minimum number of 8 byte words needed
        # to hold all the bytes.
        def round_up_bytes_to_words(b):
            return (b + 7) // 8

        # These are constants but may change in the future
        coin_Size = 0
        utxo_entry_size_without_val = 27
        ada_only_utxo_size = utxo_entry_size_without_val + coin_Size
        pid_size = 28

        # Get the number of unique policy IDs and token names in the bundle
        num_assets = len(assets.values())
        num_pids = len(assets)

        # The sum of the length of the ByteStrings representing distinct asset names
        names = []
        for k in assets.keys():
            for v in assets[k]:
                if v not in names:
                    names.append(v)
        sum_asset_name_lengths = sum([len(s.encode("utf-8")) for s in names])

        # The size of the token bundle in 8-byte long words
        size_bytes = 6 + round_up_bytes_to_words(
            ((num_assets) * 12) + sum_asset_name_lengths + (num_pids * pid_size)
        )

        return max(
            [
                min_utxo,
                (min_utxo // ada_only_utxo_size)
                * (utxo_entry_size_without_val + size_bytes),
            ]
        )

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
        return self.build_multi_mint_transaction(
            [quantity],
            policy_id,
            [asset_name],
            payment_addr,
            witness_count,
            tx_metadata=tx_metadata,
            folder=folder,
            cleanup=cleanup,
        )

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
        quantities : list
            List of the numbers of each asset to mint.
        policy_id : str
            The minting policy ID generated from the signature script--the
            same for all assets.
        asset_names : list
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
        utxos = self.shelley.get_utxos(payment_addr, filter="Lovelace")
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()
        min_utxo = self.shelley.protocol_parameters["minUTxOValue"]

        # Calculate the minimum UTxO
        min_output = self.calc_min_utxo({policy_id: asset_names})

        # Create minting string
        for i, name in enumerate(asset_names):
            if quantities[i] < 1:
                raise MaryError("Invalid quantity for minting!")
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
                f"{self.shelley.cli} transaction build-raw {tx_in_str}"
                f'--tx-out "{payment_addr}+{utxo_total}+{mint_str}" '
                f'--ttl 0 --fee 0 --mint "{mint_str}" {meta_str} '
                f"{self.shelley.era} --out-file {tx_draft_file}"
            )

            # Calculate the minimum fee
            min_fee = self.shelley.calc_min_fee(
                tx_draft_file,
                utxo_count,
                tx_out_count=1,
                witness_count=witness_count,
            )

            # If we have enough Lovelaces to cover the transaction can stop
            # iterating through the UTXOs.
            if utxo_total > (min_fee + min_output):
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
        if utxo_amt < min_output:
            # Verify that the UTXO is larger than the minimum.
            raise MaryError(
                f"Transaction failed due to insufficient funds. The UTxO is "
                f"{utxo_amt} lovelace which is smaller than the minimum UTxO "
                f"of {min_output} lovelace."
            )

        # Build the transaction to the blockchain.
        tx_raw_file = Path(self.shelley.working_dir) / (tx_name + ".raw")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {tx_in_str}"
            f'--tx-out "{payment_addr}+{utxo_amt}+{mint_str}" '
            f'--ttl {ttl} --fee {min_fee} --mint "{mint_str}" {meta_str} '
            f"{self.shelley.era} --out-file {tx_raw_file}"
        )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file

    def build_multi_burn_transaction(
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
        """Build the transaction for burning a native asset.

        Requires a running and synced node.

        Parameters
        ----------
        quantities : list
            List of the numbers of each asset to burn.
        policy_id : str
            The minting policy ID generated from the signature script--the
            same for all assets.
        asset_names : list
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

        # Users may send the quantities in as negative values since we are
        # burining. However, the quantities must be positive for the
        # calculations prior to the transaction. The negative sign will be
        # added to the mint inputs appropriately.
        quantities = [abs(q) for q in quantities]

        # Get a list of UTxOs for the transaction
        utxos = []
        input_str = ""
        input_lovelace = 0
        remaining_quantities = []
        for i, asset in enumerate(asset_names):

            # Find all the UTxOs containing the asset to be burned. This may take a while if there are a lot of tokens!
            filter_name = f"{policy_id}.{asset}"
            utxos_found = self.shelley.get_utxos(
                payment_addr, filter=filter_name
            )

            # Iterate through the UTxOs and only take enough needed to burn the
            # requested amount of tokens. Also, only create a list of unique
            # UTxOs.
            asset_count = 0
            for utxo in utxos_found:
                if utxo not in utxos:
                    utxos.append(utxo)

                    # If this is a unique UTxO being added to the list, keep
                    # track of the total Lovelaces and add it to the
                    # transaction input string.
                    input_lovelace += int(utxo["Lovelace"])
                    input_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

                asset_count += int(utxo[filter_name])
                if asset_count >= quantities[i]:
                    remaining_quantities.append(asset_count - quantities[i])
                    break

            if asset_count < quantities[i]:
                raise MaryError("Not enought tokens availible to burn.")

        # I don't think this can happen, but if it does something is wrong!
        if len(remaining_quantities) != len(quantities):
            raise MaryError("Something went wrong when finding UTxOs")

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()
        min_utxo = self.shelley.protocol_parameters["minUTxOValue"]

        # Create transaction strings for the tokens. The minting input string
        # and the UTxO string for any remaining tokens.
        output_assets = {}
        token_utxo_str = ""
        for i, asset_name in enumerate(asset_names):
            if i == 0:
                burn_str = f"{-1*quantities[i]} {policy_id}.{asset_name}"
            else:
                burn_str += f" + {-1*quantities[i]} {policy_id}.{asset_name}"
            if remaining_quantities[i] > 0:
                output_assets[policy_id] = asset_name
                token_utxo_str += (
                    f" + {remaining_quantities[i]} " f"{policy_id}.{asset_name}"
                )

        # Create a metadata string
        meta_str = ""
        if tx_metadata is not None:
            meta_str = f"--metadata-json-file {tx_metadata}"

        # Calculate the minimum fee and UTxO sizes for the transaction as it is
        # right now with only the minimum UTxOs needed for the tokens.
        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {input_str}"
            f'--tx-out "{payment_addr}+{input_lovelace}{token_utxo_str}" '
            f'--ttl 0 --fee 0 --mint "{burn_str}" {meta_str} '
            f"{self.shelley.era} --out-file {tx_draft_file}"
        )
        min_fee = self.shelley.calc_min_fee(
            tx_draft_file,
            len(utxos),
            tx_out_count=1,
            witness_count=witness_count,
        )
        min_utxo_out = self.calc_min_utxo({policy_id: asset_names})
        min_utxo_ret = self.calc_min_utxo(output_assets)

        # If we don't have enough ADA, we will have to add another UTxO to cover
        # the transaction fees.
        if input_lovelace < min_fee + min_utxo_ret:

            # Get a list of Lovelace only UTxOs and sort them in decending order
            #  by value.
            ada_utxos = self.shelley.get_utxos(payment_addr, filter="Lovelace")
            ada_utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

            # Iterate through the UTxOs until we have enough funds to cover the
            # transaction. Also, update the tx_in string for the transaction.
            utxo_count = len(utxos)
            for idx, utxo in enumerate(ada_utxos):
                utxo_count += idx + 1
                input_lovelace += int(utxo["Lovelace"])
                input_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

                # Build a transaction draft
                self.shelley.run_cli(
                    f"{self.shelley.cli} transaction build-raw {input_str}"
                    f'--tx-out "{payment_addr}+{input_lovelace}{token_utxo_str}" '
                    f'--ttl 0 --fee 0 --mint "{burn_str}" {meta_str} '
                    f"{self.shelley.era} --out-file {tx_draft_file}"
                )

                # Calculate the minimum fee
                min_fee = self.shelley.calc_min_fee(
                    tx_draft_file,
                    len(utxos),
                    tx_out_count=1,
                    witness_count=witness_count,
                )

                # If we have enough Lovelaces to cover the transaction, we can stop
                # iterating through the UTxOs.
                if input_lovelace > (min_fee + min_utxo_ret):
                    break

        # Handle the error case where there is not enough inputs for the output
        if input_lovelace < min_fee + min_utxo_ret:
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{payment_addr} needs an additional ADA only UTxO."
            )

        # Build the transaction to the blockchain.
        utxo_amt = input_lovelace - min_fee
        tx_raw_file = Path(self.shelley.working_dir) / (tx_name + ".raw")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {input_str}"
            f'--tx-out "{payment_addr}+{utxo_amt}{token_utxo_str}" '
            f'--ttl {ttl} --fee {min_fee} --mint "{burn_str}" {meta_str} '
            f"{self.shelley.era} --out-file {tx_raw_file}"
        )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file
