import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Test Inputs
path_to_cli = "/usr/local/bin/cardano-cli"
path_to_socket = "/home/lovelace/cardano-node/node.socket"
working_dir = "/home/lovelace/cardano-node/"
key_file = "/home/lovelace/cardano-node/owner.skey"
to_addr = "addr_test1qpzft..."
from_addr = "addr_test1qrjpd..."
amt_ada = 10

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli,
    path_to_socket,
    working_dir,
    network="--testnet-magic 42"  # <-- for the testnet
)
shelley.debug = True  # <-- print debug info

# Send the payment
shelley.send_payment(amt_ada, to_addr, from_addr, key_file)
