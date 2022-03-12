from cardano_tools import NodeCLI

# Stakepool registration inputs
metadata = {
    "name": "My pool name",
    "description": "My pool description.",
    "ticker": "TICKER",
    "homepage": "https://my-ada-pool.com/"
}

cli = NodeCLI(
    "/home/cardano/.cabal/bin/cardano-cli", 
    "/home/cardano/relay-node/db/node.socket", 
    "/home/cardano/.cardano-tools/"
)

# Create the Metadata JSON file
metadata_hash = cli.create_metadata_file(metadata) 
print(metadata_hash)