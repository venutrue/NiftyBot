#!/usr/bin/env python3
"""
EMERGENCY: Exit all positions immediately
"""

import sys
import os
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.trade_executor import TradeExecutor
from executor.risk_manager import RiskManager
from common.logger import setup_logger

def main():
    """Emergency exit all positions."""
    parser = argparse.ArgumentParser(description='Emergency exit positions')
    parser.add_argument('--symbol', help='Exit specific symbol')
    parser.add_argument('--all', action='store_true', help='Exit all positions')
    args = parser.parse_args()

    if not args.symbol and not args.all:
        print("\nUsage:")
        print("  Exit specific: python emergency_exit.py --symbol NIFTY24500CE")
        print("  Exit all:      python emergency_exit.py --all")
        return 1

    logger = setup_logger("EMERGENCY")

    print("\n" + "=" * 70)
    print("🚨 EMERGENCY EXIT")
    print("=" * 70)

    try:
        # Get risk manager
        risk_mgr = RiskManager()
        open_positions = risk_mgr.open_positions

        if not open_positions:
            print("\n✅ No open positions to exit")
            return 0

        print(f"\n📋 Open Positions: {len(open_positions)}")
        for symbol, pos in open_positions.items():
            print(f"  {symbol}: {pos['quantity']} lots @ ₹{pos['entry_price']:.2f}")

        # Get symbols to exit
        if args.all:
            symbols_to_exit = list(open_positions.keys())
            print(f"\n⚠️  Will exit ALL {len(symbols_to_exit)} positions")
        else:
            if args.symbol not in open_positions:
                print(f"\n❌ No open position for {args.symbol}")
                return 1
            symbols_to_exit = [args.symbol]
            print(f"\n⚠️  Will exit {args.symbol}")

        print("\nType 'EXIT' to confirm: ", end='')
        confirmation = input().strip()

        if confirmation != "EXIT":
            print("\n❌ Exit cancelled")
            return 0

        print("\n🚨 Exiting positions...")

        # Connect to executor
        executor = TradeExecutor()
        if not executor.connect():
            print("\n❌ Failed to connect to broker")
            print("   Exit positions manually via Kite app!")
            return 1

        # Exit each position
        for symbol in symbols_to_exit:
            print(f"\n  Exiting {symbol}...", end='')
            try:
                order_id = executor.exit_position(symbol, reason="EMERGENCY_EXIT")
                if order_id:
                    print(f" ✅ Order placed: {order_id}")

                    # Get fill price (wait a moment for order to execute)
                    import time
                    time.sleep(2)
                    order_history = executor.get_order_history(order_id)
                    if order_history and order_history.get('status') == 'COMPLETE':
                        exit_price = order_history.get('average_price', 0)
                        risk_mgr.register_trade_exit(symbol, exit_price, "EMERGENCY_EXIT")
                        print(f"    Filled @ ₹{exit_price:.2f}")
                else:
                    print(" ❌ Failed")
                    print(f"    Exit {symbol} manually via Kite!")

            except Exception as e:
                print(f" ❌ Error: {e}")
                print(f"    Exit {symbol} manually via Kite!")

        print("\n✅ Emergency exit complete")
        print("\nNext steps:")
        print("1. Verify all positions closed in Kite")
        print("2. Review what went wrong")
        print("3. Consider activating kill switch")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n⚠️  EXIT POSITIONS MANUALLY VIA KITE APP!")
        return 1

    print("=" * 70 + "\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
