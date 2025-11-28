#!/usr/bin/env python3
"""
NiftyBot Live Monitor
Real-time monitoring dashboard for NiftyBot trading activity
"""

import os
import time
import datetime
from collections import deque

def clear_screen():
    """Clear terminal screen"""
    os.system('clear' if os.name != 'nt' else 'cls')

def parse_log_file(log_file='niftybot.log', tail_lines=100):
    """Parse log file and extract key information"""
    if not os.path.exists(log_file):
        return None

    try:
        with open(log_file, 'r') as f:
            lines = deque(f, maxlen=tail_lines)

        data = {
            'day_type': 'UNKNOWN',
            'trades': [],
            'positions': [],
            'pnl': 0.0,
            'trade_count': 0,
            'last_signal': None,
            'status': 'RUNNING',
            'last_update': None
        }

        for line in lines:
            # Extract day type
            if 'Day type detected:' in line or 'Day type changed:' in line:
                if 'TRENDING' in line:
                    data['day_type'] = 'TRENDING'
                elif 'SIDEWAYS' in line:
                    data['day_type'] = 'SIDEWAYS'

            # Extract signals
            if 'Signal:' in line:
                parts = line.split('Signal:')[1].strip()
                data['last_signal'] = parts

            # Extract positions
            if 'Position added:' in line:
                parts = line.split('Position added:')[1].strip()
                data['positions'].append(parts)

            # Extract closed positions
            if 'Position closed:' in line:
                parts = line.split('Position closed:')[1].strip()
                data['trades'].append(parts)
                if 'P&L:' in parts:
                    pnl_str = parts.split('P&L:')[1].strip()
                    try:
                        data['pnl'] += float(pnl_str)
                    except:
                        pass

            # Count trades
            if 'Order placed: BUY' in line:
                data['trade_count'] += 1

            # Check bot status
            if 'Bot stopped' in line or 'Daily loss limit' in line or 'Market closed' in line:
                data['status'] = 'STOPPED'

            # Last update
            if line.strip():
                try:
                    timestamp = line.split(' - ')[0]
                    data['last_update'] = timestamp
                except:
                    pass

        return data

    except Exception as e:
        return None

def display_dashboard(data):
    """Display monitoring dashboard"""
    clear_screen()

    print("═" * 80)
    print("  🤖 NIFTYBOT LIVE MONITOR  ".center(80))
    print("═" * 80)
    print()

    if data is None:
        print("❌ Unable to read log file. Make sure bot is running.")
        print("   Log file: niftybot.log")
        return

    # Status section
    status_emoji = "🟢" if data['status'] == 'RUNNING' else "🔴"
    print(f"{status_emoji} Status: {data['status']}")
    print(f"🕐 Last Update: {data['last_update'] if data['last_update'] else 'N/A'}")
    print()

    # Market mode
    mode_emoji = "📈" if data['day_type'] == 'TRENDING' else "↔️" if data['day_type'] == 'SIDEWAYS' else "❓"
    print("─" * 80)
    print(f"MARKET MODE")
    print("─" * 80)
    print(f"{mode_emoji} {data['day_type']}")
    print()

    # Trading summary
    print("─" * 80)
    print("TRADING SUMMARY")
    print("─" * 80)
    print(f"Trades Today: {data['trade_count']}/5")
    print(f"Open Positions: {len(data['positions'])}")
    pnl_emoji = "💰" if data['pnl'] > 0 else "📉" if data['pnl'] < 0 else "➖"
    print(f"{pnl_emoji} Daily P&L: ₹{data['pnl']:.2f}")
    print()

    # Open positions
    if data['positions']:
        print("─" * 80)
        print("OPEN POSITIONS")
        print("─" * 80)
        for i, pos in enumerate(data['positions'][-5:], 1):  # Last 5 positions
            print(f"{i}. {pos}")
        print()

    # Recent trades
    if data['trades']:
        print("─" * 80)
        print("RECENT CLOSED TRADES")
        print("─" * 80)
        for i, trade in enumerate(data['trades'][-5:], 1):  # Last 5 trades
            print(f"{i}. {trade}")
        print()

    # Last signal
    if data['last_signal']:
        print("─" * 80)
        print("LAST SIGNAL")
        print("─" * 80)
        print(f"📊 {data['last_signal']}")
        print()

    print("═" * 80)
    print("Press Ctrl+C to exit monitor | Refreshing every 5 seconds...")
    print("═" * 80)

def main():
    """Main monitoring loop"""
    print("Starting NiftyBot Monitor...")
    print("Reading from: niftybot.log")
    print()

    try:
        while True:
            data = parse_log_file()
            display_dashboard(data)
            time.sleep(5)  # Refresh every 5 seconds

    except KeyboardInterrupt:
        clear_screen()
        print("\n👋 Monitor stopped.")
        print()

if __name__ == "__main__":
    main()
