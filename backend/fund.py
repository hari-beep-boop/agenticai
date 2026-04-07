from algosdk.v2client import algod
from algosdk import mnemonic, account, transaction

# Your wallet
receiver = "ULEEDROACPRYKDC43GGXTTO3JYSVYTGSUY2DVSWJDPHZVHWEAPSKU6XI5E"

# 🔥 FUNDED TEST ACCOUNT (SAFE TESTNET)
sender_mnemonic = "furnace ladder wet girl swap thank else inside episode walk defense gasp clarify permit term power horse ordinary stamp hybrid monkey tree segment above lion"

sender_private_key = mnemonic.to_private_key(sender_mnemonic)
sender_address = account.address_from_private_key(sender_private_key)

# Connect to Algorand testnet
algod_client = algod.AlgodClient(
    "",
    "https://testnet-api.algonode.cloud"
)

params = algod_client.suggested_params()

txn = transaction.PaymentTxn(
    sender=sender_address,
    sp=params,
    receiver=receiver,
    amt=1000000  # 1 ALGO
)

signed_txn = txn.sign(sender_private_key)

txid = algod_client.send_transaction(signed_txn)

print("Transaction sent! TXID:", txid)