from eth_account import Account
from mnemonic import Mnemonic
import secrets
from eth_utils import to_hex

def generate_wallet_with_mnemonic():
    """Generate an Ethereum wallet with mnemonic phrase"""
    # Generate mnemonic (seed phrase)
    mnemo = Mnemonic("english")
    mnemonic = mnemo.generate(strength=256)  # 24 words
    seed = mnemo.to_seed(mnemonic)
    
    # Generate private key from seed
    private_key = to_hex(seed[:32])  # Take first 32 bytes for private key
    account = Account.from_key(private_key)
    address = account.address
    
    print("\nWallet Details:")
    print(f"Address: {address}")
    print(f"\nMnemonic Phrase (24 words):")
    print(f"{mnemonic}")
    print(f"\nPrivate Key: {private_key}")
    print("\nIMPORTANT: Save your mnemonic phrase securely! It's your wallet backup.")
    return private_key, address, mnemonic

if __name__ == "__main__":
    try:
        # Generate wallet with mnemonic
        private_key, address, mnemonic = generate_wallet_with_mnemonic()
        
        # Update .env file
        with open('.env', 'r') as file:
            env_contents = file.readlines()
        
        # Update the relevant lines
        for i, line in enumerate(env_contents):
            if 'ETHEREUM_PRIVATE_KEY=' in line:
                env_contents[i] = f'ETHEREUM_PRIVATE_KEY={private_key[2:] if private_key.startswith("0x") else private_key}\n'
            elif 'WALLET_ADDRESS=' in line:
                env_contents[i] = f'WALLET_ADDRESS={address}\n'
        
        # Write back to .env
        with open('.env', 'w') as file:
            file.writelines(env_contents)
        
        # Save mnemonic to a separate secure file
        with open('wallet_backup.txt', 'w') as file:
            file.write("IMPORTANT: Keep this file secure and never share it with anyone!\n\n")
            file.write("Ethereum Wallet Backup\n")
            file.write("=====================\n\n")
            file.write(f"Wallet Address: {address}\n\n")
            file.write("Mnemonic Phrase (24 words):\n")
            file.write(f"{mnemonic}\n\n")
            file.write("Instructions:\n")
            file.write("1. Write down these 24 words on paper\n")
            file.write("2. Store the paper in a secure location\n")
            file.write("3. Never share your mnemonic phrase with anyone\n")
            file.write("4. You can restore your wallet using these words\n")
        
        print("\nWallet details have been added to your .env file!")
        print("Mnemonic phrase has been saved to 'wallet_backup.txt'")
        print("\nWARNING: Make sure to backup your mnemonic phrase and delete wallet_backup.txt after securing it!")
        
    except Exception as e:
        print(f"An error occurred: {e}")
