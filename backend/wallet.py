from algosdk import account, mnemonic

private_key, address = account.generate_account()

print("ADDRESS:", address)
print("MNEMONIC:", mnemonic.from_private_key(private_key))