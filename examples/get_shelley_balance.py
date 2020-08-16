import sys
sys.path.append('../')
from cardano_tools import ShelleyTools
from pathlib import Path

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/db/node.socket"
working_dir = Path("/home/cardano/.cardano-tools/")

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli,
    path_to_socket,
    working_dir
)
# shelley.debug = True

# Get the addresses
addr = open(working_dir / "mywallet.addr", 'r').read()

# Get and print the balances
print(shelley.query_balance(addr))