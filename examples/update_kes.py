from cardano_tools import NodeCLI

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/node/node.socket"
working_dir = "/home/cardano/.cardano-tools/"

cli = NodeCLI(path_to_cli, path_to_socket, working_dir)

cli.update_kes_keys(
    "/home/cardano/node/mainnet-shelley-genesis.json",
    "/home/cardano/.cardano-tools/APOOL_cold.skey",
    "/home/cardano/.cardano-tools/APOOL_cold.counter",
    pool_name="APOOL",
)
