#!/usr/bin/env python3
"""
Reset daily statistics (run at start of trading day)
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.risk_manager import RiskManager
from common.logger import log_system

def main():
    """Reset daily stats."""
    print("\n" + "=" * 70)
    print("RESET DAILY STATISTICS")
    print("=" * 70)

    print("\n⚠️  This will reset:")
    print("  - Daily P&L to ₹0")
    print("  - Daily trade count to 0")
    print("  - Consecutive loss counter to 0")
    print("  - Bot trade counters to 0")
    print("\n✅ This will KEEP:")
    print("  - Weekly P&L")
    print("  - Trade history")
    print("  - Blocked symbols")
    print("  - Circuit breaker status (if active)")

    print("\n⚠️  Only run this at the START of a new trading day!")
    print("\nType 'RESET' to confirm: ", end='')

    confirmation = input().strip()

    if confirmation != "RESET":
        print("\n❌ Reset cancelled")
        return 0

    try:
        risk_mgr = RiskManager()

        # Show current stats before reset
        summary = risk_mgr.get_risk_summary()
        print(f"\n📊 Current Daily Stats:")
        print(f"  P&L: ₹{summary['daily']['pnl']:,.0f}")
        print(f"  Trades: {summary['daily']['trades']}")
        print(f"  Consecutive Losses: {summary['daily']['consecutive_losses']}")

        # Reset
        risk_mgr.reset_daily_stats()

        print("\n✅ Daily statistics reset")
        print("\nYou can now start fresh for today.")

        # Show new stats
        summary = risk_mgr.get_risk_summary()
        print(f"\n📊 New Daily Stats:")
        print(f"  P&L: ₹{summary['daily']['pnl']:,.0f}")
        print(f"  Trades: {summary['daily']['trades']}")
        print(f"  Consecutive Losses: {summary['daily']['consecutive_losses']}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    print("=" * 70 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
