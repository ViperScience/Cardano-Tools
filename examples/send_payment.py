from cardano_tools import NodeCLI
import logging

# Setup logging (optional)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Test Inputs
path_to_cli = "/usr/local/bin/cardano-cli"
path_to_socket = "/home/lovelace/cardano-node/node.socket"
working_dir = "/home/lovelace/cardano-node/"
key_file = "/home/lovelace/cardano-node/owner.skey"
to_addr = "addr_test1qpzft..."
from_addr = "addr_test1qrjpd..."
amt_ada = 10

cli = NodeCLI(
    path_to_cli,
    path_to_socket,
    working_dir,
    network="--testnet-magic 42"  # <-- for the testnet
)

# Send the payment
cli.send_payment(amt_ada, to_addr, from_addr, key_file)
