"""Alert management system."""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import threading
from database import db


class AlertManager:
    """Manages alert generation and storage."""
    
    def __init__(self):
        self.alerts_history: List[Dict[str, Any]] = []
        self.last_alert_time = {}  # Prevent spam alerts
        self.alert_cooldown = 300  # 5 minutes cooldown between same setup types
        self.max_history = 50  # Keep last 50 alerts in memory
    
    def process_alert(self, alert_data: Dict[str, Any]) -> bool:
        """
        Process and store alert if valid.
        
        Args:
            alert_data: Alert data from setup detection
            
        Returns:
            True if alert was processed, False if ignored (cooldown)
        """
        
        # Check cooldown
        alert_key = f"{alert_data['direction']}_{alert_data['wall_price']}"
        current_time = time.time()
        
        if alert_key in self.last_alert_time:
            if current_time - self.last_alert_time[alert_key] < self.alert_cooldown:
                return False  # Still in cooldown
        
        # Update last alert time
        self.last_alert_time[alert_key] = current_time
        
        # Add alert to history
        alert_entry = {
            'timestamp': alert_data['timestamp'],
            'type': alert_data['type'],
            'direction': alert_data['direction'],
            'wall_price': alert_data['wall_price'],
            'current_price': alert_data['current_price'],
            'confidence': alert_data['setup_confidence'],
            'message': self._generate_alert_message(alert_data)
        }
        
        self.alerts_history.append(alert_entry)
        
        # Keep only recent alerts
        if len(self.alerts_history) > self.max_history:
            self.alerts_history = self.alerts_history[-self.max_history:]
        
        # Log to console
        self._log_alert(alert_entry)
        
        # Store in database (future enhancement)
        # db.store_alert(alert_entry)
        
        return True
    
    def _generate_alert_message(self, alert_data: Dict[str, Any]) -> str:
        """Generate human-readable alert message."""
        
        direction = alert_data['direction'].upper()
        wall_price = alert_data['wall_price']
        current_price = alert_data['current_price']
        confidence = alert_data['setup_confidence']
        distance_pct = alert_data['distance_pct']
        
        # Format prices
        wall_str = f"${wall_price:,.2f}"
        price_str = f"${current_price:,.2f}"
        
        # Confidence level
        if confidence > 0.8:
            conf_level = "HIGH"
        elif confidence > 0.6:
            conf_level = "MEDIUM"
        else:
            conf_level = "LOW"
        
        # Generate message
        message = (
            f"🚨 {direction} ALERT - {conf_level} Confidence\n"
            f"Wall: {wall_str} | Price: {price_str}\n"
            f"Distance: {distance_pct:.2f}% | CVD: {alert_data['cvd_slope']}\n"
            f"Expected: Price move toward {wall_str}"
        )
        
        return message
    
    def _log_alert(self, alert_entry: Dict[str, Any]):
        """Log alert to console."""
        timestamp = datetime.fromtimestamp(alert_entry['timestamp'] / 1000).strftime('%H:%M:%S')
        
        print(f"\n{'='*60}")
        print(f"ALERT [{timestamp}] - {alert_entry['direction'].upper()}")
        print(f"{'='*60}")
        print(alert_entry['message'])
        print(f"{'='*60}\n")
    
    def get_recent_alerts(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent alerts for UI display."""
        return self.alerts_history[-limit:] if self.alerts_history else []
    
    def get_alert_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        if not self.alerts_history:
            return {
                'total_alerts': 0,
                'long_alerts': 0,
                'short_alerts': 0,
                'last_alert_time': None
            }
        
        total = len(self.alerts_history)
        long_count = sum(1 for alert in self.alerts_history if alert['direction'] == 'long')
        short_count = total - long_count
        
        return {
            'total_alerts': total,
            'long_alerts': long_count,
            'short_alerts': short_count,
            'last_alert_time': self.alerts_history[-1]['timestamp'] if self.alerts_history else None
        }


# Global alert manager
alert_manager = AlertManager()


def process_alert(alert_data: Dict[str, Any]) -> bool:
    """Global function to process alert."""
    return alert_manager.process_alert(alert_data)


def get_recent_alerts(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent alerts."""
    return alert_manager.get_recent_alerts(limit)


def get_alert_stats() -> Dict[str, Any]:
    """Get alert statistics."""
    return alert_manager.get_alert_stats()
