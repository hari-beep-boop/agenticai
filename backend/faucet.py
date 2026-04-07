import requests

ADDRESS = "U2MLMIKY5VPX76RB7Q3QLYSIJP4ZDPYYZAPOUAJGPIET34U3VSX30B4NQ"

url = "https://dispenser.testnet.aws.algodev.network/v2/dispense"

data = {
    "receiver": ADDRESS,
    "amount": 1000000   # 1 ALGO
}

res = requests.post(url, json=data)

print("Status:", res.status_code)
print("Response:", res.text)