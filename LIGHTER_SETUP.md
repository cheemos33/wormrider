# Lighter.xyz Mainnet Integration Setup

## ✅ Completed Setup

### 1. Environment Configuration
- **Network**: Mainnet
- **API URL**: https://mainnet.zklighter.elliot.ai
- **Private Key**: Configured (hidden for security)
- **Position Size**: $10 (test size)

### 2. Files Created
- `exchange/lighter.py` - Lighter SDK integration
- `strategy/live_trading.py` - Live trading logic
- `.env` - Environment variables
- `.env.example` - Template for other developers

### 3. Configuration Values
```
USE_LIGHTER_MAINNET=true
LIGHTER_POSITION_SIZE=10
LIGHTER_TP_PCT=0.001327  # +0.1327%
LIGHTER_SL_PCT=0.001062  # -0.1062%
LIGHTER_LIVE_TRADING=false  # Disabled for safety
```

## 🚀 How to Enable Live Trading

### Step 1: Edit .env
```bash
LIGHTER_LIVE_TRADING=true
```

### Step 2: Verify Settings
- Check position size: `LIGHTER_POSITION_SIZE=10`
- Check TP/SL percentages
- Verify network is MAINNET

### Step 3: Test Connection
```bash
python3 test_lighter_connection.py
python3 test_live_trading.py
```

### Step 4: Start Trading
```bash
python3 app.py
```

## ⚠️ Important Notes

1. **Start Small**: Position size is $10 for testing
2. **Monitor Closely**: Watch first few trades carefully
3. **Mainnet**: Real money is at stake
4. **Backup**: Keep `.env` file backed up securely

## 📊 What Happens When Enabled

1. Paper trading signals are generated as before
2. Each signal triggers a real trade on Lighter
3. TP/SL are managed by Lighter smart contracts
4. Trades are logged to database

## 🔧 Troubleshooting

### Error: "no running event loop"
- Lighter SDK requires async context
- May need to wrap calls in async functions

### Error: "Private key not set"
- Check `.env` file exists
- Verify `LIGHTER_MAINNET_PRIVATE_KEY` is set

### Error: "Connection failed"
- Check network connectivity
- Verify Lighter mainnet is operational
- Try testnet first for debugging

## 📝 Next Steps

1. Test with paper trading first
2. Enable live trading on testnet
3. Test with small position on mainnet
4. Scale up gradually
