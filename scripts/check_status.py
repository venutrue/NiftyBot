#!/usr/bin/env python3
"""
Quick status check for live trading system
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.risk_manager import RiskManager
from live_trading_config import LIVE_TRADING_ENABLED, PAPER_TRADING_ENABLED, print_config_summary

def main():
    """Print system status."""
    # Print config
    print_config_summary()

    # Check risk manager state
    print("\n" + "=" * 70)
    print("RISK MANAGER STATUS")
    print("=" * 70)

    try:
        risk_mgr = RiskManager()
        summary = risk_mgr.get_risk_summary()

        print(f"\n🚦 STATUS:")
        if summary['kill_switch_active']:
            print("  🔴 KILL SWITCH ACTIVE")
        elif summary['circuit_breaker_active']:
            print(f"  🟡 CIRCUIT BREAKER ACTIVE (until {summary['cool_off_until']})")
        elif summary['trading_enabled']:
            print("  🟢 TRADING ENABLED")
        else:
            print("  🔴 TRADING DISABLED")

        print(f"\n📊 TODAY:")
        print(f"  P&L: ₹{summary['daily']['pnl']:,.0f}")
        print(f"  Trades: {summary['daily']['trades']}")
        print(f"  Win Rate: {summary['daily']['winners']}/{summary['daily']['trades']}")
        print(f"  Consecutive Losses: {summary['daily']['consecutive_losses']}")
        print(f"  Open Positions: {summary['daily']['open_positions']}")
        print(f"  Capital Deployed: ₹{summary['daily']['capital_deployed']:,.0f}")

        print(f"\n📅 THIS WEEK:")
        print(f"  P&L: ₹{summary['weekly']['pnl']:,.0f}")
        print(f"  Trades: {summary['weekly']['trades']}")

        if summary['blocked_symbols']:
            print(f"\n🚫 BLOCKED SYMBOLS:")
            for symbol, unblock_time in summary['blocked_symbols'].items():
                print(f"  {symbol}: until {unblock_time}")

        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error loading risk manager: {e}")
        print("   (This is normal if never run before)")

if __name__ == "__main__":
    main()
