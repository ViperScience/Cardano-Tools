import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/db/node.socket"
working_dir = "/home/cardano/.cardano-tools/"

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli, 
    path_to_socket,
    working_dir, 
    network="--testnet-magic 42"
)

# Run tests
print(shelley.cli)
print(f"Tip = {shelley.get_tip()}")