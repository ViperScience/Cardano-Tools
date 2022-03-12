# Cardano Tools
A python module for interacting with the [Cardano](https://www.cardano.org/) 
blockchain.

## Installation

You can install Cardano Tools from PyPI:

```
pip install cardano-tools
```

The Cardano Tools package supports Python 3.9 and above.

## Usage

The library provides objects for interfacing with different parts of the Cardano ecosystem: the node, the node CLI, and the wallet server. The basic usage is outlined below. For more help see the [example scripts](https://gitlab.com/viper-staking/cardano-tools/-/tree/master/examples) and browse through the code.

### The Cardano-Node

A cardano-node may be started in passive mode from a Python script using the code:

    node = CardanoNode(
        binary="/usr/local/bin/cardano-node",
        topology=base_path / "mainnet-topology.json",
        database=base_path / "db",
        socket=base_path / "db" / "node.socket",
        config=base_path / "mainnet-config.json",
        show_output=True,  # Optionally print node output to the terminal.
    )
    node.start()

To run the node as a block producer, supply the additional parameters to the `CardanoNode` object constructor before starting.

    node = CardanoNode(
        binary="/usr/local/bin/cardano-node",
        topology="mainnet-topology.json",
        database="db",
        socket="node.socket",
        config="mainnet-config.json",
        kes_key="pool_kes.skey",
        vrf_key="pool_vrf.skey",
        cert="pool.cert",
        port=3002,  # defaults to 3001
    )
    node.start()

A running node may then be later stopped by calling `node.stop()` which sends the `SIGINT` signal to the node process. This allows the node to shutdown gracefully by closing the database files and results in faster startup times during the next run. This feature may be useful for using Python to automate node restarts.

See the [official cardano-node GitHub repository](https://github.com/input-output-hk/cardano-node) for details on the necessary arguments and files needed for operating the node as well as how to install the binary.

### The Cardano-Node CLI
The Cardano-Tools `NodeCLI` object provides a wrapped interface to functionality within the Cardano CLI. Raw methods are wrapped and provide a simple way to get results from CLI commands into your Python scripts. Also, common tasks that require multiple CLI commands are combined into easy to call methods.

    cli = NodeCLI(
        binary="/usr/local/bin/cardano-cli",
        socket="/home/nalyd88/ViperStaking/cardano-node/db/node.socket",
        working_dir=os.getcwd(),
        ttl_buffer=1000,          # optional (default 1000)
        network="--mainnet",      # optional (default --mainnet)
        era="--mary-era",         # optional (default --mary-era)
    )

    print(f"Tip = {cli.get_tip()}")

#### Managing Wallets
Many common tasks like checking balances and sending ADA are provided.

    # Get and print the ADA balance in an address
    addr = open(working_dir + "/mywallet.addr", 'r').read()
    print(cli.query_balance(addr))

    # Get and display all the UTxOs currently in a address
    print(json.dumps(cli.get_utxos(addr), indent=4, sort_keys=True))

    # Send ADA
    key_file = "/home/lovelace/cardano-node/owner.skey"
    to_addr = "addr_test1qpzft..."
    from_addr = "addr_test1qrjpd..."
    amt_ada = 10
    cli.send_payment(amt_ada, to_addr, from_addr, key_file)

#### Stake Pool Management
The Cardano-Tools library provides tools to help Cardano Stake-Pool Operators (SPOs) setup and maintain pools.

    # Generate a new set of pool keys.
    pool_id = cli.create_block_producing_keys(
        "/home/lovelace/cardano-node/mainnet-shelley-genesis.json",
        pool_name="TESTS"
    )

Remember to keep your cold keys in a secure, off-line, location!

    # Stakepool registration inputs
    pledges = {
        "owner1": 110_000,
        "owner2": 340_000,
    } # ADA
    pmt_addr = "addr1..."
    args = {
        "pool_name": "TESTS",
        "pool_pledge": sum(pledges.values())*1_000_000,
        "pool_cost": 340*1_000_000,
        "pool_margin": 1.0,
        "pool_cold_vkey":   "keys/TESTS_cold.vkey",
        "pool_vrf_key":     "keys/TESTS_vrf.vkey",
        "pool_reward_vkey": "owner1_pledge_stake.vkey",
        "owner_stake_vkeys": [
            "owner1_pledge_stake.vkey",
            "owner2_pledge_stake.vkey",
        ],
        "pool_relays": [
            {
                "port": "3001",
                "host": "myrelay.testspool.io",
                "host-type": "single"
            }
        ],
        "pool_metadata_url": "https://testspool.io/files/TESTS_metadata.json",
        "folder": working_dir
    }

    # Signatures required (must be present during signing).
    witness_files = [
        working_dir / "cold_witness.json",
        working_dir / "fees_witness.json",
        working_dir / "owner1_witness.json",
        working_dir / "owner2_witness.json",
    ]

    # Create the stake pool registration certificate and the transaction to be 
    # signed.
    raw_tx = cli.build_raw_transaction(
        pool_addr, 
        witness_count=len(witness_files),
        certs=[
            cli.generate_stake_pool_cert(**args)
        ]
    )

After the registration transaction is successfully signed by all the required keys (hardware wallets and cold keys), collect the witness files and then sign and send the stake pool registration transaction. 

    # Apply witness signatures
    signed_tx = cli.witness_transaction(raw_tx, witness_files)

    # Send the transaction
    cli.submit_transaction(signed_tx)

#### Minting and Burning Non-Fungible Tokens (NFTs)

The first step in minting an NFT, other than the art work 😉, is to create a policy ID. 

    # Get hashes of the verification keys from the signing keys.
    vkey_hash = cli.get_key_hash("./payment.vkey")

    # Time until policy ID closes
    genesis = "/home/lovelace/cardano-node/mainnet-shelley-genesis.json"
    slots_till_close = cli.days2slots(365, genesis)  # 1 yr
    closing_slot = cli.get_tip() + slots_till_close

    # Create the minting script
    multi_script = cli.build_multisignature_scripts(
        "policyid-name-multisig",
        [vkey_hash],  # Supports multiple signing keys
        "all",
        end_slot=closing_slot,
    )

    # Generate the policy ID
    policy_id = cli.generate_policy(multi_script)

Next, we must create the asset metadata and then store it in a JSON file.
This is not specific to the Cardano-Tools library.

    metadata = {
        "721": {
            policy_id: policy_id,
            "version": "1.0"
            "COOL_NFT_00": {
                "image": "ipfs://...",
                ...
            }
        }
    }

    with open("my_nft_metadata.json", 'w') as outfile:
        json.dump(metadata, outfile, indent=4)

Then all we have to do is simply build and send the minting transaction.

    # Address that will own the NFT when it is minted. 
    addr = "addr1..."

    # You can mint more than one NFT at a time but we will do just one here.
    asset_names = ["COOL_NFT_00",]

    # Since we are minting NFTs and not FTs, set the amounts to 1.
    asset_amounts = [1 for i in asset_names]

    # Build the minting transaction
    tx_file = cli.build_mint_transaction(
        policy_id,
        asset_names, 
        asset_amounts,
        addr,
        n_wit := 1,  # Number of signing keys in multi-sig script
        tx_metadata="my_nft_metadata.json",
        minting_script="policyid-name-multisig.json",
        ada=3  # Optionally specify some ADA to exist in the UTxO with the NFT
    )

    # Sign the transaction
    skey = "payment.skey"
    signed_tx = cli.sign_transaction(tx_file, [skey,])

    # Send the transaction
    cli.submit_transaction(signed_tx)

If you need to burn an NFT, the process is similar.

    tx_file = cli.build_burn_transaction(
        policy_id, 
        asset_names, 
        asset_amounts,
        addr, 
        n_wit := 1,
        minting_script="policyid-name-multisig.json",
    )

Sending an NFT is also covered.


    # Address that currently owns the UTxOs 
    from_addr = open("payment.addr", 'r').read().strip()

    # Address to receive the token
    to_addr = "addr1..."

    # Asset name to send
    asset_name = "COOL_NFT_00"

    # Build the sending transaction
    tx_file = cli.build_send_tx(
        to_addr,
        from_addr,
        quantity := 1,
        policy_id,
        asset_name=asset_name,
    )

    # Sign the transaction
    skey1 = "payment.skey"
    signed_tx = cli.sign_transaction(tx_file, [skey1])

# Send the transaction
if click.confirm("Do you want to send?", abort=True):
    txid = cli.submit_transaction(signed_tx)
    logging.info(f"Send transaction: {txid}")

### The Cardano Wallet
The Cardano-Tools library contains an interface to the [Cardano wallet back end](https://github.com/input-output-hk/cardano-wallet), which may be accessed via either the CLI or through HTTP requests.

#### CLI

    cw_cli = WalletCLI(
        path_to_cli="/usr/local/bin/cardano-wallet"
    )

    logging.basicConfig(level=logging.DEBUG)

    # Find the wallet
    wallet = cw_cli.get_wallet_by_name("ADDER_Rewards")
  
    # Print the balance (ADA)
    print(int(wallet["balance"]["total"]["quantity"])/1_000_000)

    # Use the built-in method
    print(cw_cli.get_wallet_balance(wallet["id"]))

#### HTTP Server

    cw_http = WalletHTTP(
        wallet_server="http://127.0.0.1",
        wallet_server_port=8090
    )

    ada_amt = 100.5
    rx_address = "addr1...."

    wallet = cw_http.get_wallet_by_name("ExampleWallet")

    # Get the passphrase from an env variable. DO NOT store in script.
    # Example ZSH shell command to save the password in a local variable
    # without it being stored in the command history:
    #
    #     $ read "?Enter password: " WALLET_PASS
    #     $ export WALLET_PASS
    #
    passphrase = os.getenv('WALLET_PASS')

    cw_http.send_ada(
        wallet.get("id"),
        rx_address,
        ada_amt,
        passphrase,
        wait=True
    )

## Logging

The modules include detailed logging for debugging. To enable most log messages, import the logging module and include the following at the beginning of your scripts.

    logging.basicConfig(level=logging.DEBUG)

The [example scripts](https://gitlab.com/viper-staking/cardano-tools/-/tree/master/examples) illustrate how to enable logging.

## Contributors

This project is developed and maintained by the team at [Viper Staking](https://viperstaking.com/).

## Related Projects

The Cardano-Tools library is also used in the official [Viper Staking Docker containers](https://gitlab.com/viper-staking/docker-containers).
