import logging

from cardano_tools import NodeCLI

# Setup logging (optional)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Test Inputs
path_to_cli = "cardano-cli"
path_to_socket = "/ipc/node.socket"
working_dir = "./config"
key_file = "./config/payment.skey"
to_addr = "addr_test1qz7aejw84hukpcuqeywa3mmdgt95vtzv5mqp278g4zeua6hg0h2the7qucaar36nrfntslk57xd7p4ulkgy52ds7ysqqjecqjf"
from_addr = "addr_test1qp2fg770ddmqxxduasjsas39l5wwvwa04nj8ud95fde7f70k6tew7wrnx0s4465nx05ajz890g44z0kx6a3gsnms4c4qq8ve0n"
amt_ada = 10

cli = NodeCLI(
    path_to_cli, path_to_socket, working_dir, network="--testnet-magic 1"  # <-- for the testnet
)

# Send the payment
cli.send_payment(amt_ada, to_addr, from_addr, key_file, cleanup=False)
