"""
Data Processor for Trading Terminal
Processes raw API data for visualization
"""
import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from data.hyperliquid_api import api_client


def calculate_24h_change(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate % change from 24 hours ago for price data
    
    Args:
        df: DataFrame with 'timestamp' and 'close' columns
    
    Returns:
        DataFrame with additional 'pct_change' column (normalized to 0% at start)
    """
    if df is None or df.empty:
        return df
    
    df = df.copy()
    df = df.sort_values('timestamp')
    
    # Get the first price (24h ago)
    first_price = df.iloc[0]['close']
    
    # Calculate % change from first price
    df['pct_change'] = ((df['close'] - first_price) / first_price) * 100
    
    # REMOVED: Hardcoded ±20% cap that was causing the artificial limit
    # Let the dynamic range in spaghetti.py handle extreme values
    # df['pct_change'] = df['pct_change'].clip(-20, 20)
    
    return df


def prepare_spaghetti_data(watchlist: List[str]) -> Dict[str, pd.DataFrame]:
    """
    Fetch and prepare 24h data for all coins in watchlist
    
    Args:
        watchlist: List of coin symbols
    
    Returns:
        Dictionary mapping coin symbols to processed DataFrames
    """
    all_data = {}
    
    print(f"Fetching 24h data for {len(watchlist)} coins...")
    
    for coin in watchlist:
        print(f"  Fetching {coin}...")
        df = api_client.fetch_24h_price_data(coin)
        
        if df is not None and not df.empty:
            # Calculate % change
            df = calculate_24h_change(df)
            all_data[coin] = df
        else:
            print(f"  ⚠️  No data for {coin}")
    
    print(f"Successfully fetched data for {len(all_data)}/{len(watchlist)} coins")
    
    return all_data


def calculate_volume_profile(df: pd.DataFrame, num_bins: int = 50) -> dict:
    """
    Calculate Volume Profile for price data
    
    Args:
        df: DataFrame with 'close' and 'volume' columns
        num_bins: Number of price bins for VP calculation
    
    Returns:
        Dictionary with POC, VAL, VAH values
    """
    if df is None or df.empty or len(df) < 10:
        return {'poc': None, 'val': None, 'vah': None}
    
    try:
        # Get price range
        min_price = df['low'].min()
        max_price = df['high'].max()
        
        # Create price bins
        price_bins = pd.cut(df['close'], bins=num_bins, include_lowest=True)
        
        # Sum volume for each price bin
        volume_by_price = df.groupby(price_bins)['volume'].sum()
        
        # Find POC (Point of Control - highest volume)
        poc_bin = volume_by_price.idxmax()
        poc = poc_bin.mid
        
        # Sort by volume to find value area (70% of total volume)
        total_volume = volume_by_price.sum()
        target_volume = total_volume * 0.70
        
        sorted_bins = volume_by_price.sort_values(ascending=False)
        cumulative_volume = 0
        value_area_bins = []
        
        for bin_interval, vol in sorted_bins.items():
            cumulative_volume += vol
            value_area_bins.append(bin_interval)
            if cumulative_volume >= target_volume:
                break
        
        # Get VAL and VAH from value area bins
        value_area_prices = [b.mid for b in value_area_bins]
        val = min(value_area_prices)
        vah = max(value_area_prices)
        
        return {
            'poc': float(poc),
            'val': float(val),
            'vah': float(vah)
        }
    
    except Exception as e:
        print(f"Error calculating VP: {e}")
        return {'poc': None, 'val': None, 'vah': None}


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    Calculate RSI (Relative Strength Index)
    
    Args:
        prices: Series of close prices
        period: RSI period (default 14)
    
    Returns:
        Current RSI value (0-100)
    """
    if len(prices) < period + 1:
        return 50.0  # Not enough data, return neutral
    
    # Calculate price changes
    delta = prices.diff()
    
    # Separate gains and losses
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # Calculate RS and RSI
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0


def calculate_rolling_vwap(df: pd.DataFrame) -> float:
    """
    Calculate Rolling VWAP (Volume Weighted Average Price)
    
    Args:
        df: DataFrame with 'close' and 'volume' columns
    
    Returns:
        Current VWAP value
    """
    if df is None or df.empty or len(df) < 2:
        return 0.0
    
    try:
        # Calculate VWAP: sum(price * volume) / sum(volume)
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).sum() / df['volume'].sum()
        return float(vwap)
    except Exception as e:
        print(f"Error calculating VWAP: {e}")
        return 0.0


def get_current_prices_and_changes(watchlist: List[str]) -> List[Dict]:
    """
    Get current prices, 24h % changes, RSI, VP data, and Rolling VWAP for all coins in watchlist
    
    Args:
        watchlist: List of coin symbols
    
    Returns:
        List of dictionaries with coin data for table display
    """
    table_data = []
    
    for coin in watchlist:
        try:
            # Fetch 24h data for price change, RSI, and 1d RVWAP
            df_24h = api_client.fetch_24h_price_data(coin)
            
            if df_24h is not None and not df_24h.empty:
                first_price = df_24h.iloc[0]['close']
                current_price = df_24h.iloc[-1]['close']
                pct_change = ((current_price - first_price) / first_price) * 100
                
                # Calculate RSI (from 5-min candles)
                rsi = calculate_rsi(df_24h['close'], period=14)
                
                # Calculate 1-day Rolling VWAP
                rvwap_1d = calculate_rolling_vwap(df_24h)
                if rvwap_1d > 0:
                    rvwap_1d_distance = ((current_price - rvwap_1d) / rvwap_1d) * 100
                else:
                    rvwap_1d_distance = 0.0
                
                # Fetch 7-day data for Volume Profile and 7d RVWAP
                df_7d = api_client.fetch_7day_price_data(coin)
                
                if df_7d is not None and not df_7d.empty:
                    # Calculate Volume Profile
                    vp = calculate_volume_profile(df_7d)
                    val = vp.get('val')
                    
                    # Calculate distance to VAL
                    if val and val > 0:
                        val_distance = ((current_price - val) / val) * 100
                    else:
                        val_distance = 0.0
                    
                    # Calculate 7-day Rolling VWAP
                    rvwap_7d = calculate_rolling_vwap(df_7d)
                    if rvwap_7d > 0:
                        rvwap_7d_distance = ((current_price - rvwap_7d) / rvwap_7d) * 100
                    else:
                        rvwap_7d_distance = 0.0
                    
                    # Calculate price position in 7-day range (0-100%)
                    price_7d_high = df_7d['high'].max()
                    price_7d_low = df_7d['low'].min()
                    if price_7d_high > price_7d_low:
                        price_position = ((current_price - price_7d_low) / (price_7d_high - price_7d_low)) * 100
                    else:
                        price_position = 50.0  # Default to middle if no range
                else:
                    val_distance = 0.0
                    rvwap_7d_distance = 0.0
                    price_position = 50.0
                
                table_data.append({
                    'coin': coin,
                    'price': current_price,
                    'change_24h': pct_change,
                    'rsi': rsi,
                    'val_distance': val_distance,
                    'rvwap_1d_distance': rvwap_1d_distance,
                    'rvwap_7d_distance': rvwap_7d_distance,
                    'price_position': price_position
                })
            else:
                # Fallback: just get current price
                price = api_client.fetch_current_price(coin)
                table_data.append({
                    'coin': coin,
                    'price': price if price else 0.0,
                    'change_24h': 0.0,
                    'rsi': 50.0,
                    'val_distance': 0.0,
                    'rvwap_1d_distance': 0.0,
                    'rvwap_7d_distance': 0.0,
                    'price_position': 50.0
                })
        
        except Exception as e:
            print(f"Error processing {coin}: {e}")
            table_data.append({
                'coin': coin,
                'price': 0.0,
                'change_24h': 0.0,
                'rsi': 50.0,
                'val_distance': 0.0,
                'rvwap_1d_distance': 0.0,
                'rvwap_7d_distance': 0.0,
                'price_position': 50.0
            })
    
    return table_data


def create_mock_data_for_testing(coin: str) -> pd.DataFrame:
    """
    Create mock 24h data for testing UI without API calls
    
    Args:
        coin: Coin symbol
    
    Returns:
        DataFrame with mock price data
    """
    import numpy as np
    
    # Create 96 timestamps (24h of 15-min candles)
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=24)
    timestamps = pd.date_range(start=start_time, end=end_time, periods=96)
    
    # Generate random walk prices
    np.random.seed(hash(coin) % 2**32)  # Seed based on coin name
    base_price = np.random.uniform(0.1, 50000)  # Random base price
    returns = np.random.normal(0, 0.02, 96)  # Random returns
    prices = base_price * np.exp(np.cumsum(returns))
    
    df = pd.DataFrame({
        'timestamp': timestamps,
        'open': prices,
        'high': prices * 1.01,
        'low': prices * 0.99,
        'close': prices,
        'volume': np.random.uniform(1000, 100000, 96)
    })
    
    return df

