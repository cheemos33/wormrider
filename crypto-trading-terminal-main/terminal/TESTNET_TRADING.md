# Testnet Trading Setup

## ✅ Implementation Complete!

The bot is now configured to place **REAL orders on Hyperliquid TESTNET**.

---

## 🔧 What Was Implemented:

### 1. **Hyperliquid SDK Integration**
- Installed `hyperliquid-python-sdk` and `eth-account`
- Integrated official Hyperliquid SDK for order placement
- Proper signature generation using your private key

### 2. **Real Order Placement**
- `place_market_order()` now executes real orders on testnet
- Uses IOC (Immediate or Cancel) limit orders at 5% slippage for market-like execution
- Calculates coin size from USD amount automatically

### 3. **Order Flow**
```
Signal Detected (4★) 
  ↓
Check Budget & Positions
  ↓
Get Current Price
  ↓
Calculate Coin Size
  ↓
Place Order on Testnet (with signature)
  ↓
Record Position Locally
```

---

## 🔑 Environment Variables Required:

Your `.env` file should have:
```bash
HYPERLIQUID_SECRET_KEY=0x82ca485fc29e5...  # Your private key (testnet)
HYPERLIQUID_MAIN_WALLET_PUBKEY=0xB...       # Your wallet address
```

---

## 🚀 How It Works:

1. **Bot Detects BTC Long** → Auto-activates
2. **4-Star Signal Appears** → Bot evaluates
3. **Best Signal Selected** → Uses "dip score" to pick deepest dip
4. **Order Placed** → Real execution on testnet
5. **Position Tracked** → Shown in BOT STATUS

---

## 📊 Order Details:

- **Type:** IOC Limit Order (acts like market order)
- **Slippage:** 5% (ensures fill)
- **Size:** $2.50 per entry (configurable)
- **Max Entries:** 3 per coin
- **Total Budget:** $50

---

## ⚠️ Important Notes:

### Testnet vs Mainnet:
- **Price Data:** Fetched from MAINNET (for accuracy)
- **Trading:** Executed on TESTNET (for safety)
- **Positions:** Checked on TESTNET
- **Balance:** Checked on TESTNET

### Safety Features:
- ✅ Budget limits enforced
- ✅ Position limits (3 entries per coin, 20 coins max)
- ✅ Duplicate signal prevention
- ✅ BTC long requirement for auto-activation

---

## 🧪 Testing:

1. **Start the terminal:**
   ```bash
   cd terminal
   source venv/bin/activate
   python app.py
   ```

2. **Check console output:**
   - Look for: `✅ Hyperliquid SDK initialized for testnet`
   - If you see this, SDK is ready!

3. **Wait for 4-star signal:**
   - Bot will automatically place order when criteria met
   - Check BOT STATUS for positions
   - Check RECENT TRADES for execution history

4. **Verify on Hyperliquid:**
   - Go to https://app.hyperliquid-testnet.xyz
   - Connect your wallet
   - Check "Positions" tab for open trades

---

## 🐛 Troubleshooting:

### "Exchange client not initialized"
- Check `.env` file has `HYPERLIQUID_SECRET_KEY`
- Make sure it starts with `0x`
- Restart the app

### "Failed to get current price"
- Network issue or coin not available
- Bot will skip this trade

### Orders not showing on testnet
- Check you're using testnet wallet address
- Verify testnet has balance
- Check console for error messages

---

## 🎯 Next Steps:

Once you're comfortable with testnet:
1. Switch to mainnet keys in `.env`
2. Change API instances in `app.py` from testnet to mainnet
3. Adjust budget/position sizes for real money
4. Monitor carefully!

---

## 📝 Key Files Modified:

- `terminal/data/hyperliquid_api.py` - Order placement implementation
- `terminal/requirements.txt` - Added SDK dependencies
- `terminal/trading/signal_trader.py` - Bot logic (unchanged, uses API)
- `terminal/app.py` - Uses testnet API client (unchanged)

---

**Happy Testing! 🚀**

