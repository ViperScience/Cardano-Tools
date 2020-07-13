import sys
sys.path.append('../')
from cardano_tools import ShelleyTools
import json

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/db/node.socket"
working_dir = "/home/cardano/.cardano-tools/"
addr = ""

# Create a ShelleyTools object
shelley = ShelleyTools(path_to_cli, path_to_socket, working_dir, 
    network="--testnet-magic 42")

# Create the new address and all the required key files. Optionally specify a
# location for the files other than the object's working directory.
print(shelley.make_address("test_addr_name"))