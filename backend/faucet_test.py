import requests

ADDRESS = "U2MLMIKY5VPX76RB7Q3QLYSIJP4ZDPYYZAPOUAJGPIET34U3VSX30B4NQ"

url = "https://bank.testnet.algorand.network/"

params = {
    "account": ADDRESS
}

res = requests.get(url, params=params)

print(res.status_code)
print(res.text)