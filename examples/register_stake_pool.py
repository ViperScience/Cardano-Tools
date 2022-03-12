from cardano_tools import NodeCLI
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Stakepool registration inputs
working_dir = Path("/home/cardano/.cardano-tools/")
pmt_addr = "addr1..."
args = {
    "pool_name": "TICKER",
    "pool_pledge": 100_000 * 1_000_000,
    "pool_cost": 400 * 1_000_000,
    "pool_margin": 5,
    "pool_cold_vkey": working_dir / "POOL_cold.vkey",
    "pool_cold_skey": working_dir / "POOL_cold.skey",
    "pool_vrf_key": working_dir / "POOL_vrf.vkey",
    "pool_reward_vkey": working_dir / "rewards_acct_stake.vkey",
    "owner_stake_vkeys": [
        working_dir / "owner1_acct_stake.vkey",
        working_dir / "owner2_acct_stake.vkey",
    ],
    "owner_stake_skeys": [
        working_dir / "owner1_acct_stake.skey",
        working_dir / "owner2_acct_stake.skey",
    ],
    "payment_addr": pmt_addr,
    "payment_skey": working_dir / "pool_acct.skey",
    "genesis_file": "/home/cardano/relay-node/genesis.json",
    "pool_relays": [
        {"port": "1234", "host": "1.23.45.67", "host-type": "ipv4"},
        {"port": "1234", "host": "relay1.my-ada-pool.com", "host-type": "single"},
    ],
    "pool_metadata_url": "https://my-ada-pool.com/TICKER_metadata.json",
    "folder": working_dir,
}

cli = NodeCLI(
    "/home/cardano/.cabal/bin/cardano-cli",
    "/home/cardano/relay-node/db/node.socket",
    "/home/cardano/.cardano-tools/",
    network="--testnet-magic 42",
)

# Resister the stakepool on the blockchain
cli.register_stake_pool(**args)
# NOTE this is not the recommended method since it requires access to cold keys
# on a network connected machine. Use the pool registration transaction builder
# instead.
