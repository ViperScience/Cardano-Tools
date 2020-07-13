import sys
sys.path.append('../')
from cardano_tools import ShelleyTools
import json
from pathlib import Path

# Stakepool registration inputs
metadata = {
    "name": "My pool name",
    "description": "My pool description.",
    "ticker": "TICKER",
    "homepage": "https://my-ada-pool.com/"
}

# Create a ShelleyTools object
shelley = ShelleyTools(
    "/home/cardano/.cabal/bin/cardano-cli", 
    "/home/cardano/relay-node/db/node.socket", 
    "/home/cardano/.cardano-tools/"
)

# Create the Metadata JSON file
metadata_hash = shelley.create_metadata_file(metadata) 
print(metadata_hash)