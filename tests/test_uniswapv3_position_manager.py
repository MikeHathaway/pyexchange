# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2021 MikeHathaway
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import time
import logging
from typing import List

import pkg_resources
import pytest
import unittest

from fxpmath import Fxp
from enum import Enum
from web3 import Web3, HTTPProvider

from pyexchange.uniswapv3 import PositionManager, SwapRouter
from pyexchange.uniswapv3_constants import FEES, TICK_SPACING, TRADE_TYPE, MIN_TICK
from pyexchange.uniswapv3_calldata_params import BurnParams, CollectParams, DecreaseLiquidityParams, MintParams, \
    ExactOutputSingleParams, ExactInputSingleParams
from pyexchange.uniswapv3_entities import Pool, Position, Route, Trade, CurrencyAmount, Fraction, PriceFraction
from pyexchange.uniswapv3_math import encodeSqrtRatioX96, get_sqrt_ratio_at_tick, get_tick_at_sqrt_ratio, Tick
from pymaker import Address, Contract, Receipt, Transact
from pymaker.keys import register_keys, register_private_key
from pymaker.gas import FixedGasPrice
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.token import DSToken, ERC20Token


# TODO: update to use snake case
# TODO: generalize / split out tests for SwapRouter?
class TestUniswapV3PositionManager(Contract):

    """ Deployment docs available here: https://github.com/Uniswap/uniswap-v3-periphery/blob/main/deploys.md """

    UniswapV3Factory_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV3Factory.abi')['abi']
    UniswapV3Factory_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV3Factory.bin')
    NFTDescriptor_abi = Contract._load_abi(__name__, '../pyexchange/abi/NFTDescriptor.abi')['abi']
    NFTDescriptor_bin = Contract._load_bin(__name__, '../pyexchange/abi/NFTDescriptor.bin')
    weth_abi = Contract._load_abi(__name__, '../pyexchange/abi/WETH.abi')
    weth_bin = Contract._load_bin(__name__, '../pyexchange/abi/WETH.bin')
    NonfungiblePositionManager_abi = Contract._load_abi(__name__, '../pyexchange/abi/NonfungiblePositionManager.abi')['abi']
    NonfungiblePositionManager_bin = Contract._load_bin(__name__, '../pyexchange/abi/NonfungiblePositionManager.bin')
    SwapRouter_abi = Contract._load_abi(__name__, '../pyexchange/abi/SwapRouter.abi')['abi']
    SwapRouter_bin = Contract._load_bin(__name__, '../pyexchange/abi/SwapRouter.bin')
    UniswapV3TickLens_abi = Contract._load_abi(__name__, '../pyexchange/abi/UniswapV3TickLens.abi')['abi']
    UniswapV3TickLens_bin = Contract._load_bin(__name__, '../pyexchange/abi/UniswapV3TickLens.bin')

    def setup_method(self):
        time.sleep(10)
        # Use Ganache docker container
        self.web3 = Web3(HTTPProvider("http://0.0.0.0:8555"))
        self.web3.eth.defaultAccount = Web3.toChecksumAddress("0x9596C16D7bF9323265C2F2E22f43e6c80eB3d943")
        register_private_key(self.web3, "0x91cf2cc3671a365fcbf38010ff97ee31a5b7e674842663c56769e41600696ead")

        self.our_address = Address(self.web3.eth.defaultAccount)

        # constructor args for nonfungiblePositionManager
        self.factory_address: Address = self._deploy(self.web3, self.UniswapV3Factory_abi, self.UniswapV3Factory_bin, [])
        self.weth_address: Address = self._deploy(self.web3, self.weth_abi, self.weth_bin, [])
        self.token_descriptor_address: Address = self._deploy(self.web3, self.NFTDescriptor_abi, self.NFTDescriptor_bin, [])

        self.nonfungiblePositionManager_address = self._deploy(self.web3, self.NonfungiblePositionManager_abi, self.NonfungiblePositionManager_bin, [self.factory_address.address, self.weth_address.address, self.token_descriptor_address.address])

        self.tick_lens_address = self._deploy(self.web3, self.UniswapV3TickLens_abi, self.UniswapV3TickLens_bin, [])
        self.position_manager = PositionManager(self.web3, self.nonfungiblePositionManager_address, self.factory_address, self.tick_lens_address)

        # TODO: move SwapRouter to conftest fixtures
        self.swap_router_address = self._deploy(self.web3, self.SwapRouter_abi, self.SwapRouter_bin, [self.factory_address.address, self.weth_address.address])
        self.swap_router = SwapRouter(self.web3, self.swap_router_address)

        self.ds_dai = DSToken.deploy(self.web3, 'DAI')
        self.ds_usdc = DSToken.deploy(self.web3, 'USDC')
        self.token_dai = Token("DAI", self.ds_dai.address, 18)
        self.token_usdc = Token("USDC", self.ds_usdc.address, 6)

        receipt = self.ds_dai.mint(Wad(10)).transact()
        print(self.ds_dai.address, self.ds_usdc.address, receipt.successful)
        ## Useful for debugging failing transactions
        logger = logging.getLogger('eth')
        logger.setLevel(8)
        # Transact.gas_estimate_for_bad_txs = 210000

    # TODO: add support for approving for swap router
    def mint_tokens(self, token_0_mint_amount: Wad, token_1_mint_amount: Wad):
        self.ds_dai.mint(token_0_mint_amount).transact(from_address=self.our_address)
        self.ds_usdc.mint(self.token_usdc.unnormalize_amount(token_1_mint_amount)).transact(from_address=self.our_address)
        self.position_manager.approve(self.token_dai)
        self.position_manager.approve(self.token_usdc)
        self.swap_router.approve(self.token_dai)
        self.swap_router.approve(self.token_usdc)

    # TODO: retrieve log events from create pool event
    # TODO: is sqrt_price_x96 from mint amounts nedded for pool creation, or can 0 be used instead?
    def create_and_initialize_pool(self, starting_sqrt_price_x96: int) -> Pool:

        # TODO: best way to do this?
        token_0, token_1 = self.position_manager._set_address_order(self.token_dai, self.token_usdc)
        self.position_manager.create_pool(token_0, token_1, FEES.LOW.value, starting_sqrt_price_x96).transact()

        liquidity = 0 # liquidity is 0 upon initalization
        # # tick_current = get_tick_at_sqrt_ratio(starting_square_root_ratio_x96)
        # TODO: offset tick_current based upon expected pool ticks used in test
        tick_current = 0

        # TODO: dynamically retrieve token ordering based on comparison operator
        pool = Pool(
            token_0,
            token_1,
            FEES.LOW.value,
            starting_sqrt_price_x96,
            liquidity,
            tick_current,
            []
        )
        return pool

    def get_starting_sqrt_ratio(self, amount_0, amount_1) -> int:
        return encodeSqrtRatioX96(amount_1, amount_0)

    def generate_mint_params(self, pool: Pool) -> MintParams:
        amount_0 = 100 * 10 ** 6
        amount_1 = 100 * 10 ** 18
        self.mint_tokens(Wad.from_number(amount_0), Wad.from_number(amount_1))

        # starting_square_root_ratio_x96 = self.get_starting_sqrt_ratio(amount_0, amount_1)
        # liquidity = 0 # liquidity is 0 upon initalization
        # # TODO: if using formula to establish starting sqrt_ratio need to corresponding offest tick lower and higher
        # # tick_current = get_tick_at_sqrt_ratio(starting_square_root_ratio_x96)
        # tick_current = 0
        #
        # pool = Pool(
        #     self.token_dai,
        #     self.token_usdc,
        #     FEES.LOW.value,
        #     starting_square_root_ratio_x96,
        #     liquidity,
        #     tick_current,
        #     []
        # )

        deadline = int(time.time()) + 1000
        position = Position(pool, -10, 10, 1)
        slippage_tolerance = Fraction(20, 100)
        recipient = self.our_address

        mint_params = MintParams(self.web3, position, recipient, slippage_tolerance, deadline)
        return mint_params

    # def test_create_and_initalize_pool(self):
    #     new_pool_address = self.create_and_initialize_pool()
    #
    #     assert isinstance(new_pool_address, Address)
    #
    # def test_generate_mint_params(self):
    #     mint_params = self.generate_mint_params()
    #     assert isinstance(mint_params, MintParams)

    def get_ticks(self, pool: Pool, current_tick: int) -> List:
        assert isinstance(pool, Pool)

        pool_address = self.position_manager.get_pool_address(pool.token_0, pool.token_1, pool.fee)
        pool_contract = self.position_manager.get_pool_contract(pool_address)

        # return self.position_manager.get_pool_ticks(pool_contract, current_tick)

    # TODO: tie newly minted underlying assets to minted amount
    def xtest_mint(self):
        amount_0 = 100 * 10 ** 6
        amount_1 = 100 * 10 ** 18
        # create and intialize pool
        # pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(amount_0, amount_1))
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        mint_params = self.generate_mint_params(pool)

        gas_price = FixedGasPrice(gas_price=20000000000000000)
        gas_limit = 6021975
        mint_receipt = self.position_manager.mint(mint_params).transact(gas_price=gas_price)
        print(mint_receipt)
        assert mint_receipt is not None and mint_receipt.successful

    def test_get_position_from_id(self):
        # create and intialize pool
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        print("before mint ticks", self.get_ticks(pool, pool.tick_current))
        mint_params = self.generate_mint_params(pool)

        mint_receipt = self.position_manager.mint(mint_params).transact()
        assert mint_receipt is not None and mint_receipt.successful

        print("after mint ticks", self.get_ticks(pool, 0))

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id

        position = self.position_manager.positions(token_id)

        assert isinstance(position, Position)


    # https://github.com/Uniswap/uniswap-v3-periphery/blob/main/contracts/base/Multicall.sol
    # def test_multicall_mint(self):
    #     amount_0 = 100 * 10 ** 6
    #     amount_1 = 100 * 10 ** 18
    #     # create and intialize pool
    #     pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(amount_0, amount_1))
    #     # # create and intialize pool
    #
    #     multicall_mint_params = self.generate_mint_params(pool)
    #     multicall_mint_receipt = self.position_manager.multicall([multicall_mint_params.calldata.as_bytes()]).transact()
    #     assert multicall_mint_receipt is not None
    #
    #     # check token balance
    #     assert self.position_manager.balance_of()

    # def test_position_manager_deployment(self):
    #     test_call = self.nonfungiblePositionManager_contract.functions.DOMAIN_SEPARATOR().call()
    #     print(test_call)
    #     assert test_call is True

    def test_burn(self):
        # create and intialize pool
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id
        liquidity = mint_receipt.result[0].liquidity
        amount_0 = mint_receipt.result[0].amount_0
        amount_1 = mint_receipt.result[0].amount_1

        # decrease liquidity - remove all minted liquidity
        decrease_liquidity_params = DecreaseLiquidityParams(self.web3, token_id, liquidity, amount_0 - 1, amount_1 - 1, None)
        decrease_liquidity_receipt = self.position_manager.decrease_liquidity(decrease_liquidity_params).transact()

        assert decrease_liquidity_receipt is not None and decrease_liquidity_receipt.successful

        # burn previously created position
        burn_params = BurnParams(self.web3, token_id)
        burn_receipt = self.position_manager.burn(burn_params).transact()

        assert burn_receipt is not None and burn_receipt.successful

    # multicall(decreaseLiquidity, burn)
    def xtest_multicall_burn(self):
        # create and intialize pool
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id
        liquidity = mint_receipt.result[0].liquidity
        amount_0 = mint_receipt.result[0].amount_0
        amount_1 = mint_receipt.result[0].amount_1

        # decrease liquidity - remove all minted liquidity
        decrease_liquidity_params = DecreaseLiquidityParams(self.web3, token_id, liquidity, amount_0 - 1, amount_1 - 1, None)
        # burn position following liquidity removal
        burn_params = BurnParams(self.web3, token_id)

        multicall_calldata = [
            decrease_liquidity_params.calldata.as_bytes(),
            burn_params.calldata.as_bytes()
        ]
        print("burn multicall calldata", decrease_liquidity_params.calldata, burn_params.calldata)
        multicall_receipt = self.position_manager.multicall(multicall_calldata).transact()

        assert multicall_receipt is not None and multicall_receipt.successful

    # TODO: add support for swaps to generate fees
    def xtest_collect_exact_output_swap(self):
        # create and intialize pool
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id

        # TODO: need to get a new pool entity that reflects the new ticks[] reflecting the added liquidity
        minted_position = self.position_manager.positions(token_id)

        # execute swaps against the pool to generate fees
        amount_out = 25
        slippage_tolerance = Fraction(20, 100) # equivalent to 0.2
        recipient = self.our_address
        # recipient = Address("0x253De0f274677334eC814Fc99794C3F228de6fF3")
        deadline = int(time.time() + 10000)
        price_limit = 0

        # TODO: figure out why self.token_usdc != pool.token_usdc
        # route = Route([minted_position.pool], self.token_usdc, self.token_dai)
        # trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(self.token_dai, amount_out), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)
        route = Route([minted_position.pool], minted_position.pool.token_0, minted_position.pool.token_1)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(minted_position.pool.token_1, amount_out), TRADE_TYPE.EXACT_OUTPUT_SINGLE.value)

        # TODO: fix this calculation
        # amount_in = trade.maximum_amount_in(slippage_tolerance).quotient()

        amount_in = trade.input_amount.quotient()

        exact_output_single_params = ExactOutputSingleParams(self.web3, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_out, amount_in, price_limit)
        swap = self.swap_router.swap_exact_output_single(exact_output_single_params).transact()
        assert swap is not None and swap.successful

        position_amount_0 = self.position_manager.get_position_info(token_id)[10]
        position_amount_1 = self.position_manager.get_position_info(token_id)[11]

        # collect fees from position
        collect_params = CollectParams(self.web3, token_id, self.our_address, position_amount_0, position_amount_1)
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

    def test_collect_exact_input_swap(self):
        # create and intialize pool
        print(Wad.from_number(24.485), Wad.from_number(24.485).value)
        pool = self.create_and_initialize_pool(self.get_starting_sqrt_ratio(1, 1))

        # mint new position
        mint_params = self.generate_mint_params(pool)
        mint_receipt = self.position_manager.mint(mint_params).transact()

        # get the token_id out of the mint transaction receipt
        token_id = mint_receipt.result[0].token_id

        # TODO: need to get a new pool entity that reflects the new ticks[] reflecting the added liquidity
        minted_position = self.position_manager.positions(token_id)

        amount_in = 25
        recipient = self.our_address
        deadline = int(time.time() + 10000)
        price_limit = 0

        route = Route([minted_position.pool], minted_position.pool.token_0, minted_position.pool.token_1)
        trade = Trade.from_route(route, CurrencyAmount.from_raw_amount(minted_position.pool.token_0, amount_in),
                                 TRADE_TYPE.EXACT_INPUT_SINGLE.value)

        amount_out = trade.output_amount.quotient()
        exact_input_single_params = ExactInputSingleParams(self.web3, trade.route.token_path[0], trade.route.token_path[1], trade.route.pools[0].fee, recipient, deadline, amount_in, amount_out, price_limit)

        swap = self.swap_router.swap_exact_input_single(exact_input_single_params).transact()
        assert swap is not None and swap.successful

        position_amount_0 = self.position_manager.get_position_info(token_id)[10]
        position_amount_1 = self.position_manager.get_position_info(token_id)[11]

        # collect fees from position
        collect_params = CollectParams(self.web3, token_id, self.our_address, position_amount_0, position_amount_1)
        collect_receipt = self.position_manager.collect(collect_params).transact()

        assert collect_receipt is not None and collect_receipt.successful

    # TODO: multicall[collect, decreaseLiquidity, burn]
    def test_collect_and_burn(self):
        pass

    def test_positions(self):
        pass