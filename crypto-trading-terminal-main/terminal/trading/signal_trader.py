"""
Signal-Based Trading Bot for Hyperliquid
Trades 4★ signals after BTC position is opened
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from .position_manager import PositionManager
from data.hyperliquid_api import HyperliquidAPI
from data.analytics_db import analytics_db
from config import config


class SignalTrader:
    """Automated trader that executes 4★ signals"""
    
    def __init__(self, api_client: HyperliquidAPI, budget: float = 50.0, position_size: float = 2.5):
        """
        Initialize signal trader
        
        Args:
            api_client: Hyperliquid API client
            budget: Total trading budget
            position_size: Size per entry in USD
        """
        self.api = api_client
        self.position_manager = PositionManager(budget=budget, position_size=position_size, max_entries_per_coin=1)
        
        # Bot state
        self.is_active = False
        self.activation_time = None
        self.btc_position = None
        
        # Signal tracking
        self.last_trade_time = None
        self.processed_signals = set()  # Track which signals we've already traded
        self.signal_timestamps = {}  # Track signal timestamps for database updates
    
    def check_btc_position(self) -> Optional[Dict]:
        """
        Check if BTC long position exists on mainnet
        Also syncs all positions with exchange
        
        Returns:
            BTC position dict if exists, None otherwise
        """
        try:
            print("🔎 DEBUG: check_btc_position() called")
            wallet = config.HYPERLIQUID_WALLET
            if not wallet:
                print("⚠️ Wallet address not configured")
                return None
            
            # Fetch user positions from Hyperliquid MAINNET
            positions = self.api.get_user_positions(wallet)
            
            # Sync local positions with exchange (remove closed positions)
            sync_result = self.position_manager.sync_with_exchange(positions)
            
            # Find BTC position with positive size (long)
            btc_pos = next((p for p in positions if p['coin'] == 'BTC' and p['size'] > 0), None)
            
            if btc_pos:
                print(f"✅ BTC position detected: {btc_pos['size']} @ ${btc_pos['entry_price']}")
            
            return btc_pos
            
        except Exception as e:
            print(f"Error checking BTC position: {e}")
            return None
    
    def check_balance(self) -> float:
        """
        Check testnet balance
        
        Returns:
            Available balance in USD
        """
        try:
            wallet = config.HYPERLIQUID_WALLET
            if not wallet:
                print("⚠️ Wallet address not configured")
                return 0.0
            
            # Get balance from Hyperliquid TESTNET
            balance = self.api.get_account_balance(wallet)
            print(f"💰 Testnet balance: ${balance:.2f}")
            return balance
            
        except Exception as e:
            print(f"Error checking balance: {e}")
            return 0.0
    
    def calculate_dip_score(self, signal_data: Dict) -> float:
        """
        Calculate dip score for prioritization
        
        Dip Score = |RSI - 18| + |VAL| + |1d RVWAP| + |7d RVWAP|
        Higher score = deeper dip = higher priority
        
        Args:
            signal_data: Dict with rsi, val_distance, rvwap_1d_distance, rvwap_7d_distance
        
        Returns:
            Dip score (float)
        """
        rsi = signal_data.get('rsi', 50)
        val = signal_data.get('val_distance', 0)
        rvwap_1d = signal_data.get('rvwap_1d_distance', 0)
        rvwap_7d = signal_data.get('rvwap_7d_distance', 0)
        
        # Calculate absolute deviations
        rsi_deviation = abs(rsi - 20) if rsi < 20 else 0
        val_deviation = abs(val) if val < 0 else 0  # PRODUCTION - below VAL line
        rvwap_1d_deviation = abs(rvwap_1d) if rvwap_1d < 0 else 0
        rvwap_7d_deviation = abs(rvwap_7d) if rvwap_7d < 0 else 0
        
        score = rsi_deviation + val_deviation + rvwap_1d_deviation + rvwap_7d_deviation
        
        return score
    
    def get_strongest_signal(self, signals: List[Dict]) -> Optional[Dict]:
        """
        Get the signal with highest dip score
        
        Args:
            signals: List of signal dicts with coin and indicator data
        
        Returns:
            Signal dict with highest score, or None
        """
        if not signals:
            return None
        
        # Filter out coins that are maxed out
        tradeable_signals = []
        for signal in signals:
            coin = signal.get('coin')
            can_trade, _ = self.position_manager.can_open_position(coin)
            if can_trade:
                signal['dip_score'] = self.calculate_dip_score(signal)
                tradeable_signals.append(signal)
        
        if not tradeable_signals:
            return None
        
        # Sort by dip score (highest first)
        tradeable_signals.sort(key=lambda x: x['dip_score'], reverse=True)
        
        return tradeable_signals[0]
    
    def execute_trade(self, coin: str, price: float) -> bool:
        """
        Execute a long trade on Hyperliquid testnet
        
        Args:
            coin: Coin to long
            price: Current price
        
        Returns:
            Success boolean
        """
        try:
            wallet = config.HYPERLIQUID_WALLET
            if not wallet:
                print("⚠️ Wallet address not configured")
                return False
            
            size_usd = self.position_manager.position_size
            
            # Place market order on Hyperliquid MAINNET
            print(f"🔄 Placing order: LONG {coin} ${size_usd} @ ${price} (4x leverage)")
            
            result = self.api.place_market_order(
                wallet_address=wallet,
                coin=coin,
                is_buy=True,
                size_usd=size_usd,
                leverage=4
            )
            
            if result and result.get('status') == 'success':
                # Record position with leverage
                success = self.position_manager.add_position(coin, price, size_usd, leverage=4)
                
                if success:
                    self.last_trade_time = datetime.now()
                    
                    # Update signal in database as traded
                    try:
                        entry_time = datetime.now().isoformat()
                        signal_timestamp = self.signal_timestamps.get(coin)
                        if signal_timestamp:
                            analytics_db.update_signal_entry(
                                coin=coin,
                                timestamp=signal_timestamp,
                                entry_price=price,
                                entry_time=entry_time
                            )
                    except Exception as e:
                        print(f"⚠️ Failed to update signal entry in database: {e}")
                
                return success
            else:
                # Order failed or rejected - save rejection reason
                print(f"❌ Order failed for {coin}")
                
                # Save rejection reason to database
                try:
                    rejection_reason = None
                    if result and result.get('status') == 'rejected':
                        error_msg = result.get('error', 'Unknown error')
                        # Parse error message into friendly format
                        if 'open interest' in error_msg.lower() or 'at cap' in error_msg.lower():
                            rejection_reason = 'Position Cap'
                        elif 'could not immediately match' in error_msg.lower():
                            rejection_reason = 'No Liquidity'
                        elif 'insufficient' in error_msg.lower():
                            rejection_reason = 'Insufficient Funds'
                        else:
                            rejection_reason = 'Exchange Error'
                    else:
                        rejection_reason = 'Unknown Error'
                    
                    signal_timestamp = self.signal_timestamps.get(coin)
                    if signal_timestamp:
                        analytics_db.update_signal_rejection(
                            coin=coin,
                            timestamp=signal_timestamp,
                            rejection_reason=rejection_reason
                        )
                except Exception as e:
                    print(f"⚠️ Failed to save rejection reason to database: {e}")
                
                return False
            
        except Exception as e:
            print(f"❌ Error executing trade: {e}")
            return False
    
    def activate(self) -> bool:
        """Activate the bot"""
        # Check balance
        balance = self.check_balance()
        if balance < self.position_manager.total_budget:
            print(f"⚠️ Insufficient balance: ${balance:.2f} < ${self.position_manager.total_budget}")
            return False
        
        self.is_active = True
        self.activation_time = datetime.now()
        print(f"✅ Bot ACTIVATED at {self.activation_time.strftime('%H:%M:%S')}")
        print(f"💰 Budget: ${self.position_manager.total_budget} | Position size: ${self.position_manager.position_size}")
        return True
    
    def deactivate(self):
        """Deactivate the bot"""
        self.is_active = False
        print(f"⏸️ Bot DEACTIVATED - Keeping positions open")
    
    def process_signals(self, current_signals: List[Dict]) -> Optional[Dict]:
        """
        Process current signals and execute trade if appropriate
        
        Args:
            current_signals: List of 4★ signals with coin and indicator data
        
        Returns:
            Trade result dict if trade executed, None otherwise
        """
        if not self.is_active:
            return None
        
        # Filter signals that appeared after activation
        new_signals = []
        for signal in current_signals:
            # Check if this is a new signal (not already traded)
            signal_id = f"{signal['coin']}_{signal.get('timestamp', '')}"
            if signal_id not in self.processed_signals:
                new_signals.append(signal)
                
                # Save signal to analytics database
                try:
                    timestamp = signal.get('timestamp', datetime.now().isoformat())
                    analytics_db.insert_signal(
                        coin=signal['coin'],
                        timestamp=timestamp,
                        stars=4,
                        rsi=signal.get('rsi', 0),
                        val=signal.get('val_distance', 0),
                        rvwap_1d=signal.get('rvwap_1d_distance', 0),
                        rvwap_7d=signal.get('rvwap_7d_distance', 0),
                        price_at_signal=signal.get('price', 0),
                        skip_reason=None  # Will be set later if not traded
                    )
                    # Store timestamp for later database updates
                    self.signal_timestamps[signal['coin']] = timestamp
                except Exception as e:
                    print(f"⚠️ Failed to save signal to database: {e}")
        
        if not new_signals:
            return None
        
        # Check if enough time passed since last trade (3 minutes for mainnet)
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).total_seconds()
            if time_since_last < 180:
                return None
        
        # Get all signals sorted by dip score (best first)
        tradeable_signals = []
        for signal in new_signals:
            # Check if can open position for this coin
            can_trade, reason = self.position_manager.can_open_position(signal['coin'])
            if can_trade:
                signal['dip_score'] = self.calculate_dip_score(signal)
                tradeable_signals.append(signal)
        
        if not tradeable_signals:
            return None
        
        # Sort by dip score (highest first)
        tradeable_signals.sort(key=lambda x: x['dip_score'], reverse=True)
        
        # Try signals in order until one succeeds (fallback logic)
        for signal in tradeable_signals:
            coin = signal['coin']
            price = signal.get('price', 0)
            
            print(f"🎯 Attempting trade: {coin} (dip score: {signal['dip_score']:.2f})")
            
            success = self.execute_trade(coin, price)
            
            if success:
                # Mark signal as processed
                signal_id = f"{coin}_{signal.get('timestamp', '')}"
                self.processed_signals.add(signal_id)
                
                # Keep processed signals list manageable
                if len(self.processed_signals) > 1000:
                    self.processed_signals = set(list(self.processed_signals)[-500:])
                
                return {
                    'coin': coin,
                    'price': price,
                    'size': self.position_manager.position_size,
                    'dip_score': signal['dip_score'],
                    'entry_num': self.position_manager.get_entry_count(coin)
                }
            else:
                # This coin failed, try next one
                print(f"⏭️ Skipping {coin}, trying next signal...")
                continue
        
        # All signals failed
        print("❌ All signals failed to execute")
        return None
    
    def get_status(self, current_prices: Dict[str, float] = None) -> Dict:
        """
        Get bot status for display
        
        Args:
            current_prices: Dict of {coin: current_price} for P&L calculation
        """
        summary = self.position_manager.get_position_summary(current_prices)
        
        return {
            'is_active': self.is_active,
            'activation_time': self.activation_time.strftime('%H:%M:%S') if self.activation_time else None,
            'btc_position': self.btc_position,
            'budget_total': self.position_manager.total_budget,
            'budget_spent': summary['total_spent'],
            'budget_remaining': summary['remaining_budget'],
            'notional_total': self.position_manager.get_notional_budget(),
            'notional_spent': self.position_manager.get_notional_spent(),
            'notional_remaining': self.position_manager.get_remaining_notional(),
            'total_coins': summary['total_coins'],
            'total_entries': summary['total_entries'],
            'positions': summary['positions'],
            'recent_trades': self.position_manager.get_trade_history(20)
        }
    
    def close_position(self, coin: str) -> bool:
        """
        Close a position on Hyperliquid exchange
        
        Args:
            coin: Coin symbol to close
        
        Returns:
            Success boolean
        """
        try:
            if not self.api.exchange:
                print("❌ Exchange client not initialized")
                return False
            
            print(f"🔄 Closing {coin} position on Hyperliquid...")
            
            # First, verify position exists on exchange
            wallet = config.HYPERLIQUID_WALLET
            exchange_positions = self.api.get_user_positions(wallet)
            
            coin_position = next((p for p in exchange_positions if p['coin'] == coin), None)
            
            if not coin_position:
                print(f"⚠️ {coin} position not found on exchange - removing from local tracking only")
                success = self.position_manager.close_position(coin)
                return success
            
            position_size = coin_position['size']
            print(f"   Found {coin} position: size={position_size}")
            
            # Determine if we need to BUY or SELL to close
            # Positive size = long position → need to SELL to close
            # Negative size = short position → need to BUY to close
            is_buy = position_size < 0
            close_size = abs(position_size)
            
            print(f"   Closing: {'BUY' if is_buy else 'SELL'} {close_size} {coin}")
            
            # Get current price for limit order
            current_price = self.api.fetch_current_price(coin)
            if not current_price:
                print(f"❌ Failed to get current price for {coin}")
                return False
            
            # Set aggressive limit price to ensure fill
            # Use 5 decimal places for accurate pricing on low-priced coins
            if is_buy:
                limit_price = round(current_price * 1.05, 5)  # 5% above for buy
            else:
                limit_price = round(current_price * 0.95, 5)  # 5% below for sell
            
            # Place closing order with reduce-only
            try:
                result = self.api.exchange.order(
                    coin,
                    is_buy,
                    close_size,
                    limit_price,
                    {"limit": {"tif": "Ioc"}, "reduce_only": True}  # Reduce-only prevents opening opposite
                )
                print(f"📤 Close result: {result}")
            except Exception as close_error:
                print(f"❌ Close order error: {close_error}")
                import traceback
                traceback.print_exc()
                return False
            
            # Check if successful
            if result and isinstance(result, dict):
                if result.get('status') == 'ok':
                    # Check for errors
                    response_data = result.get('response', {}).get('data', {})
                    statuses = response_data.get('statuses', [])
                    
                    if statuses and len(statuses) > 0:
                        if 'error' in statuses[0]:
                            error_msg = statuses[0]['error']
                            print(f"❌ Close rejected: {error_msg}")
                            return False
                    
                    # Get position data before closing (for P&L calculation)
                    position_entries = self.position_manager.positions['active_positions'].get(coin, [])
                    if position_entries:
                        # Calculate average entry price and total size
                        avg_entry = sum(e['price'] * e['size'] for e in position_entries) / sum(e['size'] for e in position_entries)
                        total_size = sum(e['size'] for e in position_entries)
                        first_entry_time = position_entries[0]['timestamp']
                        
                        # Calculate P&L
                        pnl_usd = (current_price - avg_entry) / avg_entry * total_size
                        pnl_pct = ((current_price - avg_entry) / avg_entry) * 100
                        
                        # Update signal exit in database
                        try:
                            analytics_db.update_signal_exit(
                                coin=coin,
                                entry_time=first_entry_time,
                                exit_price=current_price,
                                exit_time=datetime.now().isoformat(),
                                pnl_usd=pnl_usd,
                                pnl_pct=pnl_pct
                            )
                        except Exception as e:
                            print(f"⚠️ Failed to update signal exit in database: {e}")
                    
                        # Success - remove from local tracking and save exit data
                        success = self.position_manager.close_position(
                            coin=coin,
                            exit_price=current_price,
                            exit_pnl_usd=pnl_usd,
                            exit_pnl_pct=pnl_pct
                        )
                        if success:
                            print(f"✅ {coin} position closed successfully!")
                            return True
                    else:
                        # No position data found, close without exit data
                        success = self.position_manager.close_position(coin)
                        if success:
                            print(f"✅ {coin} position closed successfully!")
                            return True
            
            print(f"❌ Close failed: unexpected response")
            return False
            
        except Exception as e:
            print(f"❌ Error closing position: {e}")
            import traceback
            traceback.print_exc()
            return False

