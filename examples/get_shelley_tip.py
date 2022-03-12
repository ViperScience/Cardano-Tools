from cardano_tools import NodeCLI

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/relay-node/node.socket"
working_dir = "/home/cardano/.cardano-tools/"

cli = NodeCLI(
    path_to_cli, 
    path_to_socket,
    working_dir, 
    network="--testnet-magic 42"
)

print(f"Tip = {cli.get_tip()}")