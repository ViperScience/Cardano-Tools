import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/db/node.socket"
working_dir = "/home/cardano/.cardano-tools/"
genesis_json_file = "/home/cardano/relay-node/ff-genesis.json"
cold_vkey = "/home/cardano/tools/pool_cold.vkey"
cold_skey = "/home/cardano/tools/pool_cold.skey"
pmt_skey = "/home/cardano/relay-node/payment.skey"
addr = ""

# Create a ShelleyTools object
shelley = ShelleyTools(path_to_cli, path_to_socket, working_dir, 
    network="--testnet-magic 42")

# Run tests
shelley.retire_stake_pool(
    10, genesis_json_file, cold_vkey, cold_skey, pmt_skey, addr)