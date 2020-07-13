import sys
sys.path.append('../')
from cardano_tools import ShelleyTools
from fabric import Connection

# Test Inputs
path_to_cli = "/home/myuser/.cabal/bin/cardano-cli"
path_to_socket = "/home/myuser/relay-node/db/node.socket"
working_dir = "/home/myuser/.cardano-tools/"

# SSH connection to remote host
conn = Connection(
    host="hostname",
    user="admin",
    connect_kwargs={
        "key_filename": "/home/myuser/.ssh/private.key",
    },
)

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli, 
    path_to_socket, 
    working_dir,
    ssh=conn,
    network="--testnet-magic 42"
)

# Run tests
print(shelley.cli)
print(f"Tip = {shelley.get_tip()}")