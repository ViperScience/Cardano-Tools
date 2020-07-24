import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Inputs
genesis_file = "/home/lovelace/cardano-node/shelley_testnet-genesis.json"
working_dir = "/home/lovelace/cardano-node/"

# Create a ShelleyTools object
shelley = ShelleyTools(
    "/usr/local/bin/cardano-cli",
    "/home/lovelace/cardano-node/node.socket",
    working_dir,
    network="--testnet-magic 42"  # <-- for testnet only
)

# Generate the pool keys.
pool_id = shelley.create_block_producing_keys(genesis_file, pool_name="POOL")
print(f"Stake Pool ID: {pool_id}")
