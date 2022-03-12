from cardano_tools import NodeCLI

# Inputs (change for your node!)
path_to_cli = "/home/cardano/.cabal/bin/cardano-cli"
path_to_socket = "/home/cardano/node-mainnet/node.socket"
working_dir = "/home/cardano/pool-setup-test/"

cli = NodeCLI(
    path_to_cli,
    path_to_socket,
    working_dir
)

# Create the new address and all the corresponding key files.
owner1_addr = cli.make_address("owner1")
owner2_addr = cli.make_address("owner2")
rewards_addr = cli.make_address("rewards")
print(f"Owner #1 address: {owner1_addr}")
print(f"Owner #2 address: {owner2_addr}")
print(f"Rewards address: {rewards_addr}")
