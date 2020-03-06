import time
import sys
import pprint

from web3 import HTTPProvider
from web3 import Web3

from pymaker import Address, Wad, Contract
from pymaker.approval import directly
from pyexchange.airswap_v2 import AirswapContract, AirswapApi
from pymaker.token import DSToken

# https://airswap-maker.now.sh

def test_all_trades():

    web3 = Web3(HTTPProvider(endpoint_uri=sys.argv[1]))

    airswap_contract = AirswapContract(web3, Address('0x2e7373D70732E0F37F4166D8FD9dBC89DD5BC476'), 500)

    pair = {
        Address('0x0000000000000000000000000000000000000000'): True,
        Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'): True
    }

    eth_dai_trades = airswap_contract.get_all_trades(pair, 1)

    print("airswap all trades -->")
    pprint.pprint(eth_dai_trades)


def test_our_trades():

    web3 = Web3(HTTPProvider(endpoint_uri=sys.argv[1]))
    web3.eth.defaultAccount = sys.argv[2]
    airswap_contract = AirswapContract(web3, Address('0x2e7373D70732E0F37F4166D8FD9dBC89DD5BC476'), 500)

    pair = {
        Address('0x0000000000000000000000000000000000000000'): True,
        Address('0x89d24a6b4ccb1b6faa2625fe562bdd9a23260359'): True
    }

    eth_dai_trades = airswap_contract.get_trades(pair, 1)

    print("airswap our trades -->")
    pprint.pprint(eth_dai_trades)

# test_all_trades()
# test_our_trades()

airswap = AirswapApi('http://localhost:3000', 9.5)

print(airswap.set_intents())