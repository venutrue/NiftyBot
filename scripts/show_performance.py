#!/usr/bin/env python3
"""
Show trading performance summary
"""

import sys
import os
import argparse
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.risk_manager import RiskManager
from executor.paper_trading import PaperTradingEngine
from live_trading_config import PAPER_TRADING_ENABLED

def show_live_performance():
    """Show live trading performance."""
    try:
        risk_mgr = RiskManager()
        summary = risk_mgr.get_risk_summary()

        print("\n" + "=" * 70)
        print("LIVE TRADING PERFORMANCE")
        print("=" * 70)

        # Daily stats
        print(f"\n📊 TODAY ({datetime.now().strftime('%Y-%m-%d')}):")
        daily = summary['daily']
        print(f"  P&L: ₹{daily['pnl']:,.0f}")
        print(f"  Trades: {daily['trades']}")
        if daily['trades'] > 0:
            win_rate = (daily['winners'] / daily['trades']) * 100
            print(f"  Winners: {daily['winners']} ({win_rate:.1f}%)")
            print(f"  Losers: {daily['losers']}")
        print(f"  Consecutive Losses: {daily['consecutive_losses']}")
        print(f"  Open Positions: {daily['open_positions']}")

        # Weekly stats
        print(f"\n📅 THIS WEEK:")
        weekly = summary['weekly']
        print(f"  P&L: ₹{weekly['pnl']:,.0f}")
        print(f"  Trades: {weekly['trades']}")

        # Recent trades
        if risk_mgr.trade_history:
            print(f"\n📜 RECENT TRADES:")
            print("-" * 70)
            for trade in list(risk_mgr.trade_history)[-10:]:
                print(
                    f"{trade.timestamp.strftime('%m-%d %H:%M')} | "
                    f"{trade.symbol:20s} | "
                    f"₹{trade.pnl:8,.0f} ({trade.pnl_percent:+6.1f}%) | "
                    f"{trade.reason}"
                )

        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   (Run bot at least once to generate data)")

def show_paper_performance():
    """Show paper trading performance."""
    try:
        paper = PaperTradingEngine()
        paper.print_summary()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("   (Run paper trading at least once)")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Show trading performance')
    parser.add_argument('--mode', choices=['live', 'paper', 'auto'], default='auto',
                        help='Which performance to show')
    args = parser.parse_args()

    if args.mode == 'paper' or (args.mode == 'auto' and PAPER_TRADING_ENABLED):
        show_paper_performance()
    else:
        show_live_performance()

if __name__ == "__main__":
    main()
