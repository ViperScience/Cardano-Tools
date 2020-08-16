import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Test Inputs
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
# path_to_socket = "/home/cardano/relay-node/db/node.socket"
# working_dir = "/home/cardano/.cardano-tools/"
working_dir = "/home/cardano/viper-pool/pool-setup"
path_to_socket = "/home/cardano/viper-pool/node-mainnet/node.socket"

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli, 
    path_to_socket,
    working_dir
)

# Run tests
cold_vkey_path = "/home/cardano/viper-pool/pool-setup/VIPER_cold.vkey"
print(f"Pool ID = {shelley.get_stake_pool_id(cold_vkey_path)}")