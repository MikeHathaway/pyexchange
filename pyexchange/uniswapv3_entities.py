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

import time

from fxpmath import Fxp
from typing import List, Optional, Tuple
from web3 import Web3

from pyexchange.uniswapv3_math import get_sqrt_ratio_at_tick, SqrtPriceMath
from pymaker import Address, Calldata, Invocation
from pymaker.model import Token
from pymaker.numeric import Wad
from pymaker.utils import bytes_to_int, bytes_to_hexstring


class PriceFraction:

    def __init__(self, base_token: Token, quote_token: Token, denominator: int, numerator: int):
        assert isinstance(base_token, Token)
        assert isinstance(quote_token, Token)

        self.base_token = base_token
        self.quote_token = quote_token
        self.numerator = numerator # quote token
        self.denominator = denominator # base token
    
    def get_float_price(self) -> float:
        return float(numerator / denominator)


class Pool:
    """ https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/entities/pool.ts """
    def __init__(self, token_0: Token, token_1: Token, fee: int, square_root_ratio_x96: Fxp, liquidity: Wad, tick_current: int, ticks: List):
        assert isinstance(token_0, Token)
        assert isinstance(token_1, Token)
        assert isinstance(fee, int)
        assert isinstance(square_root_ratio_x96, Fxp)
        assert isinstance(liquidity, Wad)
        assert isinstance(tick_current, int)
        assert isinstance(ticks, List)

        self.token_0 = token_0
        self.token_1 = token_1
        self.fee = fee
        self.square_root_ratio_x96 = square_root_ratio_x96
        self.liquidity = liquidity
        self.tick_current = tick_current
        self.ticks = ticks
        self.token_0_price = get_token_1_price()
        self.token_1_price = get_token_1_price()

    def get_token_0_price(self) -> PriceFraction:
        # base, quote
        return PriceFraction(self.token_0, self.token_1, Q192, (self.square_root_ratio_x96 * self.square_root_ratio_x96))

    # TODO: verify proper return type here -- wad desired?
    def get_token_1_price(self) -> PriceFraction:
        return PriceFraction(self.token_0, self.token_1, (self.square_root_ratio_x96 * self.square_root_ratio_x96), Q192)


class Position:

    # TODO: check the integer precision of liquidity
    def __init__(self, pool: Pool, tick_lower: int, tick_upper: int, liquidity: int):
        """ https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/entities/position.ts """
        assert isinstance(pool, Pool)
        assert isinstance(tick_lower, int)
        assert isinstance(tick_upper, int)
        assert isinstance(liquidity, int)

        self.pool = pool
        self.tick_lower = tick_lower
        self.tick_upper = tick_upper
        self.liquidity = liquidity

        self.token_0_amount = None
        self.token_1_amount = None
        self.mint_amounts: Tuple = None # Tuple

    def get_token_0_price_lower(self):
        """ return the token_0 price at the lower tick """
        pass

    def get_token_0_price_upper(self):
        """ return the token_0 price at the upper tick """
        pass

    def amount_in_token_0(self) -> Wad:
        """ Returns the amount of token0 that this position's liquidity could be burned for at the current pool price """
        if self.token_0_amount == None:
            if self.pool.tick_current < self.tick_lower:
                self.token_0_amount = SqrtPriceMath.get_amount_0_delta(
                    get_sqrt_ratio_at_tick(self.tick_lower),
                    get_sqrt_ratio_at_tick(self.tick_upper),
                    self.liquidity,
                    False
                )
            elif self.pool.tick_current < self.tick_upper:
                self.token_0_amount = SqrtPriceMath.get_amount_0_delta(
                    get_sqrt_ratio_at_tick(self.tick_lower),
                    get_sqrt_ratio_at_tick(self.tick_upper),
                    self.liquidity,
                    False
                )
            else:
                self.token_0_amount = Wad.from_number(0)

    def amount_in_token_1(self) -> Wad:
        """ """
        pass

    def max_liquidity_for_amounts(self, pool: Pool, sqrtRatioAX96, sqrtRatioBX96, amount_0, amount_1, use_full_precision):
        assert (isinstance(pool, Pool))

        sqrtRatioAX96, sqrtRatioBX96 = SqrtPriceMath.invert_ratio_if_needed(sqrtRatioAX96, sqrtRatioBX96)

        max_liquidity_for_amount_0 = 

    # TODO: finish implementing
    @staticmethod
    def from_amounts(pool: Pool, tick_lower: int, tick_upper: int, amount_0, amount_1, use_full_precision):
        """ """
        assert (isinstance(pool, Pool))
        assert (isinstance(tick_lower, int))
        assert (isinstance(tick_upper, int))

        sqrtRatioAX96 = get_sqrt_ratio_at_tick(tick_lower)
        sqrtRatioBX96 = get_sqrt_ratio_at_tick(tick_upper)

        return Position(pool, tick_lower, tick_upper, self.max_liquidity_for_amounts(
            pool.square_root_ratio_x96,
            sqrtRatioAX96,
            sqrtRatioBX96,
            amount_0,
            amount_1,
            useFullPrecision
        ))

    def mint_amounts(self) -> Tuple:
        # TODO: convert 0 to ZERO Fxp constant?
        if self._mint_amount == None:
            if self.pool.tick_current < self.tick_lower:
                return {
                    "amount0": SqrtPriceMath.get_amount_0_delta(
                        get_sqrt_ratio_at_tick(self.tick_lower),
                        get_sqrt_ratio_at_tick(self.tick_upper),
                        self.liquidity,
                        True
                    ),
                    "amount1": 0
                }
            elif self.pool.tick_current < self.tick_upper:
                return {
                    "amount0": SqrtPriceMath.get_amount_0_delta(),
                    "amount1": SqrtPriceMath.get_amount_1_delta()
                }
            else:
                return {
                    "amount0": 0,
                    "amount1": SqrtPriceMath.get_amount_1_delta()
                }
        else:
            return self._mint_amount

    # TODO: determine if conversion to fractions is necessary
    def _ratios_after_slippage(self, slippage_tolerance: float) -> Tuple:
        assert isinstance(slippage_tolerance, float)
        assert (slippage_tolerance < 1 and slippage_tolerance > 0)

        price_lower = self.pool.get_token_0_price().get_float_price() * (1 - slippage_tolerance)
        price_upper = self.pool.get_token_0_price().get_float_price() * (1 + slippage_tolerance)

        sqrtRatioX96Lower = encodeSqrtRatioX96(price_lower.numerator, price_lower.denominator)

        if sqrtRatioX96Lower < MIN_SQRT_RATIO:
            sqrtRatioX96Lower = MIN_SQRT_RATIO + 1
        
        sqrtRatioX96Upper = encodeSqrtRatioX96(price_upper.numerator, price_upper.denominator)

        if sqrtRatioX96Upper > MAX_SQRT_RATIO:
            sqrtRatioX96Upper = MAX_SQRT_RATIO - 1

        return (sqrtRatioX96Lower, sqrtRatioX96Upper)

    # TODO: finish implementing
    def mint_amounts_with_slippage(self, slippage_tolerance: float) -> Tuple:
        """ Returns amount0; amount1 to mint after accounting for the given slippage_tolerance """

        sqrtRatioX96Lower, sqrtRatioX96Upper = self._ratios_after_slippage(slippage_tolerance)

    # TODO: is this still necessary?
    def as_NFT(self):
        """ return erc-721 representation of position"""
        pass


class Params:

    def convert_to_bytes(self, calldata: Calldata) -> bytes:
        """ convert calldata to byte array """
        return calldata.as_bytes()

    def encode_calldata(self, web3: Web3, fn_signature: str, arguments: List) -> Calldata:
        """ encode inputted contract and methods with call arguments as pymaker.Calldata """
        assert isinstance(web3, Web3)
        assert isinstance(fn_signature, str)
        assert isinstance(arguments, List)

        # TODO: add Invocation support
        return Calldata.from_signature(web3, fn_signature, arguments)

    # TODO: remove method if unnecessary?
    # TODO: figure out how to handle multicall calldata
    @staticmethod
    def prepare_invocation(contract_address: Address, calldata: Calldata):
        return Invocation(contract_address, calldata)

    def _deadline(self) -> int:
        """Get a predefined deadline."""
        return int(time.time()) + 1000
    
    # TODO: simplify conversion path from int -> hexstring
    # TODO: call self.convert_to_bytes?
    def _to_hex(self, num: int) -> str:
        return bytes_to_hexstring(int_to_bytes32(num))



# TODO: construct callback to be passed to mint()
## https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.ts#L162
## https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.ts#L44    
class MintParams(Params):

    # https://github.com/Uniswap/uniswap-v3-sdk/blob/main/src/nonfungiblePositionManager.test.ts
    def __init__(self, web3: Web3, position: Position, recipient: Address, slippage_tolerance: float, deadline: int):
        assert(isinstance(web3, Web3))
        assert(isinstance(position, Position))
        assert(isinstance(recipient, Address))
        assert(isinstance(slippage_tolerance, float))
        assert(isinstance(deadline, int) or (deadline is None))

        self.position = position
        self.recipient = recipient
        self.slippage_tolerance = slippage_tolerance

        self.deadline = deadline if deadline is not None else self._deadline()

        # TODO: figure out most effective way to calculate amount0desired, amount1Desired

        amount_0, amount_1 = self.position.mint_amounts()

        calldata_args = [{
            "token0": position.pool.token_0.address,
            "token1": position.pool.token_1.address,
            "fee": position.pool.fee,
            "tickLower": position.tick_lower,
            "tickUpper": position.tick_upper,
            "amount0Desired": self._to_hex(amount_0),
            "amount1Desired": self._to_hex(amount_1),
            "amount0Min": 0,
            "amount1Min": 0,
            "recipient": self.recipient,
            "deadline": self.deadline
        }]

        # TODO: figure out how to handle struct typing
        method = "mint(struct INonfungiblePositionManager.MintParams)"
        # TODO: add fn signature types
        # TODO: figure out how to pass through web3
        self.encode_calldata = self.encode_calldata(web3, method, calldata_args)

    @staticmethod
    def calculate_mint_amounts(self, liquidity: Wad) -> Tuple[Wad, Wad]:
        """ Return a tuple of amount0, amount1 to be minted for a given position to match a desired amount of liquidity """
        assert(isinstance(slippage, int))

        amount0Desired = Wad.from_number(0)

        return {
            "amount0Desired": amount0Desired
        }


class CollectParams(Params):

    # TODO: pass through the contract, and uniswap_pool
    def __init__(self, uniswap_pool: Pool, recipient: Address, tick_lower: int, tick_upper: int, amounts: dict) -> None:
        assert(isinstance(uniswap_pool, Pool))

        self.params = {}

        self.params.amount1Min = amounts["amount1Min"]
        self.deadline = self._deadline()
