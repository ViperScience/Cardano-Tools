import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/node/db/node.socket"
working_dir = "/home/cardano/.cardano-tools/"

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli, 
    path_to_socket,
    working_dir
)
shelley.debug = True

# Resister the stakepool on the blockchain
shelley.update_kes_keys(
    "/home/cardano/node/mainnet-shelley-genesis.json",
    "/home/cardano/.cardano-tools/APOOL_cold.skey",
    "/home/cardano/.cardano-tools/APOOL_cold.counter",
    pool_name="APOOL"
)
