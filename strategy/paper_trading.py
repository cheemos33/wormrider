"""Paper trading monitor for tracking signal performance."""

import time
import threading
from typing import Optional, Dict, Any, List
from database import db_signals


class PaperTradingMonitor:
    """
    Monitor active signals and update status when TP/SL hit.
    Runs in background thread, checking current price every second.
    """
    
    def __init__(self):
        self.running = False
        self.monitor_thread = None
        self.current_price = None
        self.check_interval = 1.0  # Check every 1 second
    
    def update_price(self, price: float):
        """Update current price (called from main app)."""
        self.current_price = price
    
    def start(self):
        """Start monitoring thread."""
        if self.running:
            return
        
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("📊 Paper trading monitor started")
    
    def stop(self):
        """Stop monitoring thread."""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2.0)
    
    def _monitor_loop(self):
        """Main monitoring loop - monitors all 3 strategies."""
        while self.running:
            try:
                # Get active signals for all 3 strategies
                active_historical = db_signals.get_active_signal('HISTORICAL')
                active_instant = db_signals.get_active_signal('INSTANT')
                active_hybrid = db_signals.get_active_signal('HYBRID')
                
                # Check exit conditions for each active signal
                if active_historical and self.current_price:
                    self._check_exit_conditions(active_historical)
                
                if active_instant and self.current_price:
                    self._check_exit_conditions(active_instant)
                
                if active_hybrid and self.current_price:
                    self._check_exit_conditions(active_hybrid)
                
                # Also check pending signals for immediate entry (all 3 strategies)
                pending_historical = db_signals.get_pending_signal('HISTORICAL')
                pending_instant = db_signals.get_pending_signal('INSTANT')
                pending_hybrid = db_signals.get_pending_signal('HYBRID')
                
                if pending_historical and self.current_price:
                    self._activate_pending_signal(pending_historical)
                
                if pending_instant and self.current_price:
                    self._activate_pending_signal(pending_instant)
                
                if pending_hybrid and self.current_price:
                    self._activate_pending_signal(pending_hybrid)
                
            except Exception as e:
                print(f"Error in paper trading monitor: {e}")
            
            time.sleep(self.check_interval)
    
    def _activate_pending_signal(self, signal: Dict[str, Any]):
        """
        Activate pending signal (simulate immediate entry at entry_price).
        In paper trading, we assume instant fill at signal price.
        """
        signal_id = signal['id']
        entry_price = signal['entry_price']
        entry_time = int(time.time() * 1000)
        
        # Update to active (correct parameter order: signal_id, entry_price, entry_time)
        db_signals.update_signal_entry(signal_id, entry_price, entry_time)
        
        # Log entry
        direction = signal['direction']
        emoji = '🔴' if direction == 'short' else '🟢'
        
        print(f"\n{'='*60}")
        print(f"{emoji} {direction.upper()} ENTRY @ ${entry_price:,.2f}")
        print(f"   TP: ${signal['tp_price']:,.2f} | SL: ${signal['sl_price']:,.2f}")
        print(f"   Imbalance: {signal['imbalance_ratio']*100:.1f}% | CVD: {signal['cvd_slope']}")
        print(f"{'='*60}\n")
    
    def _check_exit_conditions(self, signal: Dict[str, Any]):
        """Check if TP or SL hit for active signal."""
        direction = signal['direction']
        entry_price = signal['entry_price']
        tp_price = signal['tp_price']
        sl_price = signal['sl_price']
        current = self.current_price
        
        hit_tp = False
        hit_sl = False
        
        if direction == 'long':
            # Long: TP above, SL below
            if current >= tp_price:
                hit_tp = True
            elif current <= sl_price:
                hit_sl = True
        else:  # short
            # Short: TP below, SL above
            if current <= tp_price:
                hit_tp = True
            elif current >= sl_price:
                hit_sl = True
        
        if hit_tp:
            self._close_position(signal, current, 'tp_hit', 'Price reached TP (+$50)')
        elif hit_sl:
            self._close_position(signal, current, 'sl_hit', 'Price reached SL (-$40)')
    
    def _close_position(self, signal: Dict[str, Any], exit_price: float, status: str, exit_reason: str):
        """Close position and log result."""
        signal_id = signal['id']
        direction = signal['direction']
        entry_price = signal['entry_price']
        exit_time = int(time.time() * 1000)
        
        # Position size: $1000 with 5x leverage = $5000 position
        position_size_usd = 5000.0
        
        # Calculate price difference
        if direction == 'long':
            price_diff = exit_price - entry_price
        else:  # short
            price_diff = entry_price - exit_price
        
        # Calculate PnL based on position size
        # PnL = (price_diff / entry_price) * position_size
        pnl = (price_diff / entry_price) * position_size_usd
        
        # Calculate duration
        entry_time = signal['entry_time']
        duration_seconds = (exit_time - entry_time) / 1000
        
        # Update database with exit_reason
        db_signals.update_signal_exit(signal_id, exit_price, exit_time, pnl, status, exit_reason)
        
        # Log exit
        emoji = '✅' if status == 'tp_hit' else '❌'
        status_text = 'TP HIT' if status == 'tp_hit' else 'SL HIT'
        pnl_color = '+' if pnl > 0 else ''
        pnl_pct = (pnl / position_size_usd) * 100
        
        print(f"\n{'='*60}")
        print(f"{emoji} {status_text} @ ${exit_price:,.2f}")
        print(f"   Entry: ${entry_price:,.2f} → Exit: ${exit_price:,.2f}")
        print(f"   Price Diff: {pnl_color}${price_diff:.2f}")
        print(f"   Position: $5000 (5x leverage)")
        print(f"   PnL: {pnl_color}${pnl:.2f} ({pnl_color}{pnl_pct:.2f}%)")
        print(f"   Duration: {duration_seconds:.0f}s")
        print(f"   Reason: {exit_reason}")
        print(f"{'='*60}\n")


# Global instance
paper_monitor = PaperTradingMonitor()

