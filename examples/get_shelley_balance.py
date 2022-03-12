from cardano_tools import NodeCLI
from pathlib import Path

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/db/node.socket"
working_dir = Path("/home/cardano/.cardano-tools/")

cli = NodeCLI(path_to_cli, path_to_socket, working_dir)

# Get the addresses
addr = open(working_dir + "/mywallet.addr", "r").read()

# Get and print the balances
print(cli.query_balance(addr))
