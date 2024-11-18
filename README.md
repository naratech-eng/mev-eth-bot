# Ethereum MEV-Protected Trading Bot

A sophisticated Ethereum trading bot with advanced MEV (Miner Extractable Value) protection mechanisms for secure token trading on Uniswap V2.

## Key Features

- **MEV Protection**
  - Dynamic gas pricing optimization
  - Transaction timing strategies
  - Frontrunning protection
  - Sandwich attack mitigation

- **Trading Functions**
  - Token buying with MEV protection
  - Token selling with slippage control
  - Price impact analysis
  - Liquidity verification
  - Token approval management

- **Wallet Management**
  - Secure wallet generation
  - Balance checking for ETH and ERC-20 tokens
  - Transaction signing
  - Private key security

- **Advanced Features**
  - Real-time price quotes
  - Dynamic slippage adjustment
  - Gas optimization
  - Comprehensive error handling
  - Detailed transaction reporting

## Prerequisites

- Python 3.10 or higher
- Ethereum wallet with ETH for gas
- Ethereum node access (e.g., Alchemy, Infura)

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd eth-buying-bot
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create and configure your `.env` file:
```bash
cp .env.example .env
```

## Configuration

Add the following to your `.env` file:

```env
ETHEREUM_PRIVATE_KEY=your_private_key_here
ETHEREUM_NODE_URL=your_node_url_here
WALLET_ADDRESS=your_wallet_address
WETH_ADDRESS=0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2
DEFAULT_SLIPPAGE=0.5
GAS_MULTIPLIER=1.1
```

## Usage

### Generate New Wallet
```bash
python generate_wallet.py
```

### Check Token Balances
```bash
python check_balance.py
```

### Trade Tokens
```bash
python mev_protected_buyer.py
```

The trading interface provides options to:
1. Buy tokens
2. Sell tokens
3. Check token prices
4. View transaction status

## Security Features

- No hardcoded sensitive data
- Environment variable management
- Secure mnemonic handling
- Address validation and checksumming
- Transaction verification

## Transaction Protection

- Liquidity verification
- Price impact analysis
- Slippage control
- MEV protection
- Gas optimization
- Failed transaction handling

## Error Handling

The bot handles various scenarios:
- Insufficient balance
- Low liquidity
- High price impact
- Failed transactions
- Network issues
- Invalid tokens

## Project Structure

```
eth-buying-bot/
├── mev_protected_buyer.py  # Main trading logic
├── check_balance.py        # Balance checking utility
├── generate_wallet.py      # Wallet generation tool
├── requirements.txt        # Python dependencies
├── .env                    # Configuration file
└── abis/                  # Smart contract ABIs
    ├── ERC20.json
    └── UniswapV2Router02.json
```

## Best Practices

1. Always test with small amounts first
2. Keep your private key secure
3. Monitor gas prices before trading
4. Check token contracts on Etherscan
5. Verify liquidity before trading

## Limitations

- Uniswap V2 only (currently)
- Ethereum mainnet focus
- Requires manual node configuration
- Gas costs vary with network congestion

## Disclaimer

This bot is for educational purposes only. Cryptocurrency trading carries significant risks. Always:
- DYOR (Do Your Own Research)
- Test with small amounts first
- Never risk more than you can afford to lose
- Verify all token contracts
- Be aware of network conditions

## License

MIT License - See LICENSE file for details
