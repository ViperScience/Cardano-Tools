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
        ttl_buffer=1000, network="--mainnnet"):

        # Set the path to the CLI and verify it works. An exception will be 
        # thrown if the command is not found.
        self.cli = path_to_cli
        subprocess.run([self.cli, "--version"], capture_output=True)

        # Set the socket path and export it as an environment variable.
        self.socket = path_to_socket
        os.environ["CARDANO_NODE_SOCKET_PATH"] = self.socket

        # Set the working directory. Create the path if it doesn't exist.
        self.working_dir = working_dir
        Path(working_dir).mkdir(parents=True, exist_ok=True)
        
        self.ttl_buffer = ttl_buffer
        self.network = network
        self.protocol_parameters = None

    def load_protocol_parameters(self):
        """Load the protocol parameters which are needed for creating 
        transactions.
        """
        params_file = self.working_dir + "protocol.json"
        arg = (
            f"{self.cli} shelley query protocol-parameters {self.network} "
            f"--out-file {params_file}"
        )
        subprocess.run(arg.split())
        with open(params_file, 'r') as json_file:
            self.protocol_parameters = json.load(json_file)
        return params_file

    def get_tip(self):
        """Query the node for the current tip of the blockchain.
        """
        arg = f"{self.cli} shelley query tip {self.network}"
        result = subprocess.run(arg.split(), capture_output=True)
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

        # Generate payment key pair.
        arg = (
            f"{self.cli} shelley address key-gen "
            f"--verification-key-file {payment_vkey} "
            f"--signing-key-file {payment_skey}"
        )
        subprocess.run(arg.split())

        # Generate stake key pair.
        arg = (
            f"{self.cli} shelley stake-address key-gen "
            f"--verification-key-file {stake_vkey} "
            f"--signing-key-file {stake_skey}"
        )
        subprocess.run(arg.split())

        # Create the payment address.
        arg = (
            f"{self.cli} shelley address build "
            f"--payment-verification-key-file {payment_vkey} "
            f"--stake-verification-key-file {stake_vkey} "
            f"--out-file {payment_addr} {self.network}"
        )
        subprocess.run(arg.split())
        
        # Read the file and return the payment address.
        with open(payment_addr, 'r') as payment_addr_file:
            addr = payment_addr_file.read().strip()
        return addr

    def get_utxos(self, addr):
        """Query the list of UTXOs for a given address and parse the output. 
        The returned data is formatted as a list of dict objects.
        """
        arg = f"{self.cli} shelley query utxo --address {addr} {self.network}"
        result = subprocess.run(arg.split(), capture_output=True)
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
        arg = (
            f"{self.cli} shelley transaction calculate-min-fee "
            f"--tx-in-count {tx_in_count} --tx-out-count 2 --ttl {ttl} "
            f"{self.network} --signing-key-file {key_file} "
            f"--protocol-params-file {params_file}"
        )
        result = subprocess.run(arg.split(), capture_output=True)
        min_fee = int(result.stdout.decode().split()[1])

        # Build the transaction
        tx_raw_file = Path(self.working_dir) / (tx_name + ".raw")
        arg = (
            f"{self.cli} shelley transaction build-raw{tx_in} "
            f"--tx-out {to_addr}+{payment} "
            f"--tx-out {from_addr}+{total_in - payment-min_fee} "
            f"--ttl {ttl} --fee {min_fee} --out-file {tx_raw_file}"
        )
        subprocess.run(arg.split())

        # Sign the transaction with the signing key
        tx_signed_file = Path(self.working_dir) / (tx_name + ".signed")
        arg = (
            f"{self.cli} shelley transaction sign "
            f"--tx-body-file {tx_raw_file} --signing-key-file {key_file} "
            f"{self.network} --out-file {tx_signed_file}"
        )
        subprocess.run(arg.split())

        # Submit the transaction
        arg = (
            f"{self.cli} shelley transaction submit "
            f"--tx-file {tx_signed_file} {self.network}"
        )
        subprocess.run(arg.split())

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
        arg = (
            f"{self.cli} shelley stake-address registration-certificate "
            f"--stake-verification-key-file {stake_vkey_file} "
            f"--out-file {stake_cert_path}"
        )
        result = subprocess.run(arg.split(), stdout=subprocess.PIPE)

        # Determine the TTL
        tip = self.get_tip()
        ttl = tip + self.ttl_buffer

        # Get a list of UTXOs and sort them in decending order by value.
        utxos = self.get_utxos(addr)
        utxos.sort(key=lambda k: k["Lovelace"], reverse=True)

        # Iterate through the UTXOs until we have enough funds to cover the 
        # transaction. Also, create the tx_in string for the transaction.
        utxo_total = 0
        tx_in_str = ""
        for idx, utxo in enumerate(utxos):
            utxo_total += int(utxo['Lovelace'])
            tx_in_str += f" --tx-in {utxo['TxHash']}#{utxo['TxIx']}"

            # Calculate the minimum fee
            params_file = self.load_protocol_parameters()
            arg = (
                f"{self.cli} shelley transaction calculate-min-fee "
                f"--tx-in-count {idx + 1} --tx-out-count 1 --ttl {ttl} "
                f"{self.network} --signing-key-file {pmt_skey_file} "
                f"--signing-key-file {stake_skey_file} "
                f"--certificate-file {stake_cert_path} "
                f"--protocol-params-file {params_file}"
            )
            result = subprocess.run(arg.split(), capture_output=True)
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
        arg = (
            f"{self.cli} shelley transaction build-raw{tx_in_str} "
            f"--tx-out {from_addr}+{utxo_total - cost} "
            f"--ttl {ttl} --fee {min_fee} --out-file {tx_raw_file} "
            f"--certificate-file {stake_cert_path}"
        )
        subprocess.run(arg.split())

        # Sign the transaction with both the payment and stake keys.
        tx_signed_file = Path(self.working_dir) / (tx_name + ".signed")
        arg = (
            f"{self.cli} shelley transaction sign "
            f"--tx-body-file {tx_raw_file} --signing-key-file {pmt_skey_file} "
            f"--signing-key-file {stake_skey_file} {self.network} "
            f"--out-file {tx_signed_file}"
        )
        subprocess.run(arg.split())

        # Submit the transaction
        arg = (
            f"{self.cli} shelley transaction submit "
            f"--tx-file {tx_signed_file} {self.network}"
        )
        subprocess.run(arg.split())

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
        arg = (
            f"{self.cli} shelley node key-gen "
            f"--cold-verification-key-file {cold_vkey} "
            f"--cold-signing-key-file {cold_skey} "
            f"--operational-certificate-issue-counter-file {cold_counter}"
        )
        subprocess.run(arg.split())

        # Generate VRF Key pair
        vrf_vkey = folder / (pool_name + "_vrf.vkey")
        vrf_skey = folder / (pool_name + "_vrf.skey")
        arg = (
            f"{self.cli} shelley node key-gen-VRF "
            f"--verification-key-file {vrf_vkey} "
            f"--signing-key-file {vrf_skey}"
        )
        subprocess.run(arg.split())

        # Generate the KES Key pair
        kes_vkey = folder / (pool_name + "_kes.vkey")
        kes_skey = folder / (pool_name + "_kes.skey")
        arg = (
            f"{self.cli} shelley node key-gen-KES "
            f"--verification-key-file {kes_vkey} "
            f"--signing-key-file {kes_skey}"
        )
        subprocess.run(arg.split())

        # Get the network protocol parameters
        with open(genesis_file, "r") as genfile:
            genesis_parameters = json.load(genfile)

        # Generate the Operational Certificate/
        cert_file = folder / (pool_name + ".cert")
        slots_kes_period = genesis_parameters["slotsPerKESPeriod"]
        tip = self.get_tip()
        kes_period = tip // slots_kes_period  # Integer division
        arg = (
            f"{self.cli} shelley node issue-op-cert "
            f"--kes-verification-key-file {kes_vkey} "
            f"--cold-signing-key-file {cold_skey} "
            f"--operational-certificate-issue-counter {cold_counter} "
            f"--kes-period {kes_period} --out-file {cert_file}"
        )
        subprocess.run(arg.split())


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
    shelley.create_block_producing_keys(genesis_json_file, "test_pool")