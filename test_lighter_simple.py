"""
Simple test of Lighter SDK connection
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("="*60)
print("LIGHTER SDK TEST")
print("="*60)

try:
    from lighter import Configuration, ApiClient
    
    use_mainnet = os.getenv('USE_LIGHTER_MAINNET', 'false').lower() == 'true'
    
    if use_mainnet:
        url = os.getenv('LIGHTER_MAINNET_URL', 'https://mainnet.zklighter.elliot.ai')
        network = "MAINNET"
    else:
        url = os.getenv('LIGHTER_TESTNET_URL', 'https://lighter-api-testnet.publicnode.com')
        network = "TESTNET"
    
    print(f"\n🌐 Network: {network}")
    print(f"🔗 URL: {url}")
    
    # Test configuration
    configuration = Configuration(host=url)
    configuration.verify_ssl = False
    
    print("✅ Configuration created successfully!")
    print(f"   Host: {configuration.host}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("="*60)
