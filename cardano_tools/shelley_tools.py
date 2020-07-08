from datetime import datetime
from pathlib import Path
import subprocess
import json
import os
import re


class ShelleyError(Exception):
    pass

class ShelleyTools():

    def __init__(self, path_to_cli, path_to_socket, working_dir, 
        ttl_buffer=1000, ssh=None, network="--mainnnet"):

        # Set the path to the CLI and verify it works. An exception will be 
        # thrown if the command is not found.
        self.cli = path_to_cli
        subprocess.run([self.cli, "--version"], capture_output=True)

        # Set the socket path and export it as an environment variable.
        self.socket = path_to_socket
        os.environ["CARDANO_NODE_SOCKET_PATH"] = self.socket

        # Set the working directory. Create the path if it doesn't exist.
        self.working_dir = Path(working_dir)
        self.working_dir.mkdir(parents=True, exist_ok=True)
        
        self.ttl_buffer = ttl_buffer
        self.ssh = ssh
        self.network = network
        self.protocol_parameters = None

    def __run(self, cmd):
        if self.ssh:
            
            # Open the connection
            self.ssh.open()

            # Run the commands remotely
            result = self.conn.run(cmd, warn=True, hide=True)

            # Close the connection
            self.ssh.close()

        else:

            # Execute the commands locally
            result = subprocess.run(cmd.split(), capture_output=True)
        
        return result

    def load_protocol_parameters(self):
        """Load the protocol parameters which are needed for creating 
        transactions.
        """
        params_file = self.working_dir / "protocol.json"
        cmd = (
            f"{self.cli} shelley query protocol-parameters {self.network} "
            f"--out-file {params_file}"
        )
        subprocess.run(cmd.split())
        with open(params_file, 'r') as json_file:
            self.protocol_parameters = json.load(json_file)
        return params_file

    def get_tip(self):
        """Query the node for the current tip of the blockchain.
        """
        cmd = f"{self.cli} shelley query tip {self.network}"
        #result = subprocess.run(cmd.split(), capture_output=True)
        #output = result.stdout.decode().strip()
        result = self.__run(cmd)
        output = result.stdout.decode().strip()
        if "unSlotNo" not in output:
            raise ShelleyError(result.stderr.decode().strip())
        vals = [int(x) for x in re.findall(r'\d+', result.stdout.decode())]
        return vals[0]
    
    def make_address(self, name, folder=None):
        """Create an address and the corresponding payment and staking keys.
        """
        if folder is None:
            folder = self.working_dir

        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        payment_vkey = folder / (name + ".vkey")
        payment_skey = folder / (name + ".skey")
        stake_vkey = folder / (name + "_stake.vkey")
        stake_skey = folder / (name + "_stake.skey")
        payment_addr = folder / (name + ".addr")
        stake_addr = folder / (name + "_stake.addr")

        # Generate payment key pair.
        cmd = (
            f"{self.cli} shelley address key-gen "
            f"--verification-key-file {payment_vkey} "
            f"--signing-key-file {payment_skey}"
        )
        subprocess.run(cmd.split())

        # Generate stake key pair.
        cmd = (
            f"{self.cli} shelley stake-address key-gen "
            f"--verification-key-file {stake_vkey} "
            f"--signing-key-file {stake_skey}"
        )
        subprocess.run(cmd.split())

        # Create the payment address.
        cmd = (
            f"{self.cli} shelley address build "
            f"--payment-verification-key-file {payment_vkey} "
            f"--stake-verification-key-file {stake_vkey} "
            f"--out-file {payment_addr} {self.network}"
        )
        subprocess.run(cmd.split())

        # Create the staking address.
        cmd = (
            f"{self.cli} shelley stake-address build "
            f"--stake-verification-key-file {stake_vkey} "
            f"--out-file {stake_addr} {self.network}"
        )
        subprocess.run(cmd.split())
        
        # Read the file and return the payment address.
        with open(payment_addr, 'r') as payment_addr_file:
            addr = payment_addr_file.read().strip()
        return addr

    def get_utxos(self, addr):
        """Query the list of UTXOs for a given address and parse the output. 
        The returned data is formatted as a list of dict objects.
        """
        cmd = f"{self.cli} shelley query utxo --address {addr} {self.network}"
        result = self.__run(cmd)
        raw_utxos = result.stdout.decode().split('\n')[2:-1]
        utxos = []
        for utxo_line in raw_utxos:
            vals = utxo_line.split()
            utxos.append({
                "TxHash" : vals[0],
                "TxIx" : vals[1],
                "Lovelace" : vals[2]
            })
        return utxos

    def send_payment(self, amt, to_addr, from_addr, key_file, cleanup=True):
        """Send a simple payment of ADA.
        """
        payment = amt*1_000_000  # ADA to Lovelaces

        # Build a transaction name
        tx_name = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.get_utxos(from_addr)
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Determine which UTXO(s) to spend.
        tx_in = ""
        total_in = 0
        tx_in_count = 0
        for u in utxos:
            tx_in += f" --tx-in {u['TxHash']}#{u['TxIx']}"
            total_in += int(u['Lovelace'])
            tx_in_count += 1
            if total_in > payment:
                break
        if total_in < payment:
            raise ShelleyError(
                f"Transaction failed due to insufficient funds. "
                f"Account {from_addr} cannot send {amt} ADA to account "
                f"{to_addr} because it only contains {total_in/1_000_000} ADA."
            )
            # Maybe this should fail more gracefully, but higher level logic can 
            # also just catch the error and handle it.

        # Determine the slot where the transaction will become invalid. Get the
        # current slot number and add a buffer to it.
        tip = self.get_tip()
        ttl = tip + self.ttl_buffer

        # Calculate the minimum fee
        params_file = self.load_protocol_parameters()
        cmd = (
            f"{self.cli} shelley transaction calculate-min-fee "
            f"--tx-in-count {tx_in_count} --tx-out-count 2 --ttl {ttl} "
            f"{self.network} --signing-key-file {key_file} "
            f"--protocol-params-file {params_file}"
        )
        result = subprocess.run(cmd.split(), capture_output=True)
        min_fee = int(result.stdout.decode().split()[1])

        # Build the transaction
        tx_raw_file = Path(self.working_dir) / (tx_name + ".raw")
        cmd = (
            f"{self.cli} shelley transaction build-raw{tx_in} "
            f"--tx-out {to_addr}+{payment} "
            f"--tx-out {from_addr}+{total_in - payment-min_fee} "
            f"--ttl {ttl} --fee {min_fee} --out-file {tx_raw_file}"
        )
        subprocess.run(cmd.split())

        # Sign the transaction with the signing key
        tx_signed_file = Path(self.working_dir) / (tx_name + ".signed")
        cmd = (
            f"{self.cli} shelley transaction sign "
            f"--tx-body-file {tx_raw_file} --signing-key-file {key_file} "
            f"{self.network} --out-file {tx_signed_file}"
        )
        subprocess.run(cmd.split())

        # Submit the transaction
        cmd = (
            f"{self.cli} shelley transaction submit "
            f"--tx-file {tx_signed_file} {self.network}"
        )
        subprocess.run(cmd.split())

        # Delete the transaction files if specified.
        if cleanup:
            os.remove(tx_raw_file)
            os.remove(tx_signed_file)

    def register_stake_address(self, addr, stake_vkey_file, stake_skey_file, 
        pmt_skey_file, cleanup=True):
        """Register a stake address in the blockchain.
        """

        # Build a transaction name
        tx_name = datetime.now().strftime("reg_stake_key_%Y-%m-%d_%Hh%Mm%Ss")

        # Create a registration certificate
        key_file_path = Path(stake_vkey_file)
        stake_cert_path = key_file_path.parent / (key_file_path.stem + ".cert")
        cmd = (
            f"{self.cli} shelley stake-address registration-certificate "
            f"--stake-verification-key-file {stake_vkey_file} "
            f"--out-file {stake_cert_path}"
        )
        subprocess.run(cmd.split())

        # Determine the TTL
        tip = self.get_tip()
        ttl = tip + self.ttl_buffer

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.get_utxos(addr)
        if len(utxos) < 1:
            raise ShelleyError(
                f"Transaction failed due to insufficient funds. "
                f"Account {addr} cannot pay tranction costs because "
                "it does not contain any ADA."
            )
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)
        
        # Ensure the parameters file exists
        params_file = self.load_protocol_parameters()

        # Iterate through the UTXOs until we have enough funds to cover the 
        # transaction. Also, create the tx_in string for the transaction.
        utxo_total = 0
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            utxo_total += int(utxo['Lovelace'])
            tx_in_str += f" --tx-in {utxo['TxHash']}#{utxo['TxIx']}"

            # Calculate the minimum fee
            cmd = (
                f"{self.cli} shelley transaction calculate-min-fee "
                f"--tx-in-count {idx + 1} --tx-out-count 1 --ttl {ttl} "
                f"{self.network} --signing-key-file {pmt_skey_file} "
                f"--signing-key-file {stake_skey_file} "
                f"--certificate-file {stake_cert_path} "
                f"--protocol-params-file {params_file}"
            )
            result = subprocess.run(cmd.split(), capture_output=True)
            min_fee = int(result.stdout.decode().split()[1])

            # TX cost
            cost = min_fee + self.protocol_parameters["keyDeposit"]
            if utxo_total > cost:
                break

        if utxo_total < cost:
            cost_ada = cost/1_000_000
            utxo_total_ada = utxo_total/1_000_000
            raise ShelleyError(
                f"Transaction failed due to insufficient funds. "
                f"Account {addr} cannot pay tranction costs of {cost} "
                f"lovelaces because it only contains {utxo_total_ada} ADA."
            )

        # Build the transaction.
        tx_raw_file = Path(self.working_dir) / (tx_name + ".raw")
        cmd = (
            f"{self.cli} shelley transaction build-raw{tx_in_str} "
            f"--tx-out {addr}+{utxo_total - cost} "
            f"--ttl {ttl} --fee {min_fee} "
            f"--certificate-file {stake_cert_path} "
            f"--out-file {tx_raw_file}"
            
        )
        subprocess.run(cmd.split())
        
        # Sign the transaction with both the payment and stake keys.
        tx_signed_file = Path(self.working_dir) / (tx_name + ".signed")
        cmd = (
            f"{self.cli} shelley transaction sign "
            f"--tx-body-file {tx_raw_file} --signing-key-file {pmt_skey_file} "
            f"--signing-key-file {stake_skey_file} {self.network} "
            f"--out-file {tx_signed_file}"
        )
        subprocess.run(cmd.split())
        
        # Submit the transaction
        cmd = (
            f"{self.cli} shelley transaction submit "
            f"--tx-file {tx_signed_file} {self.network}"
        )
        subprocess.run(cmd.split())

        # Delete the transaction files if specified.
        if cleanup:
            os.remove(tx_raw_file)
            os.remove(tx_signed_file)

    def create_block_producing_keys(self, genesis_file, pool_name="pool", 
        folder=None):
        """Create keys for a block-producing node.
        WARNING: You may want to use your local machine for this process
        (assuming you have cardano-node and cardano-cli on it). Make sure you
        are not online until you have put your cold keys in a secure storage and
        deleted the files from you local machine.

        The block-producing node or pool node needs:
            Cold key pair,
            VRF Key pair,
            KES Key pair,
            Operational Certificate
        """

        if folder is None:
            folder = self.working_dir
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)

        # Generate Cold Keys and a Cold_counter
        cold_vkey = folder / (pool_name + "_cold.vkey")
        cold_skey = folder / (pool_name + "_cold.skey")
        cold_counter = folder / (pool_name + "_cold.counter")
        cmd = (
            f"{self.cli} shelley node key-gen "
            f"--cold-verification-key-file {cold_vkey} "
            f"--cold-signing-key-file {cold_skey} "
            f"--operational-certificate-issue-counter-file {cold_counter}"
        )
        subprocess.run(cmd.split())

        # Generate VRF Key pair
        vrf_vkey = folder / (pool_name + "_vrf.vkey")
        vrf_skey = folder / (pool_name + "_vrf.skey")
        cmd = (
            f"{self.cli} shelley node key-gen-VRF "
            f"--verification-key-file {vrf_vkey} "
            f"--signing-key-file {vrf_skey}"
        )
        subprocess.run(cmd.split())

        # Generate the KES Key pair
        kes_vkey = folder / (pool_name + "_kes.vkey")
        kes_skey = folder / (pool_name + "_kes.skey")
        cmd = (
            f"{self.cli} shelley node key-gen-KES "
            f"--verification-key-file {kes_vkey} "
            f"--signing-key-file {kes_skey}"
        )
        subprocess.run(cmd.split())

        # Get the network protocol parameters
        with open(genesis_file, "r") as genfile:
            genesis_parameters = json.load(genfile)

        # Generate the Operational Certificate/
        cert_file = folder / (pool_name + ".cert")
        slots_kes_period = genesis_parameters["slotsPerKESPeriod"]
        tip = self.get_tip()
        kes_period = tip // slots_kes_period  # Integer division
        cmd = (
            f"{self.cli} shelley node issue-op-cert "
            f"--kes-verification-key-file {kes_vkey} "
            f"--cold-signing-key-file {cold_skey} "
            f"--operational-certificate-issue-counter {cold_counter} "
            f"--kes-period {kes_period} --out-file {cert_file}"
        )
        subprocess.run(cmd.split())

        # Get the pool ID and return it.
        cmd = (
            f"{self.cli} shelley stake-pool id "
            f"--verification-key-file {cold_vkey}"
        )
        result = subprocess.run(cmd.split(), capture_output=True)
        pool_id = result.stdout.decode()
        with open(folder / (pool_name + ".id"), "w") as idfile:
            idfile.write(pool_id)
        return pool_id  # Return the pool id after first saving it to a file.

    def register_stake_pool(self, pool_name, pool_metadata, pool_pledge, 
        pool_cost, pool_margin, pool_cold_vkey, pool_cold_skey, pool_vrf_key, 
        pool_reward_vkey, owner_stake_vkeys, owner_stake_skeys, payment_addr, 
        payment_skey, genesis_file, folder=None, cleanup=True):
        """Register a stake pool on the blockchain.

        Parameters
        ----------
        pool_name : str
            Pool name for file/certificate naming.
        pool_metadata : dict
            Dictionary of stake pool metadata to be converted to json.
        pool_pledge : int
            Pool pledge amount in lovelace.
        pool_cost : int
            Pool cost (fixed fee per epoch) in lovelace.
        pool_margin : float
            Pool margin (variable fee) as a percentage.
        pool_cold_vkey : str, Path
            Path to the pool's cold verification key.
        pool_cold_skey : str, Path
        pool_vrf_key : str, Path
            Path to the pool's verification key.
        pool_reward_vkey : str, Path
            Path to the staking verification key that will receive pool rewards.
        owner_stake_vkeys : list
            List of owner stake keys (paths) responsible for the pledge.
        owner_stake_skeys : list
        payment_addr : 
        payment_skey : 
        folder : str, Path, optional
            The directory where the generated files/certs will be placed.
        cleanup : bool, optional
            A flag used to cleanup the transaction files (default is True)

        Returns
        -------
        list
            a list of strings representing the header columns
        """

        if folder is None:
            folder = self.working_dir
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)

        # Create a JSON file with your pool's metadata and get the file's hash.
        metadata_file_path = folder / f"{pool_name}_metadata.json"
        with open(metadata_file_path, "w") as metadata_file:
            json.dump(pool_metadata, metadata_file)
        cmd = (
            f"{self.cli} shelley stake-pool metadata-hash "
            f"--pool-metadata-file {metadata_file_path}"
        )
        result = subprocess.run(cmd.split(), capture_output=True)
        metadata_hash = result.stdout.decode().strip()
        
        # Generate Stake pool registration certificate
        pool_cert_path = folder / (pool_name + "_registration.cert")
        owner_key_str = ""
        for key_path in owner_stake_vkeys:
            owner_key_str += f"--pool-owner-stake-verification-key-file {key_path} "
        cmd = (
            f"{self.cli} shelley stake-pool registration-certificate "
            f"--cold-verification-key-file {pool_cold_vkey} "
            f"--vrf-verification-key-file {pool_vrf_key} "
            f"--pool-pledge {pool_pledge} "
            f"--pool-cost {pool_cost} "
            f"--pool-margin {pool_margin/100} "
            f"--pool-reward-account-verification-key-file {pool_reward_vkey} "
            f"{owner_key_str} {self.network} --out-file {pool_cert_path}"
        )
        subprocess.run(cmd.split())

        # TODO: Edit the cert free text

        # Generate delegation certificate (pledge from each owner)
        del_cert_args = ""
        signing_key_args = ""
        for key_path in owner_stake_vkeys:
            key_path = Path(key_path)
            cert_path = key_path.parent / (key_path.stem + "_delegation.cert")
            del_cert_args += f"--certificate-file {cert_path} "
            cmd = (
                f"{self.cli} shelley stake-address delegation-certificate "
                f"--stake-verification-key-file {key_path} "
                f"--cold-verification-key-file {pool_cold_vkey} "
                f"--out-file {cert_path}"
            ) 
            subprocess.run(cmd.split())
        for key_path in owner_stake_skeys:
            signing_key_args += f"--signing-key-file {key_path} "

        # Get the pool deposit from the network genesis parameters.
        with open(genesis_file, "r") as genfile:
            genesis_parameters = json.load(genfile)
        pool_deposit = genesis_parameters["protocolParams"]["poolDeposit"]

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.get_utxos(payment_addr)
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Determine the TTL
        tip = self.get_tip()
        ttl = tip + self.ttl_buffer

        # Ensure the parameters file exists
        params_file = self.load_protocol_parameters()
        
        # Iterate through the UTXOs until we have enough funds to cover the 
        # transaction. Also, create the tx_in string for the transaction.
        utxo_total = 0
        min_fee = 1  # make this start greater than utxo_total
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            utxo_total += int(utxo['Lovelace'])
            tx_in_str += f" --tx-in {utxo['TxHash']}#{utxo['TxIx']}"

            # Calculate the minimum fee
            cmd = (
                f"{self.cli} shelley transaction calculate-min-fee "
                f"--tx-in-count {idx + 1} --tx-out-count 1 --ttl {ttl} "
                f"{self.network} --signing-key-file {payment_skey} "
                f"{signing_key_args} --signing-key-file {pool_cold_skey} "
                f"--certificate-file {pool_cert_path} {del_cert_args}"
                f"--protocol-params-file {params_file}"
            )
            result = subprocess.run(cmd.split(), capture_output=True)
            min_fee = int(result.stdout.decode().split()[1])
            if utxo_total > (min_fee + pool_deposit):
                break

        if utxo_total < min_fee:
            cost_ada = (min_fee + pool_deposit)/1_000_000
            utxo_total_ada = utxo_total/1_000_000
            raise ShelleyError(
                f"Transaction failed due to insufficient funds. "
                f"Account {payment_addr} cannot pay tranction costs of {cost_ada} "
                f"lovelaces because it only contains {utxo_total_ada} ADA."
            )
        
        # Build the transaction to submit the pool certificate and delegation 
        # certificate(s) to the blockchain.
        tx_name = datetime.now().strftime("reg_stake_key_%Y-%m-%d_%Hh%Mm%Ss")
        tx_raw_file = Path(self.working_dir) / (tx_name + ".raw")
        cmd = (
            f"{self.cli} shelley transaction build-raw{tx_in_str} "
            f"--tx-out {payment_addr}+{utxo_total - min_fee - pool_deposit} "
            f"--ttl {ttl} --fee {min_fee} --out-file {tx_raw_file} "
            f"--certificate-file {pool_cert_path} {del_cert_args}"
        )
        subprocess.run(cmd.split())

        # Sign the transaction with both the payment and stake keys.
        tx_signed_file = Path(self.working_dir) / (tx_name + ".signed")
        cmd = (
            f"{self.cli} shelley transaction sign "
            f"--tx-body-file {tx_raw_file} --signing-key-file {payment_skey} "
            f"{signing_key_args} --signing-key-file {pool_cold_skey} "
            f"{self.network} --out-file {tx_signed_file}"
        )
        subprocess.run(cmd.split())

        # Submit the transaction
        cmd = (
            f"{self.cli} shelley transaction submit "
            f"--tx-file {tx_signed_file} {self.network}"
        )
        subprocess.run(cmd.split())

        # Delete the transaction files if specified.
        if cleanup:
            os.remove(tx_raw_file)
            os.remove(tx_signed_file)

    def retire_stake_pool(self, remaining_epochs, genesis_file, cold_vkey, 
        cold_skey, payment_skey, payment_addr):
        """Retire a stake pool using the stake pool keys.

        To retire the stake pool we need to:
        - Create a deregistration certificate and
        - Submit the certificate to the blockchain with a transaction

        The deregistration certificate contains the epoch in which we want to 
        retire the pool. This epoch must be after the current epoch and not 
        later than eMax epochs in the future, where eMax is a protocol
        parameter.
        """

        # Get the network parameters
        params_file = self.load_protocol_parameters()
        e_max = self.protocol_parameters["eMax"]

        # Make sure the remaining epochs is a valid number.
        if remaining_epochs < 1:
            remaining_epochs = 1
        elif remaining_epochs > e_max:
            raise ShelleyError(
                f"Invalid number of remaining epochs ({remaining_epochs}) "
                f"prior to pool retirement. The maximum is {e_max}."
            )

        # Get the network genesis parameters
        with open(genesis_file, "r") as genfile:
            genesis_parameters = json.load(genfile)
        epoch_length = genesis_parameters["epochLength"]

        # Determine the TTL
        tip = self.get_tip()
        ttl = tip + self.ttl_buffer

        # Get the current epoch
        epoch = tip // epoch_length

        # Create deregistration certificate
        pool_dereg = self.working_dir / "pool.dereg"
        cmd = (
            f"{self.cli} shelley stake-pool deregistration-certificate "
            f"--cold-verification-key-file {cold_vkey} "
            f"--epoch {epoch + remaining_epochs} --out-file {pool_dereg}"
        )
        subprocess.run(cmd.split())

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.get_utxos(payment_addr)
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Iterate through the UTXOs until we have enough funds to cover the 
        # transaction. Also, create the tx_in string for the transaction.
        utxo_total = 0
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            utxo_total += int(utxo['Lovelace'])
            tx_in_str += f" --tx-in {utxo['TxHash']}#{utxo['TxIx']}"

            # Calculate the minimum fee
            cmd = (
                f"{self.cli} shelley transaction calculate-min-fee "
                f"--tx-in-count {idx + 1} --tx-out-count 1 --ttl {ttl} "
                f"{self.network} --signing-key-file {payment_skey} "
                f"--signing-key-file {payment_skey} "
                f"--signing-key-file {cold_skey} "
                f"--certificate {pool_dereg} "
                f"--protocol-params-file {params_file}"
            )
            result = subprocess.run(cmd.split(), capture_output=True)
            min_fee = int(result.stdout.decode().split()[1])
            if utxo_total > min_fee:
                break

        if utxo_total < min_fee:
            cost_ada = min_fee/1_000_000
            utxo_total_ada = utxo_total/1_000_000
            raise ShelleyError(
                f"Transaction failed due to insufficient funds. "
                f"Account {addr} cannot pay tranction costs of {cost} "
                f"lovelaces because it only contains {utxo_total_ada} ADA."
            )

        # Build the raw transaction
        tx_raw = self.working_dir / "pool_dereg_tx.raw"
        cmd = (
            f"{self.cli} shelley transaction build-raw{tx_in_str} "
            f"--tx-out {payment_addr}+{utxo_total - min_fee} --ttl {ttl} "
            f"--fee {min_fee} --out-file {tx_raw} "
            f"--certificate-file {pool_dereg}"
        )
        subprocess.run(cmd.split())

        # Sign it with both the payment signing key and the cold signing key.
        tx_signed = self.working_dir / "pool_dereg_tx.signed"
        cmd = (
            f"{self.cli} shelley transaction sign --tx-body-file {tx_raw} "
            f"--signing-key-file {payment_skey} --signing-key-file {cold_skey} "
            f"{self.network} --out-file {tx_signed}"
        )
        subprocess.run(cmd.split())

        # Submit the transaction
        cmd = (
            f"{self.cli} shelley transaction submit "
            f"--tx-file {tx_signed} {self.network}"
        )
        subprocess.run(cmd.split())


if __name__ == "__main__":
    # Run Tests #

    # Test Inputs
    path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
    path_to_socket = "/home/cardano/viper-pool/relay-node/db/node.socket"
    working_dir = "/home/cardano/viper-pool/tools/"
    from_addr = "0040b9d5731b44c460f535f099b11e15287411356493a3b403d7a430d8a933f8a9462c1d2791ce2ef9c4613022f8ab8189168a6f7be02aa9bc763322d4995cd357"
    to_addr = "00326950228e95f1c9f0af8802137db85a985a4ffbd6c8e4cce3fe67e31fd461861680a365653455546b57be380f9607edfe2376539d639fbf4803866e2dc5b332"
    key_file = "/home/cardano/viper-pool/relay-node/payment.skey"
    genesis_json_file = "/home/cardano/viper-pool/relay-node/ff-genesis.json"

    # Create a ShelleyTools object
    shelley = ShelleyTools(path_to_cli, path_to_socket, working_dir, 
        network="--testnet-magic 42")

    # Run tests
    # print(shelley.cli)
    # print(shelley.load_protocol_parameters())
    # print(json.dumps(shelley.protocol_parameters, indent=4, sort_keys=True))
    # print(f"Tip = {shelley.get_tip()}")
    # print(shelley.make_address("test"))
    # print(json.dumps(shelley.get_utxos(from_addr), indent=4, sort_keys=True))
    # #shelley.send_payment(100, to_addr, from_addr, key_file, cleanup=True)
    # shelley.register_stake_address(
    #     from_addr,
    #     "/home/cardano/viper-pool/relay-node/stake.vkey", 
    #     "/home/cardano/viper-pool/relay-node/stake.skey",
    #     key_file)
    #shelley.create_block_producing_keys(genesis_json_file, "test_pool")