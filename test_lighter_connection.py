"""
Test Lighter connection and credentials
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("LIGHTER CONNECTION TEST")
print("="*60)

# Check environment
use_mainnet = os.getenv('USE_LIGHTER_MAINNET', 'false').lower() == 'true'
network = "MAINNET" if use_mainnet else "TESTNET"

print(f"\n🌐 Network: {network}")

if use_mainnet:
    url = os.getenv('LIGHTER_MAINNET_URL')
    private_key = os.getenv('LIGHTER_MAINNET_PRIVATE_KEY')
    print(f"🔗 URL: {url}")
    print(f"🔑 Private Key: {private_key[:10]}...{private_key[-5:] if private_key else 'NOT SET'}")
else:
    url = os.getenv('LIGHTER_TESTNET_URL')
    private_key = os.getenv('LIGHTER_TESTNET_PRIVATE_KEY')
    print(f"🔗 URL: {url}")
    print(f"🔑 Private Key: {'SET' if private_key else 'NOT SET'}")

# Try to initialize
print("\n🔧 Initializing Lighter clients...")
try:
    from exchange import lighter
    lighter.init_clients()
    print("✅ Clients initialized successfully!")
    
    # Try to get account info
    print("\n📊 Getting account info...")
    account = lighter.get_account_info()
    if account:
        print("✅ Account info retrieved!")
        print(f"   Account: {account}")
    else:
        print("⚠️  Could not retrieve account info")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*60)
