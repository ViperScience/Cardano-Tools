from datetime import datetime
from pathlib import Path
from sys import breakpointhook

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

    def calc_min_utxo(self, assets) -> int:
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

        # Round the number of bytes to the minimum number of 8 byte words needed
        # to hold all the bytes.
        def round_up_bytes_to_words(b):
            return (b + 7) // 8

        # These are constants but may change in the future
        coin_Size = 2
        utxo_entry_size_without_val = 27
        ada_only_utxo_size = utxo_entry_size_without_val + coin_Size
        pid_size = 28

        # Get the minimum UTxO parameter
        utxo_cost_word = self.shelley.protocol_parameters["utxoCostPerWord"]
        min_utxo = ada_only_utxo_size*utxo_cost_word
        if len(assets) == 0:
            return min_utxo

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
        num_pids = len(unique_pids)
        num_assets = max([len(unique_names), 1])

        # The sum of the length of the ByteStrings representing distinct asset names
        sum_asset_name_lengths = sum(
            [len(s.encode("utf-8")) for s in unique_names]
        )
        [s.encode("utf-8") for s in unique_names]

        # The size of the token bundle in 8-byte long words
        size_bytes = 6 + round_up_bytes_to_words(
            (num_assets * 12) + sum_asset_name_lengths + (num_pids * pid_size)
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

        # This is a constant modifier to determine the minimum ADA for breaking
        # off additional ADA into a separate UTxO. It essentially prevents
        # oscillations at potential bifurcation points where adding or taking
        # away a transaction output puts the extra ADA under or over the
        # minimum UTxO due to transaction fees. This parameter may need to be
        # tuned bust should be fairly small.
        minMult = 1.1

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

        # Calculate the minimum ADA for the token UTxOs.
        min_utxo_out = self.calc_min_utxo(output_tokens.keys())
        min_utxo_ret = self.calc_min_utxo(return_tokens.keys())

        # Lovelace to send with the Token
        utxo_out = max([min_utxo_out, int(ada * 1_000_000)])

        # Lovelaces to return to the wallet
        utxo_ret = min_utxo_ret
        if len(return_tokens) == 0:
            utxo_ret = 0

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Ensure the parameters file exists
        min_utxo = self.shelley.get_min_utxo()

        # Create a metadata string
        meta_str = ""  # Maybe add later

        # Get a list of Lovelace only UTxOs and sort them in ascending order
        # by value. We may not end up needing these.
        ada_utxos = self.shelley.get_utxos(from_addr, filter="Lovelace")
        ada_utxos.sort(key=lambda k: k["Lovelace"], reverse=False)

        # Create a name for the transaction files.
        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")

        # Create a TX out string given the possible scenarios.
        use_ada_utxo = False
        if len(return_tokens) == 0:
            if (input_lovelace - utxo_out) < minMult * min_utxo:
                output_str = f'--tx-out "{to_addr}+0{output_token_utxo_str}" '
            else:
                output_str = (
                    f'--tx-out "{to_addr}+0{output_token_utxo_str}" '
                    f'--tx-out "{from_addr}+0" '
                )
                use_ada_utxo = True
        else:
            if (input_lovelace - utxo_out - utxo_ret) < minMult * min_utxo:
                output_str = (
                    f'--tx-out "{to_addr}+0{output_token_utxo_str}" '
                    f'--tx-out "{from_addr}+0{return_token_utxo_str}" '
                )
            else:
                output_str = (
                    f'--tx-out "{to_addr}+0{output_token_utxo_str}" '
                    f'--tx-out "{from_addr}+0{return_token_utxo_str}" '
                    f'--tx-out "{from_addr}+0" '
                )
                use_ada_utxo = True

        # Calculate the minimum transaction fee as it is right now with only the
        # minimum UTxOs needed for the tokens.
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {input_str}"
            f"{output_str} --ttl 0 --fee 0 {meta_str} "
            f"{self.shelley.era} --out-file {tx_draft_file}"
        )
        min_fee = self.shelley.calc_min_fee(
            tx_draft_file,
            input_str.count("--tx-in "),
            tx_out_count=output_str.count("--tx-out "),
            witness_count=1,
        )

        # If we don't have enough ADA, we will have to add another UTxO to cover
        # the transaction fees.
        if input_lovelace < (min_fee + utxo_ret + utxo_out):

            # Iterate through the UTxOs until we have enough funds to cover the
            # transaction. Also, update the tx_in string for the transaction.
            for idx, utxo in enumerate(ada_utxos):
                input_lovelace += int(utxo["Lovelace"])
                input_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

                self.shelley.run_cli(
                    f"{self.shelley.cli} transaction build-raw {input_str}"
                    f"{output_str} --ttl 0 --fee 0 {meta_str} "
                    f"{self.shelley.era} --out-file {tx_draft_file}"
                )
                min_fee = self.shelley.calc_min_fee(
                    tx_draft_file,
                    input_str.count("--tx-in "),
                    tx_out_count=output_str.count("--tx-out "),
                    witness_count=1,
                )

                # If we don't have enough ADA here, then go ahead and add another
                # ADA only UTxO.
                if input_lovelace < (min_fee + utxo_ret + utxo_out):
                    continue

                # If we do have enough to cover the needed output and fees, check
                # if we need to add a second UTxO with the extra ADA.
                if (
                    input_lovelace - (min_fee + utxo_ret + utxo_out)
                    > minMult * min_utxo
                    and output_str.count("--tx-out ") < 3
                ):

                    self.shelley.run_cli(
                        f"{self.shelley.cli} transaction build-raw {input_str}"
                        f"{output_str} --tx-out {from_addr}+0 "
                        f"--ttl 0 --fee 0 {meta_str} "
                        f"{self.shelley.era} --out-file {tx_draft_file}"
                    )
                    min_fee = self.shelley.calc_min_fee(
                        tx_draft_file,
                        input_str.count("--tx-in "),
                        tx_out_count=output_str.count("--tx-out "),
                        witness_count=1,
                    )

                    # Flag that we are using an extra ADA only UTxO.
                    use_ada_utxo = True

                # We should be good here
                break  # <-- Important!

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
        if use_ada_utxo:
            if len(return_tokens) == 0:
                utxo_ret_ada = input_lovelace - utxo_out - min_fee
            else:
                utxo_ret_ada = input_lovelace - utxo_ret - utxo_out - min_fee
        else:
            if len(return_tokens) == 0:
                min_fee += input_lovelace - utxo_out - min_fee
            else:
                utxo_ret += input_lovelace - utxo_ret - utxo_out - min_fee

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
        policy_id,
        asset_names,
        quantities,
        payment_addr,
        witness_count,
        minting_script,
        tx_metadata=None,
        ada=0.0,
        folder=None,
        cleanup=True,
    ) -> str:
        """Build the transaction for minting a new native asset.

        Requires a running and synced node.

        Parameters
        ----------
        policy_id : str
            The minting policy ID (generated from the signature script).
        asset_names : list
            A list of asset names.
        quantities : list
            A list of asset quantities.
        payment_addr : str
            The address paying the minting fees. Will also own the tokens.
        witness_count : int
            The number of signing keys.
        minting_script:

        tx_metadata : str or Path, optional
            Path to the metadata stored in a JSON file.
        ada : float, optional
            Optionally set the amount of ADA to be included with the tokens.
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

        # This is a constant modifier to determine the minimum ADA for breaking
        # off additional ADA into a separate UTxO. It essentially prevents
        # oscillations at potential bifurcation points where adding or taking
        # away a transaction output puts the extra ADA under or over the
        # minimum UTxO due to transaction fees. This parameter may need to be
        # tuned bust should be fairly small.
        minMult = 2.1

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

        # Make sure all names are unique and the quantities match the names.
        # Giving a name is optional. So, if no names, one quantitiy value is
        # required.
        asset_names = list(set(asset_names))
        if len(asset_names) == 0:
            if len(quantities) != 1:
                raise MaryError("Invalid list of quantities.")
        else:
            if len(quantities) != len(asset_names):
                raise MaryError("Invalid combination of names and quantities.")
        for q in quantities:
            if q < 1:
                raise MaryError("Invalid quantity for minting!")

        # Get a list of ADA only UTXOs and sort them in ascending order by
        # value.
        utxos = self.shelley.get_utxos(payment_addr, filter="Lovelace")
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)
        if len(utxos) < 1:
            raise MaryError("No ADA only UTxOs for minting.")

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Calculate the minimum UTxO
        min_utxo = self.shelley.get_min_utxo()
        mint_assets = [f"{policy_id}.{name}" for name in asset_names]
        if len(mint_assets) == 0:
            mint_assets = [policy_id]
        min_love = self.calc_min_utxo(mint_assets)

        # Lovelace to send with the Token
        utxo_out = max([min_love, int(ada * 1_000_000)])

        # Create minting string
        mint_str = ""
        if len(asset_names) == 0:
            mint_str += f"{quantities[0]} {policy_id}"
        else:
            for i, name in enumerate(asset_names):
                sep = " + " if i != 0 else ""
                mint_str += f"{sep}{quantities[i]} {policy_id}.{name}"

        # Create a metadata string
        meta_str = ""
        if tx_metadata is not None:
            meta_str = f"--metadata-json-file {tx_metadata}"

        # Create a minting script string
        script_str = f"--minting-script-file {minting_script}"

        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")

        # Iterate through the ADA only UTxOs until we have enough funds to
        # cover the transaction. Also, create the tx_in string for the
        # transaction.
        utxo_ret_ada = 0
        utxo_total = 0
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            # Add an availible UTxO to the list and then check to see if we now
            # have enough lovelaces to cover the transaction fees and what we
            # want with the tokens.
            utxo_count = idx + 1
            utxo_total += int(utxo["Lovelace"])
            tx_in_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

            # Build a transaction draft with a single output.
            self.shelley.run_cli(
                f"{self.shelley.cli} transaction build-raw {tx_in_str}"
                f'--tx-out "{payment_addr}+{utxo_total}+{mint_str}" '
                f"--ttl 0 --fee 0 "
                f'--mint "{mint_str}" {script_str} {meta_str} '
                f"{self.shelley.era} --out-file {tx_draft_file}"
            )

            # Calculate the minimum fee for the transaction with a single
            # minting output.
            min_fee = self.shelley.calc_min_fee(
                tx_draft_file,
                utxo_count,
                tx_out_count=1,
                witness_count=witness_count,
            )

            # If we don't have enough ADA here, then go ahead and add another
            # ADA only UTxO.
            if utxo_total < (min_fee + utxo_out):
                continue

            # If we do have enough to cover the needed output and fees, check
            # if we need to add a second UTxO with the extra ADA.
            if utxo_total - (min_fee + utxo_out) > minMult * min_utxo:

                # Create a draft transaction with an extra ADA only UTxO.
                self.shelley.run_cli(
                    f"{self.shelley.cli} transaction build-raw {tx_in_str}"
                    f'--tx-out "{payment_addr}+{utxo_total}+{mint_str}" '
                    f'--tx-out "{payment_addr}+0" --ttl 0 --fee 0 '
                    f'--mint "{mint_str}" {script_str} {meta_str} '
                    f"{self.shelley.era} --out-file {tx_draft_file}"
                )

                # Calculate the minimum fee for the transaction with an extra
                # ADA only UTxO.
                min_fee = self.shelley.calc_min_fee(
                    tx_draft_file,
                    utxo_count,
                    tx_out_count=2,
                    witness_count=witness_count,
                )

                # Save the amount of ADA that we are returning in a separate
                # UTxO.
                utxo_ret_ada = utxo_total - (min_fee + utxo_out)

            else:
                # If we are staying with the single UTxO result. Make sure any
                # overages are just added to the output so the transaction
                # balances.
                utxo_out += utxo_total - (min_fee + utxo_out)

            # We should be good to go here.
            break

        # Handle the error case where there is not enough inputs for the output
        if utxo_total < (min_fee + utxo_out):
            cost_ada = (min_fee + utxo_out) / 1_000_000
            utxo_total_ada = utxo_total / 1_000_000
            raise MaryError(
                f"Transaction failed due to insufficient funds. Account "
                f"{payment_addr} cannot pay tranction costs of {cost_ada} "
                f"ADA because it only contains {utxo_total_ada} ADA."
            )

        # Build the transaction to send to the blockchain.
        token_return_ada_str = ""
        if utxo_ret_ada > 0:
            token_return_ada_str = f"--tx-out {payment_addr}+{utxo_ret_ada}"
        tx_raw_file = Path(self.shelley.working_dir) / (tx_name + ".raw")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {tx_in_str}"
            f'--tx-out "{payment_addr}+{utxo_out}+{mint_str}" '
            f"{token_return_ada_str} --ttl {ttl} --fee {min_fee} "
            f'--mint "{mint_str}" {script_str} {meta_str} '
            f"{self.shelley.era} --out-file {tx_raw_file}"
        )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file

    def build_burn_transaction(
        self,
        policy_id,
        asset_names,
        quantities,
        payment_addr,
        witness_count,
        minting_script,
        tx_metadata=None,
        folder=None,
        cleanup=True,
    ) -> str:
        """Build the transaction for burning a native asset.

        Requires a running and synced node.

        Parameters
        ----------
        policy_id : str
            The minting policy ID generated from the signature script--the
            same for all assets.
        asset_names : list
            List of asset names (same size as quantity list).
        quantities : list
            List of the numbers of each asset to burn.
        payment_addr : str
            The address paying the minting fees. Will also contain the tokens.
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

        # Make sure all names are unique and the quantities match the names.
        # Giving a name is optional. So, if no names, one quantitiy value is
        # required.
        asset_names = list(set(asset_names))
        if len(asset_names) == 0:
            if len(quantities) != 1:
                raise MaryError("Invalid list of quantities.")
        else:
            if len(quantities) != len(asset_names):
                raise MaryError("Invalid combination of names and quantities.")

        # Users may send the quantities in as negative values since we are
        # burining. However, the quantities must be positive for the
        # calculations prior to the transaction. The negative sign will be
        # added to the mint inputs appropriately.
        quantities = [abs(q) for q in quantities]

        # Get the required UTxO(s) for the requested token.
        (
            input_str,
            input_lovelace,
            output_tokens,
            return_tokens,
        ) = self._get_token_utxos(
            payment_addr, policy_id, asset_names, quantities
        )

        # Determine the TTL
        tip = self.shelley.get_tip()
        ttl = tip + self.shelley.ttl_buffer

        # Get the minimum ADA only UTxO size.
        min_utxo = self.shelley.get_min_utxo()

        # Create transaction strings for the tokens. The minting input string
        # and the UTxO string for any remaining tokens.
        burn_str = ""
        token_utxo_str = ""
        for i, asset in enumerate(output_tokens.keys()):
            sep = " + " if i != 0 else ""
            burn_str += f"{sep}{-1*output_tokens[asset]} {asset}"
        for asset in return_tokens.keys():
            token_utxo_str += f" + {return_tokens[asset]} {asset}"

        # Create a metadata string
        meta_str = ""
        if tx_metadata is not None:
            meta_str = f"--metadata-json-file {tx_metadata}"
        
        # Create a minting script string
        script_str = f"--minting-script-file {minting_script}"

        # Calculate the minimum fee and UTxO sizes for the transaction as it is
        # right now with only the minimum UTxOs needed for the tokens.
        tx_name = datetime.now().strftime("tx_%Y-%m-%d_%Hh%Mm%Ss")
        tx_draft_file = Path(self.shelley.working_dir) / (tx_name + ".draft")
        self.shelley.run_cli(
            f"{self.shelley.cli} transaction build-raw {input_str}"
            f'--tx-out "{payment_addr}+{input_lovelace}{token_utxo_str}" '
            f'--ttl 0 --fee 0 --mint "{burn_str}" {script_str} {meta_str} '
            f"{self.shelley.era} --out-file {tx_draft_file}"
        )
        min_fee = self.shelley.calc_min_fee(
            tx_draft_file,
            utxo_count := input_str.count("--tx-in "),
            tx_out_count=1,
            witness_count=witness_count,
        )
        min_utxo_ret = self.calc_min_utxo(return_tokens.keys())

        # If we don't have enough ADA, we will have to add another UTxO to cover
        # the transaction fees.
        if input_lovelace < min_fee + min_utxo_ret:

            # Get a list of Lovelace only UTxOs and sort them in ascending order
            # by value.
            ada_utxos = self.shelley.get_utxos(payment_addr, filter="Lovelace")
            ada_utxos.sort(key=lambda k: k["Lovelace"], reverse=False)

            # Iterate through the UTxOs until we have enough funds to cover the
            # transaction. Also, update the tx_in string for the transaction.
            for utxo in ada_utxos:
                utxo_count += 1
                input_lovelace += int(utxo["Lovelace"])
                input_str += f"--tx-in {utxo['TxHash']}#{utxo['TxIx']} "

                # Build a transaction draft
                self.shelley.run_cli(
                    f"{self.shelley.cli} transaction build-raw {input_str}"
                    f'--tx-out "{payment_addr}+{input_lovelace}{token_utxo_str}" '
                    f'--ttl 0 --fee 0 --mint "{burn_str}" {script_str} {meta_str} '
                    f"{self.shelley.era} --out-file {tx_draft_file}"
                )

                # Calculate the minimum fee
                min_fee = self.shelley.calc_min_fee(
                    tx_draft_file,
                    utxo_count,
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
            f'--ttl {ttl} --fee {min_fee} --mint "{burn_str}" {script_str} {meta_str} '
            f"{self.shelley.era} --out-file {tx_raw_file}"
        )

        # Delete the intermediate transaction files if specified.
        if cleanup:
            self.shelley._cleanup_file(tx_draft_file)

        # Return the path to the raw transaction file.
        return tx_raw_file
