from cardano_tools import NodeCLI
import logging
import json
import sys

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("cardano-tools-tests.log"),
        logging.StreamHandler(sys.stdout),
    ],
)

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/node.socket"
working_dir = "/home/cardano/.cardano-tools/"
addr = "addr1..."

cli = NodeCLI(path_to_cli, path_to_socket, working_dir, 
    network="--testnet-magic 1097911063")

print(json.dumps(cli.get_utxos(addr), indent=4, sort_keys=True))
