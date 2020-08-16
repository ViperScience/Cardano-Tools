import sys
sys.path.append('../')
from cardano_tools import ShelleyTools

# Inputs (change for your node!)
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/viper-pool/node-mainnet/node.socket"
working_dir = "/home/cardano/pool-setup-test/"

# Create a ShelleyTools object
shelley = ShelleyTools(
            path_to_cli,
                path_to_socket,
                    working_dir
                    )

# Create the new address and all the required key files.
owner1_addr = shelley.make_address("owner1")
owner2_addr = shelley.make_address("owner2")
rewards_addr = shelley.make_address("rewards")
print(f"Owner #1 account number: {owner1_addr}")
print(f"Owner #2 account number: {owner2_addr}")
print(f"Rewards account number: {rewards_addr}")
