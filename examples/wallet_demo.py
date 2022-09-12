import json
import logging
import math
import time

from cardano_tools import WalletCLI, WalletHTTP

logging.basicConfig(level=logging.INFO)


def generate_mnemonic():
    """We need to use the CLI API to generate the mnemonmic, as it is not supported
    by the HTTP API. We use HTTP for everything else.
    """
    print("Generating new mnemonic phrase")
    cw_cli = WalletCLI(path_to_cli="cardano-wallet")
    return cw_cli.recovery_phrase_generate()


def wallet_demo(
    wallet1_name: str, mnemonic1: str, wallet2_name: str, mnemonic2: str, cleanup: bool = False
):
    cw_api = WalletHTTP()
    default_passphrase = "$3cur3p@$$ph@$3"

    if not cw_api.get_wallet_by_name(wallet1_name):
        print(f"Creating wallet: {wallet1_name}")
        cw_api.create_wallet(wallet1_name, mnemonic1.split(" "), default_passphrase)
    else:
        print(f"Wallet {wallet1_name} already imported")

    if not cw_api.get_wallet_by_name(wallet2_name):
        print(f"Creating wallet: {wallet2_name}")
        cw_api.create_wallet(wallet2_name, mnemonic2.split(" "), default_passphrase)
    else:
        print(f"Wallet {wallet2_name} already imported")
    print("")

    print("Getting wallets by name...")
    w1: dict = cw_api.get_wallet_by_name(wallet1_name)
    w1_id: str = w1.get("id")
    w2: dict = cw_api.get_wallet_by_name(wallet2_name)
    w2_id: str = w2.get("id")
    print("")

    print("Getting wallets by ID...")
    wallet_by_id: dict = cw_api.get_wallet(w1_id)
    assert wallet_by_id.get("id") == w1_id
    print("")

    print("Renaming wallet...")
    print("")
    new_name = f"{wallet1_name}_renamed"
    result = cw_api.rename_wallet(w1_id, new_name)
    assert result.get("name") == new_name
    # Change back to old name
    result = cw_api.rename_wallet(w1_id, wallet1_name)
    assert result.get("name") == wallet1_name

    print("Changing wallet passphrase...")
    print("")
    result = cw_api.update_passphrase(w1_id, default_passphrase, f"{default_passphrase}+1")
    assert result
    # Change passphrase back to original
    result = cw_api.update_passphrase(w1_id, f"{default_passphrase}+1", default_passphrase)
    assert result

    # Get wallet balance 2 ways: from metadata and from builtin method
    w1_balance_metadata = w1.get("balance").get("total").get("quantity") / 1_000_000
    w1_ada_balance, w1_token_balance = cw_api.get_balance(w1_id)
    w1_ada_balance = w1_ada_balance.get("quantity") / 1_000_000
    assert math.isclose(w1_balance_metadata, w1_ada_balance)
    print(f"{wallet1_name} balance: {w1_ada_balance} ADA")
    w2_ada_balance, w2_token_balance = cw_api.get_balance(w2_id)
    w2_ada_balance = w2_ada_balance.get("quantity") / 1_000_000
    print(f"{wallet2_name} balance: {w2_ada_balance} ADA")
    print("")

    # List assets from metadata
    if len(w1_token_balance) > 1:
        print(f"{wallet1_name} has the following assets:")
        for token in w1_token_balance:
            print(f"\t{token}")
    if len(w2_token_balance) > 1:
        print(f"{wallet2_name} has the following assets:")
        for token in w2_token_balance:
            print(f"\t{token}")
    print("")

    # List assets using builtin method
    w1_assets = cw_api.get_assets(w1_id)
    print(f"{wallet1_name} associated assets w/ metadata: {w1_assets}")
    w2_assets = cw_api.get_assets(w2_id)
    print(f"{wallet2_name} associated assets w/ metadata: {w2_assets}")
    print("")

    if len(w1_token_balance) > 1:
        print(f"Getting first asset of {wallet1_name}...")
        policy_id = w1_tokens[0].get("policy_id")
        asset_name = w1_tokens[0].get("asset_name")
        first_asset = cw_api.get_asset(w1_id, policy_id, asset_name)
        print(f"\t{first_asset}")
        print("")

    w1_a1 = cw_api.get_addresses(w1_id)[0]
    print(f"First address of {wallet1_name}: {w1_a1}")
    print(f"Address inspect: {cw_api.inspect_address(w1_a1)}")
    w2_a1 = cw_api.get_addresses(w2_id)[0]
    print(f"First address of {wallet2_name}: {w2_a1}")
    print(f"Address inspect: {cw_api.inspect_address(w2_a1)}")
    print("")

    # estimated_fee = cw_api.estimate_tx_fee(w1_id, w2_a1, 10_000_000)
    # print(f"Estimated transaction fee for sending 10 ADA: {estimated_fee}")

    # print(f"Sending 10 ADA from {wallet1_name} to {wallet2_name}...")
    # cw_api.send_ada(w1_id, w2_a1, 10, default_passphrase, wait=True)
    # w1_new_balance = cw_api.get_balance(w1_id)[0].get("quantity") / 1_000_000
    # w2_new_balance = cw_api.get_balance(w2_id)[0].get("quantity") / 1_000_000
    # print(f"{wallet1_name} new balance: {w1_new_balance}")
    # print(f"{wallet2_name} new balance: {w2_new_balance}")
    # print("")

    print(f"Constructing transaction for {wallet1_name}...")
    payload = json.loads(
        f"""{{
            "payments": [
                {{
                    "address": "{w2_a1}",
                    "amount": {{
                        "quantity": 1000000,
                        "unit": "lovelace"
                    }}
                }}
            ],
            "withdrawal": "self",
            "validity_interval": {{
                "invalid_hereafter": {{
                    "quantity": 3600,
                    "unit": "second"
                }}
            }},
            "encoding": "base16"
        }}"""
    )
    tx = cw_api.construct_transaction(w1_id, payload)
    encoded_tx = tx.get("transaction")
    print(f"Constructed payload: {tx}")
    print("")

    signed_tx = cw_api.sign_transaction(w1_id, default_passphrase, encoded_tx)
    print(f"Signed transaction: {signed_tx}")
    print("")

    decoded_tx = cw_api.decode_transaction(w1_id, signed_tx.get("transaction"))
    print(f"Decoded transaction: {decoded_tx}")
    print("")

    # print(f"Submitting transaction...")
    # tx_output = cw_api.submit_transaction(w1_id, signed_tx.get("transaction"))
    # print("")

    migration_plan = cw_api.create_migration_plan(w1_id, [w2_a1])
    print(f"Plan for migrating {wallet1_name} UTxO balance to {wallet2_name}:")
    print(migration_plan)
    print("")

    print(f"{wallet1_name} UTxO stats:")
    print(f"\t{cw_api.get_utxo_stats(w1_id)}")
    print("")

    print(f"{wallet1_name} UTxO snapshot:")
    print(f"\t{cw_api.get_utxo_snapshot(w1_id)}")
    print("")

    w1_txs = cw_api.get_transactions(w1_id)
    w1_tx0 = w1_txs[0]
    print(f"{wallet1_name} has {len(w1_txs)} total transactions.")
    print(f"{wallet1_name} first transaction: {w1_tx0}")
    print("")

    print(f"Network parameters: {cw_api.get_network_params()}")
    print("")

    print(f"Network information: {cw_api.get_network_info()}")
    print("")

    print(f"Network clock: {cw_api.get_network_clock()}")
    print("")

    acct_pubkey = cw_api.create_account_public_key(w1_id, "1852H", default_passphrase)
    print(f"Derived account public key for index 1852H: {acct_pubkey}")
    acct_pubkeys = cw_api.get_account_public_key(w1_id)
    print(f"Retrieved account public keys: {acct_pubkeys}")
    utxo_soft_key = cw_api.get_public_key(w1_id, "utxo_external", "0")
    print(f"UTxO external public key: {utxo_soft_key}")
    print("")

    print(f"{wallet1_name} stake keys: {cw_api.list_stake_keys(w1_id)}")
    print("")

    stake_pools = cw_api.list_stake_pools(int(w1_ada_balance * 1e6))
    print(f"{len(stake_pools)} total stake pools.")
    print(f"First pool in list: {stake_pools[0]}")
    pool_id = stake_pools[0].get("id")
    print(f"Delegating {wallet1_name} to stake pool {pool_id}...")
    cw_api.join_stake_pool(w1_id, default_passphrase, pool_id)
    time.sleep(10)
    print(f"Undelegating {wallet1_name}...")
    cw_api.quit_staking(w1_id, default_passphrase)
    print("")

    print(f"Pool maintenance actions: {cw_api.pool_maintenance_actions()}")
    print(f"Forcing stake pool garbage collection...")
    cw_api.trigger_pool_maintenance("gc_stake_pools")
    print("")

    if cleanup:
        print("Deleting wallets")
        cw_api.delete_wallet(w1_id)
        cw_api.delete_wallet(w2_id)


if __name__ == "__main__":
    # mnemonic = generate_mnemonic()
    # Use fixed testnet wallets so we can work with a nonzero balance
    w1_seed = "fragile pottery wolf snack wet dolphin wish guard step track second rally panda desk because hollow route carpet ghost worry address ecology frown join"
    w2_seed = "evoke pull giraffe enhance beach ripple alien pottery beach bubble rail hold finish slice power parade brief rough fame type hungry guilt tail cabbage"
    wallet_demo("TestWallet1", w1_seed, "TestWallet2", w2_seed, cleanup=False)
