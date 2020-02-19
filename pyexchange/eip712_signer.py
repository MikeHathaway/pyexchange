from eth_utils import keccak
from eth_abi import encode_abi
from bitcoin import ecdsa_raw_sign
from web3 import Web3

class Signer:
    """
    Define a EIP-712 compliant message signer

    Based on documentation here: <https://docs.airswap.io/system/orders-and-signatures#creating-orders>
    """

    def __init__(self, web3: Web3, address: str, private_key: str):
        assert(isinstance(web3, Web3))       
        assert(isinstance(address, str))
        assert(isinstance(private_key, str))

        self.web3 = web3
        self.wallet_address = address
        self.private_key = private_key

    def sign_order(self, order) -> dict: 
        SWAP_VERSION = "2"
        SWAP_DOMAIN = "SWAP
        ERC_20_INTERFACE_ID = bytes.fromhex("36372b07")

        # TODO:
        # Address for Rinkeby. Need to add code to retrieve address based upon environment
        SWAP_CONTRACT_ADDRESS = "0x2e7373D70732E0F37F4166D8FD9dBC89DD5BC476"

        WALLET_ADDRESS = self.wallet_address
        PRIVATE_KEY = self.private_key

        SWAP_TYPES = {
            "party": b"Party(bytes4 kind,address wallet,address token,uint256 amount,uint256 id)",
            "order": b"Order(uint256 nonce,uint256 expiry,Party signer,Party sender,Party affiliate)",
            "eip712": b"EIP712Domain(string name,string version,address verifyingContract)",
        }

        SWAP_TYPE_HASHES = {
            "party": keccak(SWAP_TYPES["party"]),
            "order": keccak(SWAP_TYPES["order"] + SWAP_TYPES["party"]),
            "eip712": keccak(SWAP_TYPES["eip712"]),
        }

        DOMAIN_SEPARATOR = keccak(
            encode_abi(
                ["bytes32", "bytes32", "bytes32", "address"],
                [
                    SWAP_TYPE_HASHES["eip712"],
                    keccak(SWAP_DOMAIN.encode()),
                    keccak(SWAP_VERSION.encode()),
                    SWAP_CONTRACT_ADDRESS,
                ],
            )
        )

        hashed_signer = keccak(
            encode_abi(
                ["bytes32", "bytes4", "address", "address", "uint256", "uint256"],
                [
                    SWAP_TYPE_HASHES["party"],
                    ERC_20_INTERFACE_ID,
                    order["signerWallet"],
                    order["signerToken"],
                    int(order["signerAmount"]),
                    int(order["signerId"]),
                ],
            )
        )

        hashed_sender = keccak(
            encode_abi(
                ["bytes32", "bytes4", "address", "address", "uint256", "uint256"],
                [
                    SWAP_TYPE_HASHES["party"],
                    ERC_20_INTERFACE_ID,
                    order["senderWallet"],
                    order["senderToken"],
                    int(order["senderAmount"]),
                    int(order["senderId"]),
                ],
            )
        )

        hashed_affiliate = keccak(
            encode_abi(
                ["bytes32",  "bytes4", "address", "address", "uint256", "uint256"],
                [
                    SWAP_TYPE_HASHES["party"],
                    ERC_20_INTERFACE_ID,
                    "0x0000000000000000000000000000000000000000",
                    "0x0000000000000000000000000000000000000000",
                    0,
                    0,
                ],
            )
        )

        hashed_order = keccak(
            encode_abi(
                ["bytes32", "uint256", "uint256", "bytes32", "bytes32", "bytes32"],
                [
                    SWAP_TYPE_HASHES["order"],
                    int(order["nonce"]),
                    int(order["expiry"]),
                    hashed_signer,
                    hashed_sender,
                    hashed_affiliate,
                ],
            )
        )

        encoded_order = keccak(b"\x19Ethereum Signed Message:\n32" + keccak(b"\x19\x01" + DOMAIN_SEPARATOR + hashed_order))

        V, R, S = ecdsa_raw_sign(encoded_order, PRIVATE_KEY)

        v = V
        r = self.web3.toHex(R)
        s = self.web3.toHex(S)

        # The bitcoin.ecdsa_raw_sign method we are using may return r & s values that are under 66 bytes, so check for
        # that and pad with '0' if necessary to align with bytes32 types
        if len(s) < 66:
        diff = 66 - len(s)
        s = "0x" + "0" * diff + s[2:]

        if len(r) < 66:
        diff = 66 - len(r)
        r = "0x" + "0" * diff + r[2:]

        # version is 0x45 for personalSign
        signed_order = {
            "version": "0x45",
            "signatory": WALLET_ADDRESS,
            "validator": SWAP_CONTRACT_ADDRESS,
            "v": v,
            "r": r,
            "s": s
        }

        return signed_order