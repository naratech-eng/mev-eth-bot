from web3 import Web3
from eth_utils import to_checksum_address
import json
import os
from dotenv import load_dotenv
from typing import Dict, Tuple, Optional

# Load environment variables
load_dotenv()

class BalanceChecker:
    def __init__(self):
        # Initialize connection and credentials
        self.node_url = os.getenv('ETHEREUM_NODE_URL')
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        
        if not all([self.node_url, self.wallet_address]):
            raise ValueError("Missing required environment variables")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.node_url))
        self.wallet_address = Web3.to_checksum_address(self.wallet_address)
        
        # Load ERC20 ABI
        with open('abis/ERC20.json', 'r') as f:
            self.erc20_abi = json.load(f)

    def validate_address(self, address: str) -> str:
        """Validate and convert address to checksum format"""
        try:
            return Web3.to_checksum_address(address.strip())
        except Exception as e:
            raise ValueError(f"Invalid Ethereum address: {address}")

    def get_eth_balance(self) -> float:
        """Get ETH balance"""
        try:
            balance_wei = self.w3.eth.get_balance(self.wallet_address)
            return float(Web3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            print(f"Error getting ETH balance: {e}")
            return 0.0

    def get_token_info(self, token_address: str) -> Tuple[str, str, int]:
        """Get token symbol, name, and decimals"""
        try:
            token_contract = self.w3.eth.contract(
                address=self.validate_address(token_address),
                abi=self.erc20_abi
            )
            
            symbol = token_contract.functions.symbol().call()
            name = token_contract.functions.name().call()
            decimals = token_contract.functions.decimals().call()
            
            return symbol, name, decimals
        except Exception as e:
            print(f"Error getting token info: {e}")
            return None, None, None

    def get_token_balance(self, token_address: str) -> Tuple[float, Dict]:
        """Get token balance and information"""
        try:
            token_address = self.validate_address(token_address)
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=self.erc20_abi
            )
            
            # Get token info
            symbol, name, decimals = self.get_token_info(token_address)
            if not all([symbol, name, decimals]):
                return 0.0, {}
            
            # Get balance
            balance = token_contract.functions.balanceOf(self.wallet_address).call()
            balance_formatted = float(balance) / (10 ** decimals)
            
            return balance_formatted, {
                'symbol': symbol,
                'name': name,
                'decimals': decimals,
                'address': token_address,
                'raw_balance': balance
            }
        except Exception as e:
            print(f"Error getting token balance: {e}")
            return 0.0, {}

    def get_all_token_balances(self, token_addresses: list) -> Dict:
        """Get balances for multiple tokens"""
        balances = {}
        
        # Get ETH balance first
        eth_balance = self.get_eth_balance()
        balances['ETH'] = {
            'symbol': 'ETH',
            'name': 'Ethereum',
            'balance': eth_balance,
            'address': 'Native ETH'
        }
        
        # Get token balances
        for address in token_addresses:
            try:
                balance, token_info = self.get_token_balance(address)
                if balance > 0 and token_info:  # Only include tokens with positive balance
                    balances[token_info['symbol']] = {
                        'symbol': token_info['symbol'],
                        'name': token_info['name'],
                        'balance': balance,
                        'address': token_info['address']
                    }
            except Exception as e:
                print(f"Error processing token {address}: {e}")
                continue
        
        return balances

def format_balance_output(balances: Dict) -> str:
    """Format balance information for display"""
    output = "\n=== Wallet Balance Report ===\n"
    
    # Add wallet address
    output += f"Wallet: {os.getenv('WALLET_ADDRESS')}\n"
    output += "=" * 40 + "\n\n"
    
    # Sort by symbol
    sorted_balances = dict(sorted(balances.items()))
    
    # Display balances
    for symbol, info in sorted_balances.items():
        output += f"Token: {info['name']} ({symbol})\n"
        output += f"Balance: {info['balance']:.8f}\n"
        output += f"Address: {info['address']}\n"
        output += "-" * 40 + "\n"
    
    return output

def main():
    try:
        checker = BalanceChecker()
        
        while True:
            print("\nToken Balance Checker Menu:")
            print("1. Check ETH balance")
            print("2. Check specific token balance")
            print("3. Check multiple token balances")
            print("4. Exit")
            
            choice = input("\nEnter your choice (1-4): ")
            
            if choice == "1":
                eth_balance = checker.get_eth_balance()
                print(f"\nETH Balance: {eth_balance:.8f} ETH")
                
            elif choice == "2":
                token_address = input("\nEnter token contract address: ").strip()
                balance, token_info = checker.get_token_balance(token_address)
                if token_info:
                    print(f"\nToken: {token_info['name']} ({token_info['symbol']})")
                    print(f"Balance: {balance:.8f}")
                    print(f"Contract: {token_info['address']}")
                
            elif choice == "3":
                addresses = []
                print("\nEnter token addresses (one per line, empty line to finish):")
                while True:
                    addr = input().strip()
                    if not addr:
                        break
                    addresses.append(addr)
                
                balances = checker.get_all_token_balances(addresses)
                print(format_balance_output(balances))
                
            elif choice == "4":
                print("\nGoodbye!")
                break
                
            else:
                print("\nInvalid choice. Please try again.")
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
