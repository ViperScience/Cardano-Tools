from cardano_tools import NodeCLI

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
working_dir = "/home/cardano/viper-pool/pool-setup"
path_to_socket = "/home/cardano/node/node.socket"

cli = NodeCLI(
    path_to_cli, 
    path_to_socket,
    working_dir
)

# Run tests
cold_vkey_path = "/home/cardano/secure/VIPER_cold.vkey"
print(f"Pool ID = {cli.get_stake_pool_id(cold_vkey_path)}")