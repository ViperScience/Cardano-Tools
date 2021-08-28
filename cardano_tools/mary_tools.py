from datetime import datetime
from pathlib import Path

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

    def _get_token_utxos(self, addr, policy_id, asset_names, quantities):
        """Get a list of UTxOs that contain the desired assets."""

        # Make a list of all asset names (unique!)
        send_assets = {}
        for name, amt in zip(asset_names, quantities):
            asset = f"{policy_id}.{name}" if name else policy_id
            if asset in send_assets:
                send_assets[asset] += amt
            else:
                send_assets[asset] = amt

        # Get a list of UTxOs for the transaction
        utxos = []
        input_str = ""
        input_lovelace = 0
        for i, asset in enumerate(send_assets.keys()):

            # Find all the UTxOs containing the assets desired. This may take a
            # while if there are a lot of tokens!
            utxos_found = self.shelley.get_utxos(addr, filter=asset)

            # Iterate through the UTxOs and only take enough needed to process
            # the requested amount of tokens. Also, only create a list of unique
            # UTxOs.
            asset_count = 0
            for utxo in utxos_found:

                # UTxOs could show up twice if they contain multiple different
                # assets. Only put them in the list once.
                if utxo not in utxos:
                    utxos.append(utxo)

                    # If this is a unique UTxO being added to the list, keep
                    # track of the total Lovelaces and add it to the
                    # transaction input string.
                    input_lovelace += int(utxo["Lovelace"])
                    input_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

                asset_count += int(utxo[asset])
                if asset_count >= quantities[i]:
                    break

            if asset_count < quantities[i]:
                raise MaryError(f"Not enought {asset} tokens availible.")

        # If we get to this point, we have enough UTxOs to cover the requested
        # tokens. Next we need to build lists of the output and return tokens.
        output_tokens = {}
        return_tokens = {}
        for utxo in utxos:
            # Iterate through the UTxO entries.
            for k in utxo.keys():
                if k in ["TxHash", "TxIx", "Lovelace"]:
                    pass  # These are the UTxO IDs in every UTxO.
                elif k in send_assets:
                    # These are the native assets requested.
                    if k in output_tokens:
                        output_tokens[k] += int(utxo[k])
                    else:
                        output_tokens[k] = int(utxo[k])

                    # If the UTxOs selected for the transaction contain more
                    # tokens than requested, clip the number of output tokens
                    # and put the remainder as returning tokens.
                    if output_tokens[k] > send_assets[k]:
                        return_tokens[k] = output_tokens[k] - send_assets[k]
                        output_tokens[k] = send_assets[k]
                else:
                    # These are tokens that are not being requested so they just
                    # need to go back to the wallet in another output.
                    if k in return_tokens:
                        return_tokens[k] += int(utxo[k])
                    else:
                        return_tokens[k] = int(utxo[k])

        # Note: at this point output_tokens should be the same as send_assets.
        # It was necessary to build another dict of output tokens as we
        # iterated through the list of UTxOs for proper accounting.

        # Return the computed results as a tuple to be used for building a token
        # transaction.
        return (input_str, input_lovelace, output_tokens, return_tokens)

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

        Parameters
        ----------
        assets : list
            A list of assets in the format policyid.name.

        Returns
        -------
        int
            The minimum transaction output (Lovelace).
        """

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()

        # Get the minimum UTxO parameter
        min_utxo = self.shelley.protocol_parameters["minUTxOValue"]
        if len(assets) == 0:
            return min_utxo

        # Round the number of bytes to the minimum number of 8 byte words needed
        # to hold all the bytes.
        def round_up_bytes_to_words(b):
            return (b + 7) // 8

        # These are constants but may change in the future
        coin_Size = 0
        utxo_entry_size_without_val = 27
        ada_only_utxo_size = utxo_entry_size_without_val + coin_Size
        pid_size = 28

        # Get lists of unique policy IDs and asset names.
        unique_pids = list(set([asset.split(".")[0] for asset in assets]))
        unique_names = list(
            set(
                [
                    asset.split(".")[1]
                    for asset in assets
                    if len(asset.split(".")) > 1
                ]
            )
        )

        # Get the number of unique policy IDs and token names in the bundle
        num_assets = len(unique_pids)
        num_pids = len(unique_names)

        # The sum of the length of the ByteStrings representing distinct asset names
        sum_asset_name_lengths = sum(
            [len(s.encode("utf-8")) for s in unique_names]
        )

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

    def build_send_tx(
        self,
        to_addr,
        from_addr,
        quantity,
        policy_id,
        asset_name=None,
        ada=0.0,
        folder=None,
        cleanup=True,
    ):
        """Build a transaction for sending an integer number of native assets
        from one address to another.

        Opinionated: Only send 1 type of Native Token at a time. Will only
        combine additional ADA-only UTxOs when paying for the transactions fees
        and minimum UTxO ADA values if needed.

        Parameters
        ----------
        to_addr : str
            Address to send the asset to.
        from_addr : str
            Address to send the asset from.
        quantity : float
            Integer number of assets to send.
        policy_id : str
            Policy ID of the asset to be sent.
        asset_name : str, optional
            Asset name if applicable.
        ada : float, optional
            Optionally set the amount of ADA to be sent with the token.
        folder : str or Path, optional
            The working directory for the function. Will use the Shelley
            object's working directory if node is given.
        cleanup : bool, optional
            Flag that indicates if the temporary transaction files should be
            removed when finished (defaults to True).
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

        # Make sure the qunatity is positive.
        quantity = abs(quantity)

        # Get the required UTxO(s) for the requested token.
        (
            input_str,
            input_lovelace,
            output_tokens,
            return_tokens,
        ) = self._get_token_utxos(
            from_addr, policy_id, [asset_name], [quantity]
        )

        # Build token input and output strings
        output_token_utxo_str = ""
        for token in output_tokens.keys():
            output_token_utxo_str += f" + {output_tokens[token]} {token}"
        return_token_utxo_str = ""
        for token in return_tokens.keys():
            return_token_utxo_str += f" + {return_tokens[token]} {token}"

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Ensure the parameters file exists
        self.shelley.load_protocol_parameters()
        min_utxo = self.shelley.protocol_parameters["minUTxOValue"]

        # Create a metadata string
        meta_str = ""  # Maybe add later

        # Calculate the minimum fee and UTxO sizes for the transaction as it is
        # right now with only the minimum UTxOs needed for the tokens.
        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {input_str}"
            f'--tx-out "{to_addr}+0{output_token_utxo_str}" '
            f'--tx-out "{from_addr}+0{return_token_utxo_str}" '
            f"--ttl 0 --fee 0 {meta_str} "
            f"{self.shelley.era} --out-file {tx_draft_file}"
        )
        min_fee = self.shelley.calc_min_fee(
            tx_draft_file,
            input_str.count("--tx-in "),
            tx_out_count=1,
            witness_count=1,
        )
        min_utxo_out = self.calc_min_utxo(output_tokens.keys())
        min_utxo_ret = self.calc_min_utxo(return_tokens.keys())

        # Lovelace to send with the Token
        utxo_out = max([min_utxo_out, int(ada * 1_000_000)])

        # Lovelaces to return to the wallet
        utxo_ret = min_utxo_ret
        if len(return_tokens) == 0:
            utxo_ret = 0

        # If we don't have enough ADA, we will have to add another UTxO to cover
        # the transaction fees.
        if input_lovelace < (min_fee + utxo_ret + utxo_out):

            # Get a list of Lovelace only UTxOs and sort them in ascending order
            # by value.
            ada_utxos = self.shelley.get_utxos(from_addr, filter="Lovelace")
            ada_utxos.sort(key=lambda k: k["Lovelace"], reverse=False)

            # Iterate through the UTxOs until we have enough funds to cover the
            # transaction. Also, update the tx_in string for the transaction.
            for idx, utxo in enumerate(ada_utxos):
                input_lovelace += int(utxo["Lovelace"])
                input_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

                # Build a transaction draft
                self.shelley.run_cli(
                    f"{self.shelley.cli} transaction build-raw {input_str}"
                    f'--tx-out "{to_addr}+0{output_token_utxo_str}" '
                    f'--tx-out "{from_addr}+0{return_token_utxo_str}" '
                    f"--ttl 0 --fee 0 {meta_str} "
                    f"{self.shelley.era} --out-file {tx_draft_file}"
                )

                # Calculate the minimum fee
                min_fee = self.shelley.calc_min_fee(
                    tx_draft_file,
                    input_str.count("--tx-in "),
                    tx_out_count=1,
                    witness_count=1,
                )

                # If we have enough Lovelaces to cover the transaction, we can
                # stop iterating through the UTxOs.
                if input_lovelace > (min_fee + utxo_ret + utxo_out):
                    break

        # Handle the error case where there is not enough inputs for the output
        if input_lovelace < (min_fee + utxo_ret + utxo_out):
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{from_addr} needs an additional ADA only UTxO."
            )

        # Figure out the amount of ADA to put with the different UTxOs.
        # If we have tokens being returned to the wallet, only keep the minimum
        # ADA in that UTxO and make an extra ADA only UTxO.
        utxo_ret_ada = 0
        if input_lovelace > min_fee + utxo_ret + utxo_out:
            if len(return_tokens) == 0:
                utxo_ret_ada = input_lovelace - utxo_out - min_fee
                if utxo_ret_ada < min_utxo:
                    min_fee += utxo_ret_ada
                    utxo_ret_ada = 0
            else:
                utxo_ret_ada = input_lovelace - utxo_ret - utxo_out - min_fee
                if utxo_ret_ada < min_utxo:
                    utxo_ret += utxo_ret_ada
                    utxo_ret_ada = 0

        # Build the transaction to send to the blockchain.
        token_return_utxo_str = ""
        if utxo_ret > 0:
            token_return_utxo_str = (
                f'--tx-out "{from_addr}+{utxo_ret}{return_token_utxo_str}"'
            )
        token_return_ada_str = ""
        if utxo_ret_ada > 0:
            token_return_ada_str = f"--tx-out {from_addr}+{utxo_ret_ada}"
        tx_raw_file = Path(self.shelley.working_dir) / (tx_name + ".raw")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {input_str}"
            f'--tx-out "{to_addr}+{utxo_out}{output_token_utxo_str}" '
            f"{token_return_utxo_str} {token_return_ada_str} "
            f"--ttl {ttl} --fee {min_fee} {self.shelley.era} "
            f"--out-file {tx_raw_file}"
        )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file

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
        if utxo_amt < min_utxo:
            min_fee = utxo_amt
            utxo_amt = 0
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
