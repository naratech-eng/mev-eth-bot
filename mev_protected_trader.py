from web3 import Web3
from eth_account.account import Account
from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address
import json
import os
import time
from decimal import Decimal
from typing import Tuple, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
UNISWAP_V2_ROUTER = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
WETH_ADDRESS = Web3.to_checksum_address(os.getenv('WETH_ADDRESS', '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'))

class MEVProtectedBuyer:
    def __init__(self):
        # Load credentials
        self.private_key = os.getenv('ETHEREUM_PRIVATE_KEY')
        self.node_url = os.getenv('ETHEREUM_NODE_URL')
        self.wallet_address = Web3.to_checksum_address(os.getenv('WALLET_ADDRESS'))
        self.default_slippage = float(os.getenv('DEFAULT_SLIPPAGE', '0.5'))
        self.gas_multiplier = float(os.getenv('GAS_MULTIPLIER', '1.1'))
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.node_url))
        self.account: LocalAccount = Account.from_key(self.private_key)
        
        # Load contracts
        self.router = self.w3.eth.contract(
            address=Web3.to_checksum_address(UNISWAP_V2_ROUTER),
            abi=self.load_abi('UniswapV2Router02.json')
        )
        
        # Transaction settings
        self.min_eth_balance = Web3.to_wei(0.01, 'ether')  # Keep 0.01 ETH for future gas
        self.max_gas_price = Web3.to_wei(300, 'gwei')  # Maximum gas price willing to pay

    def validate_address(self, address: str) -> str:
        """Validate and convert address to checksum format"""
        try:
            # Remove any whitespace
            address = address.strip()
            # Convert to checksum address
            return Web3.to_checksum_address(address)
        except Exception as e:
            raise ValueError(f"Invalid Ethereum address: {address}")

    def load_abi(self, filename):
        """Load ABI from file"""
        with open(f'abis/{filename}', 'r') as f:
            return json.load(f)

    def get_token_contract(self, token_address: str):
        """Get token contract instance"""
        token_address = self.validate_address(token_address)
        return self.w3.eth.contract(
            address=token_address,
            abi=self.load_abi('ERC20.json')
        )

    def get_eth_balance(self) -> int:
        """Get ETH balance of wallet"""
        return self.w3.eth.get_balance(self.wallet_address)

    def calculate_max_spend(self, gas_price: int) -> int:
        """Calculate maximum amount we can spend while keeping minimum ETH for gas"""
        balance = self.w3.eth.get_balance(self.wallet_address)
        estimated_gas_cost = gas_price * 350000  # Estimated gas limit
        max_spend = float(balance) - float(estimated_gas_cost) - float(self.min_eth_balance)
        return max(0, int(max_spend))

    def estimate_gas_limit(self, txn) -> int:
        """Estimate gas limit with safety buffer"""
        try:
            estimated = self.w3.eth.estimate_gas(txn)
            return int(estimated * 1.2)
        except Exception as e:
            print(f"Gas estimation failed: {e}")
            return 350000  # Fallback gas limit

    def get_optimal_gas_price(self) -> Tuple[int, int]:
        """Get optimal gas price with dynamic adjustment"""
        try:
            # Get base fee from latest block
            latest_block = self.w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            
            # Get pending transactions for gas price analysis
            pending_txns = self.w3.eth.get_block('pending')
            if pending_txns and 'transactions' in pending_txns:
                pending_gas_prices = []
                for tx_hash in pending_txns['transactions'][:10]:  # Sample last 10 transactions
                    try:
                        tx = self.w3.eth.get_transaction(tx_hash)
                        if 'maxFeePerGas' in tx:
                            pending_gas_prices.append(tx['maxFeePerGas'])
                    except Exception:
                        continue
                
                if pending_gas_prices:
                    # Use median of pending transactions as reference
                    median_gas_price = sorted(pending_gas_prices)[len(pending_gas_prices)//2]
                    priority_fee = min(median_gas_price - base_fee, Web3.to_wei(3, 'gwei'))
                else:
                    priority_fee = Web3.to_wei(2, 'gwei')
            else:
                priority_fee = Web3.to_wei(2, 'gwei')
            
            # Calculate max fee (base fee + priority fee + buffer)
            max_fee = min(
                int((base_fee + priority_fee) * 1.2),
                self.max_gas_price
            )
            
            return max_fee, priority_fee
            
        except Exception as e:
            print(f"Error getting optimal gas price: {e}")
            # Fallback to simple calculation
            gas_price = self.w3.eth.gas_price
            return (
                min(int(gas_price * 1.2), self.max_gas_price),
                int(gas_price * 0.1)
            )

    def check_token_liquidity(self, token_address: str, eth_amount: float) -> Tuple[bool, float, str]:
        """Check if token has sufficient liquidity"""
        try:
            # Validate token address
            token_address = self.validate_address(token_address)
            amount_in_wei = Web3.to_wei(eth_amount, 'ether')

            # Get token info first
            token_contract = self.get_token_contract(token_address)
            try:
                symbol = token_contract.functions.symbol().call()
                decimals = token_contract.functions.decimals().call()
            except Exception as e:
                return False, 0, "Could not get token information. This might not be a valid ERC20 token."

            # Check if there's a Uniswap V2 pair
            try:
                # Get current reserves and price impact
                amounts = self.router.functions.getAmountsOut(
                    amount_in_wei,
                    [WETH_ADDRESS, token_address]
                ).call()
                
                # Calculate expected output
                tokens_out = amounts[1]
                
                # Get total supply and calculate liquidity metrics
                total_supply = token_contract.functions.totalSupply().call()
                if total_supply == 0:
                    return False, 0, "Token has no total supply"

                # Calculate liquidity ratio and price impact
                liquidity_ratio = float(tokens_out) / float(total_supply)
                
                # Get current price in ETH
                one_token_price = Web3.to_wei(1, 'ether') / amounts[1]
                
                # More lenient liquidity check
                if tokens_out == 0:
                    return False, 0, "No tokens returned for trade. Insufficient liquidity."
                
                # Check if price impact is reasonable (less than 10%)
                small_amount = Web3.to_wei(0.1, 'ether')
                small_amounts = self.router.functions.getAmountsOut(
                    small_amount,
                    [WETH_ADDRESS, token_address]
                ).call()
                
                price_impact = abs(1 - (amounts[1] / eth_amount) / (small_amounts[1] / 0.1))
                
                if price_impact > 0.10:  # 10% price impact threshold
                    return False, liquidity_ratio, f"High price impact: {price_impact*100:.2f}%. Trade might be front-run."
                
                # Print token information
                print(f"\nToken Information:")
                print(f"Symbol: {symbol}")
                print(f"Decimals: {decimals}")
                print(f"Current price: {one_token_price:.8f} ETH")
                print(f"Expected output: {Web3.from_wei(tokens_out, 'ether')} tokens")
                print(f"Price impact: {price_impact*100:.2f}%")
                
                return True, liquidity_ratio, "Sufficient liquidity"
                
            except Exception as e:
                return False, 0, f"Error checking Uniswap liquidity: {str(e)}"
            
        except Exception as e:
            return False, 0, f"Error checking liquidity: {str(e)}"

    def build_optimized_transaction(self, token_address: str, eth_amount: float, slippage: float) -> Optional[dict]:
        """Build optimized transaction with all checks"""
        try:
            # Validate addresses
            token_address = self.validate_address(token_address)
            
            # Check liquidity
            has_liquidity, liquidity_ratio, message = self.check_token_liquidity(token_address, eth_amount)
            if not has_liquidity:
                print("Insufficient liquidity for trade")
                return None
            
            # Get optimal gas prices
            max_fee, priority_fee = self.get_optimal_gas_price()
            
            # Check if we can afford the transaction
            max_spend = self.calculate_max_spend(max_fee)
            amount_in_wei = Web3.to_wei(eth_amount, 'ether')
            if max_spend < amount_in_wei:
                adjusted_amount = Web3.from_wei(max_spend, 'ether')
                print(f"Adjusting amount to {adjusted_amount} ETH due to gas costs")
                eth_amount = float(adjusted_amount)
                amount_in_wei = Web3.to_wei(eth_amount, 'ether')
            
            if eth_amount <= 0:
                print("Insufficient funds for transaction after gas costs")
                return None
            
            # Calculate minimum tokens to receive
            amounts = self.router.functions.getAmountsOut(
                amount_in_wei,
                [WETH_ADDRESS, token_address]
            ).call()
            min_tokens = int(float(amounts[1]) * (1 - float(slippage)/100))
            
            # Build transaction
            deadline = self.w3.eth.get_block('latest')['timestamp'] + 180
            unsigned_txn = self.router.functions.swapExactETHForTokens(
                min_tokens,
                [WETH_ADDRESS, token_address],
                self.wallet_address,
                deadline
            ).build_transaction({
                'from': self.wallet_address,
                'value': amount_in_wei,
                'maxFeePerGas': max_fee,
                'maxPriorityFeePerGas': priority_fee,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                'type': 2  # EIP-1559
            })
            
            # Estimate and set gas limit
            gas_limit = self.estimate_gas_limit(unsigned_txn)
            unsigned_txn['gas'] = gas_limit
            
            return unsigned_txn
            
        except Exception as e:
            print(f"Error building transaction: {e}")
            return None

    def buy_token_protected(self, token_address: str, eth_amount: float, slippage: float = None) -> Optional[str]:
        """Execute optimized token purchase"""
        try:
            slippage = slippage if slippage is not None else self.default_slippage
            
            # Build optimized transaction
            unsigned_txn = self.build_optimized_transaction(token_address, eth_amount, slippage)
            if not unsigned_txn:
                return None
            
            # Sign transaction
            signed_txn = self.w3.eth.account.sign_transaction(unsigned_txn, self.private_key)
            
            print("\nSubmitting optimized transaction...")
            
            # Submit with retries
            for attempt in range(3):
                try:
                    tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                    print(f"Transaction hash: {tx_hash.hex()}")
                    
                    # Wait for confirmation
                    print("Waiting for confirmation...")
                    receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                    
                    if receipt['status'] == 1:
                        print("\nTransaction successful!")
                        token_contract = self.get_token_contract(token_address)
                        token_balance = token_contract.functions.balanceOf(self.wallet_address).call()
                        print(f"Received {Web3.from_wei(token_balance, 'ether')} tokens")
                        return tx_hash.hex()
                    else:
                        print("\nTransaction failed!")
                        return None
                        
                except Exception as e:
                    if attempt < 2:
                        print(f"Attempt {attempt + 1} failed, retrying...")
                        time.sleep(1)
                    else:
                        print(f"All attempts failed: {e}")
                        return None
            
        except Exception as e:
            print(f"\nError buying token: {e}")
            return None

    def sell_tokens(self, token_address: str, amount: float, min_eth_received: Optional[float] = None, slippage: Optional[float] = None) -> dict:
        """
        Sell ERC20 tokens for ETH with MEV protection
        
        Args:
            token_address: Address of token to sell
            amount: Amount of tokens to sell
            min_eth_received: Minimum amount of ETH to receive (optional)
            slippage: Custom slippage tolerance (optional)
        """
        try:
            # Validate inputs
            token_address = Web3.to_checksum_address(token_address)
            slippage = float(slippage if slippage is not None else self.default_slippage)
            
            if slippage <= 0 or slippage >= 100:
                raise ValueError("Slippage must be between 0 and 100")

            # Get token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.load_abi('ERC20.json')
            )
            
            # Get token info and validate
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
            token_balance = token_contract.functions.balanceOf(self.wallet_address).call()
            
            if token_balance == 0:
                raise ValueError(f"No {symbol} tokens found in wallet")

            # Convert amount to token units
            amount_in_token_units = int(amount * (10 ** decimals))
            if amount_in_token_units > token_balance:
                raise ValueError(f"Insufficient {symbol} balance. You have {token_balance / (10 ** decimals):.8f} {symbol}")

            # Check token approval
            allowance = token_contract.functions.allowance(
                self.wallet_address,
                self.router_address
            ).call()

            # Approve tokens if needed
            if allowance < amount_in_token_units:
                print(f"Approving {symbol} for trading...")
                approve_txn = token_contract.functions.approve(
                    self.router_address,
                    amount_in_token_units
                ).build_transaction({
                    'from': self.wallet_address,
                    'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                    'gas': 100000,  # Standard gas limit for approvals
                    'maxFeePerGas': self.w3.eth.gas_price,
                    'maxPriorityFeePerGas': self.w3.eth.gas_price
                })
                
                signed_approve_txn = self.w3.eth.account.sign_transaction(approve_txn, self.private_key)
                approve_tx_hash = self.w3.eth.send_raw_transaction(signed_approve_txn.rawTransaction)
                self.w3.eth.wait_for_transaction_receipt(approve_tx_hash)

            # Get price quote
            amounts_out = self.router.functions.getAmountsOut(
                amount_in_token_units,
                [token_address, WETH_ADDRESS]
            ).call()
            expected_eth = amounts_out[1]

            # Calculate minimum ETH to receive
            if min_eth_received is None:
                min_eth_received = int(expected_eth * (1 - slippage/100))

            # Prepare transaction parameters
            deadline = int(time.time() + 300)  # 5 minutes
            
            # Get current gas prices
            base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
            priority_fee = self.w3.eth.max_priority_fee
            max_fee_per_gas = base_fee * 2 + priority_fee  # Dynamic gas pricing

            # Build the swap transaction
            swap_txn = self.router.functions.swapExactTokensForETH(
                amount_in_token_units,
                min_eth_received,
                [token_address, WETH_ADDRESS],
                self.wallet_address,
                deadline
            ).build_transaction({
                'from': self.wallet_address,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee,
                'gas': 350000  # Estimated gas limit for swaps
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(swap_txn, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            # Wait for transaction receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                eth_amount = Web3.from_wei(expected_eth, 'ether')
                return {
                    'success': True,
                    'transaction_hash': tx_hash.hex(),
                    'token_amount': amount,
                    'token_symbol': symbol,
                    'eth_received': eth_amount,
                    'gas_used': receipt['gasUsed'],
                    'effective_gas_price': receipt['effectiveGasPrice']
                }
            else:
                raise Exception("Transaction failed")

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

def main():
    try:
        buyer = MEVProtectedBuyer()
        
        while True:
            print("\nMEV Protected Trading Menu:")
            print("1. Buy tokens")
            print("2. Sell tokens")
            print("3. Check token price")
            print("4. Exit")
            
            choice = input("\nEnter your choice (1-4): ")
            
            if choice == "1":
                token_address = input("Enter token address to buy: ").strip()
                eth_amount = float(input("Enter ETH amount to spend: "))
                slippage = input("Enter slippage tolerance % (default 0.5): ").strip()
                slippage = float(slippage) if slippage else None
                
                result = buyer.buy_token_protected(token_address, eth_amount, slippage=slippage)
                if result:
                    print("\nTransaction successful!")
                    print(f"Bought tokens with transaction hash: {result}")
                else:
                    print("\nTransaction failed")
            
            elif choice == "2":
                token_address = input("Enter token address to sell: ").strip()
                amount = float(input("Enter token amount to sell: "))
                slippage = input("Enter slippage tolerance % (default 0.5): ").strip()
                slippage = float(slippage) if slippage else None
                
                result = buyer.sell_tokens(token_address, amount, slippage=slippage)
                if result['success']:
                    print("\nTransaction successful!")
                    print(f"Sold: {result['token_amount']:.8f} {result['token_symbol']}")
                    print(f"Received: {result['eth_received']:.8f} ETH")
                    print(f"Transaction hash: {result['transaction_hash']}")
                else:
                    print(f"\nTransaction failed: {result['error']}")
            
            elif choice == "3":
                token_address = input("Enter token address: ").strip()
                eth_amount = float(input("Enter ETH amount for price check: "))
                result = buyer.check_token_liquidity(token_address, eth_amount)
                if result[0]:
                    print(f"\nPrice quote for {eth_amount} ETH:")
                    print(f"Expected tokens: {Web3.from_wei(result[1], 'ether')} tokens")
                    print(f"Price impact: {result[2]}")
                else:
                    print(f"\nPrice check failed: {result[2]}")
            
            elif choice == "4":
                print("\nGoodbye!")
                break
            
            else:
                print("\nInvalid choice. Please try again.")
                
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
