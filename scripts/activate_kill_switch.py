#!/usr/bin/env python3
"""
EMERGENCY: Activate kill switch to stop all trading
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.risk_manager import RiskManager

def main():
    """Activate kill switch."""
    print("\n" + "=" * 70)
    print("🚨 KILL SWITCH ACTIVATION")
    print("=" * 70)
    print("\nThis will IMMEDIATELY stop all trading.")
    print("Existing positions will need to be closed manually.")
    print("\nAre you sure? (type 'YES' to confirm): ", end='')

    confirmation = input().strip()

    if confirmation != "YES":
        print("\n❌ Kill switch NOT activated")
        return

    reason = input("\nReason for activation: ").strip()
    if not reason:
        reason = "Manual emergency stop"

    print("\n🚨 Activating kill switch...")

    try:
        risk_mgr = RiskManager()
        risk_mgr.activate_kill_switch(reason)

        print("\n✅ KILL SWITCH ACTIVATED")
        print(f"   Reason: {reason}")
        print("\n⚠️  TRADING IS NOW DISABLED")
        print("\nNext steps:")
        print("1. Close all open positions manually via Kite")
        print("2. Review what went wrong")
        print("3. Fix any issues")
        print("4. Only reactivate when confident")
        print("\nTo reactivate:")
        print("  python scripts/deactivate_kill_switch.py")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1

    print("=" * 70 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
