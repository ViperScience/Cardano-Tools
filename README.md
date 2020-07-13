# Cardano Tools
A python module for interacting with the [Cardano](https://www.cardano.org/) 
blockchain.

The `Cardano-Tools` module provides functionality for interfacing with running
full nodes on local or remote hosts. A running Cardano node is a prerequisite
for using this package. 

Provided tools include:
* Interfacing with the node:
  * Starting a relay or pool node locally and remotely.
  * Getting the node tip. 
* Creating and administrating a wallet:
  * Create a new wallet address
  * Get UTXO list
  * Send a payment
  * Register a staking address
  * Get the blockchain tip
* Creating and administrating a stake pool:
  * Create block producing keys
  * Register a stake pool
  * Retire a stake pool

This project is developed and maintained by the team at 
[Viper Staking](https://viperscience.com/adapool#portfolio).

## Installation

You can install Cardano Tools from PyPI:

```
pip install cardano-tools
```

The Cardano Tools package supports Python 3.7 and above.

## Examples

For more detailed examples, see the [example scripts](https://gitlab.com/viper-staking/cardano-tools/-/tree/master/examples).

### Shelley Tools

The `ShelleyTools` class provides an interface to the `cardano-cli shelley` 
commands. An example for creating a wallet is given below.

```python
from cardano_tools import ShelleyTools

# Test Inputs (example paths)
path_to_cli = "/home/user/.cabal/bin/cardano-cli"
path_to_socket = "/home/user/relay-node/db/node.socket"
working_dir = "/home/user/.cardano-tools/"

# Create a ShelleyTools object
shelley = ShelleyTools(
    path_to_cli, 
    path_to_socket, 
    working_dir, 
    network="--testnet-magic 42"  # <-- For the testnet (default: --mainnet)
)

# Create a wallet address with both spending and staking keys.
print(shelley.make_address("my_wallet"))
```

Optionally, an [SSH connection object](https://docs.fabfile.org/en/2.5/api/connection.html) may be specified if working with remote hosts.

```python
from cardano_tools import ShelleyTools
from fabric import Connection

conn = Connection(
    host="hostname",
    user="admin",
    connect_kwargs={
        "key_filename": "/home/myuser/.ssh/private.key",
    },
)

shelley = ShelleyTools(
    path_to_cli, 
    path_to_socket, 
    working_dir,
    ssh=conn
)
```


