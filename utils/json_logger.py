"""
JSON Logger for signals and trades
Saves all signals to a single JSON file
"""

import json
import os
from datetime import datetime
from typing import Dict, Any


class JsonLogger:
    """Log signals and trades to JSON files"""
    
    def __init__(self, log_dir: str = "/Users/cheemos/Desktop/lighter-test-by-chat"):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = f"{log_dir}/signals.json"
    
    def log_signal(self, signal: Dict[str, Any], signal_type: str = "signal"):
        """Log a signal to JSON file (all in one file)"""
        
        # Read existing logs
        logs = []
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    logs = json.load(f)
            except:
                logs = []
        
        # Add timestamp and type to signal
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'type': signal_type,
            'data': signal
        }
        
        logs.append(log_entry)
        
        # Write back
        try:
            with open(self.log_file, 'w') as f:
                json.dump(logs, f, indent=2)
            print(f"📝 JSON logged: {self.log_file}")
        except Exception as e:
            print(f"Error writing to {self.log_file}: {e}")
    
    def log_trade(self, trade: Dict[str, Any]):
        """Log a trade to JSON file"""
        self.log_signal(trade, signal_type="trade")
    
    def log_entry(self, entry: Dict[str, Any]):
        """Log a position entry"""
        self.log_signal(entry, signal_type="entry")
    
    def log_exit(self, exit_info: Dict[str, Any]):
        """Log a position exit"""
        self.log_signal(exit_info, signal_type="exit")


# Global instance
json_logger = JsonLogger()
