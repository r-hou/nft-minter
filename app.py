import asyncio

from flask import Flask, render_template, request, Response
import json
import webview
import sys
import threading
import os
from datetime import timedelta
from web3 import Web3, AsyncHTTPProvider
from web3.eth import AsyncEth
import aiohttp
from web3.exceptions import ContractLogicError, ABIFunctionNotFound

app = Flask(__name__)

# 自动重载模板文件
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 设置静态文件缓存过期时间
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = timedelta(seconds=1)

web3 = None
async_web3 = None
wallets = []
CONTRACT_ABI = None
CHAIN_ID = None

@app.route('/')
def hello_world():
    print("in hello world")
    return render_template('index.html')

@app.route('/getviewfunctionvalue', methods=["GET"])
async def get_view_function_value():
    global CONTRACT_ABI
    monitor_function_name = request.args.get("monitor_function_name", None)
    monitor_contract_address = request.args.get("monitor_contract_address", None)
    try:
        nft_contract = web3.eth.contract(address=(Web3.toChecksumAddress(monitor_contract_address)),
                                         abi=CONTRACT_ABI)
        func = getattr(nft_contract.functions, monitor_function_name)
        func_value = func().call()
        return Response(json.dumps({"connected": True, "success": True, "func_value": func_value}), status=200,
                        mimetype='application/json')
    except ABIFunctionNotFound:
        print(f"function name:{monitor_function_name} is not found in the contract, please check it")
        return Response(json.dumps({"connected": True, "success": False, "reason": "abi not founded"}), status=201,
                        mimetype='application/json')
    except Exception as e:
        print("get_view_function_value error", e, e.__class__.__name__)
        return Response(json.dumps({"connected": True, "success": False, "reason": e.__class__.__name__}), status=201,
                        mimetype='application/json')


@app.route('/getviewfunctions', methods=["GET"])
async def get_view_functions():
    global CONTRACT_ABI
    etherscan_api_key = request.args.get("etherscan_api_key", None)
    monitor_contract_address = request.args.get("monitor_contract_address", None)
    print(etherscan_api_key, monitor_contract_address)
    url = f"https://api.etherscan.io/api?module=contract&action=getabi&address={monitor_contract_address}&apikey={etherscan_api_key}"
    try:
        async with aiohttp.ClientSession() as session:
            response = await session.get(url)
            result = await response.json()
            abi = json.loads(result['result'])
            CONTRACT_ABI = abi
            function_names = []
            for i in abi:
                statemutability = i.get("stateMutability", None)
                inputs = i.get("inputs")
                if statemutability == 'view' and not inputs:
                    function_names.append(i['name'])
            print(function_names)
            return Response(json.dumps({"connected": True, "success": True, "function_names": function_names}), status=200,
                            mimetype='application/json')
    except Exception as e:
        print("get abi error", e, e.__class__.__name__)
        return Response(json.dumps({"connected": True, "success": False, "reason": "合约未开源或者API Key错误"}), status=201,
                        mimetype='application/json')

@app.route('/testconnection', methods=["POST"])
def test_connection():
    global web3, async_web3, CHAIN_ID
    print(request.form.get("rpc", None))
    rpc_url = request.form.get("rpc", None)
    if rpc_url:
        web3 = Web3(Web3.HTTPProvider(rpc_url))
        async_web3 = Web3(AsyncHTTPProvider(rpc_url), modules={'eth': (AsyncEth,)}, middlewares=[])
        try:
            if web3.isConnected():
                CHAIN_ID = web3.eth.chain_id
                print("current chain id:", CHAIN_ID)
                return Response(json.dumps({"connected": True}), status=200, mimetype='application/json')
        except aiohttp.client_exceptions.InvalidURL:
            return Response(json.dumps({"connected": False}), status=201, mimetype='application/json')
    return Response(json.dumps({"connected": False}), status=201, mimetype='application/json')
    # return {"statusss": 200}


@app.route('/parsetxhash', methods=["POST"])
def parse_tx():
    global web3, async_web3
    tx_hash = request.form.get("tx_hash", None)
    print(request.form, web3, async_web3)
    if tx_hash:
        if web3 and async_web3:
            try:
                transaction = web3.eth.get_transaction(tx_hash)
                tx = {
                    "from": transaction['from'],
                    "to": transaction["to"],
                    "value": str(Web3.fromWei(int(transaction["value"]), 'ether')),
                    "input": str(transaction['input']),
                    "gas": str(transaction['gas']),
                    "max_fee": str(Web3.fromWei(transaction['maxFeePerGas'], "gwei")),
                    "max_priority_fee": str(Web3.fromWei(transaction['maxPriorityFeePerGas'], "gwei")),
                    "connected": True,
                    "success": True
                }
                return Response(json.dumps(tx), status=201, mimetype='application/json')
            except Exception as e:
                print(e, e.__class__.__name__)
                return Response(json.dumps({"connected": True, "success": False}), status=201,
                                mimetype='application/json')
        else:
            return Response(json.dumps({"connected": False}), status=201, mimetype='application/json')
    return Response(json.dumps({"connected": True, "success": False}), status=201, mimetype='application/json')


@app.route('/getgas', methods=["get"])
async def get_gas():
    headers = {
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Origin': 'https://www.blocknative.com',
        'Pragma': 'no-cache',
        'Referer': 'https://www.blocknative.com/gas-estimator',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36',
        'sec-ch-ua': '" Not A;Brand";v="99", "Chromium";v="100", "Google Chrome";v="100"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
    }
    count = 0
    while count < 5:
        try:
            async with aiohttp.ClientSession() as session:
                response = await  session.get('https://blocknative-api.herokuapp.com/data', headers=headers)
                result = await response.json()
                max_priority_fee = result['estimatedPrices'][2]['maxPriorityFeePerGas']
                max_fee = result['estimatedPrices'][2]['maxFeePerGas']
                # print(result)
                gas_fee = {"fast": {"max_priority_fee": result['estimatedPrices'][0]['maxPriorityFeePerGas'],
                                    "max_fee": result['estimatedPrices'][0]['maxFeePerGas']},
                           "medium": {"max_priority_fee": result['estimatedPrices'][2]['maxPriorityFeePerGas'],
                                      "max_fee": result['estimatedPrices'][2]['maxFeePerGas']},
                           "slow": {"max_priority_fee": result['estimatedPrices'][4]['maxPriorityFeePerGas'],
                                    "max_fee": result['estimatedPrices'][4]['maxFeePerGas']}}
                print(gas_fee)
                return Response(
                    json.dumps({"success": True, "gasfee": gas_fee}),
                    status=200, mimetype='application/json')
        except Exception as e:
            count += 1
            print("get gas fee error: ", e)
            await asyncio.sleep(1)
        return Response(
            json.dumps({"success": False, "gasfee": {"max_priority_fee": max_priority_fee, "max_fee": max_fee}}),
            status=201, mimetype='application/json')


async def send_tx(wallet, tx):
    global CHAIN_ID
    my_address = wallet['address']
    my_private_key = wallet['private_key']
    input_data = tx['input']
    from_address = tx['from']
    nonce = await async_web3.eth.get_transaction_count(my_address)
    if from_address[2::].lower() in input_data:
        input_data = input_data.replace(from_address[2::].lower(),
                                        my_address[2::].lower())

    tx = {
        'nonce': nonce,
        'to': Web3.toChecksumAddress(tx['to']),
        "from": Web3.toChecksumAddress(my_address),
        'value': Web3.toWei(tx['value'], 'ether'),
        'gas': int(tx['gas']),
        "maxPriorityFeePerGas": Web3.toWei(tx["maxPriorityFeePerGas"], 'gwei'),
        "maxFeePerGas": Web3.toWei(tx["maxFeePerGas"], 'gwei'),
        "data": input_data,
        "chainId": Web3.toHex(CHAIN_ID)
    }
    print("my_tx:", tx)
    signed_tx = web3.eth.account.sign_transaction(tx, my_private_key)
    print("signed_tx:", signed_tx)
    tx_hash = await async_web3.eth.send_raw_transaction(signed_tx.rawTransaction)
    print(my_address, "https://rinkeby.etherscan.io/tx/" + str(Web3.toHex(tx_hash)))
    return str(Web3.toHex(tx_hash))


@app.route('/sendtx', methods=["POST"])
async def sendtx():
    global wallets
    tasks = []
    tx = request.form.get("tx", "{}")
    print(tx)
    tx = json.loads(tx)
    print(tx)
    if not async_web3:
        return Response(json.dumps({"connected": False}), status=201, mimetype='application/json')
    if tx:
        for wallet in wallets:
            tasks.append(asyncio.create_task(send_tx(wallet, tx)))
        tx_hashes = await asyncio.gather(*tasks)
        urls = ["https://rinkeby.etherscan.io/tx/" + tx_hash for tx_hash in tx_hashes]
        return Response(json.dumps({"success": True, "connected": True, "urls": urls}), status=201,
                        mimetype='application/json')
    else:
        return Response(json.dumps({"success": True, "connected": True, "reason": "未获取到交易信息"}), status=201,
                        mimetype='application/json')


@app.route('/uploadwallets', methods=["POST"])
async def record_wallets():
    global wallets
    wallets = []
    wallets_str = request.form.get("wallets", None)
    try:
        wallets = json.loads(wallets_str)
        tasks = []
        for wallet in wallets:
            tasks.append(asyncio.create_task(balance_and_nonce_task(wallet)))
        wallets = await asyncio.gather(*tasks)
        # wallets = await get_balance_and_nonce(wallets)
        print(len(wallets), wallets)
        return Response(json.dumps({"success": True, "wallets": wallets}), status=200, mimetype='application/json')
    except json.JSONDecodeError:
        return Response(json.dumps({"success": False, "reason": "格式错误"}), status=201, mimetype='application/json')
    except Exception as e:
        return Response(json.dumps({"success": False, "reason": e}), status=201, mimetype='application/json')


async def balance_and_nonce_task(wallet):
    address = wallet['address']
    nonce = await async_web3.eth.get_transaction_count(address)
    balance = await async_web3.eth.get_balance(address)
    wallet['nonce'] = nonce
    wallet['balance'] = str(round(Web3.fromWei(balance, "ether"), 5))
    return wallet


async def get_balance_and_nonce(wallets):
    tasks = []
    for wallet in wallets:
        tasks.append(asyncio.create_task(balance_and_nonce_task(wallet)))
    wallets = await asyncio.gather(*tasks)
    # print(wallets)
    return wallets


def start_server():
    app.run(host='0.0.0.0', port=1080)




if __name__ == '__main__':
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    print(os.path.dirname(os.path.realpath(sys.argv[0])))
    # t.join()
    window = webview.create_window("NFT Minter", width=1400, height=900, url="http://localhost:1080/", resizable=False,
                                   x=0, y=0)
    webview.start()
    sys.exit()
