#!/usr/bin/env python3
"""
NiftyBot Control Panel
Manual control and monitoring for live positions
"""

import os
from kiteconnect import KiteConnect

# Configuration
API_KEY = os.getenv("KITE_API_KEY", "your_api_key")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN", "your_access_token")

try:
    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
except Exception as e:
    print(f"❌ Failed to connect to Kite API: {e}")
    print("Make sure your .env file is configured correctly.")
    exit(1)

def show_positions():
    """Display all open positions"""
    try:
        positions = kite.positions()

        print("\n" + "═" * 80)
        print("  📊 CURRENT POSITIONS  ".center(80))
        print("═" * 80)

        day_positions = positions.get('day', [])

        if not day_positions:
            print("\n✅ No open positions")
            return

        total_pnl = 0

        for i, pos in enumerate(day_positions, 1):
            if pos['quantity'] == 0:
                continue

            symbol = pos['tradingsymbol']
            qty = pos['quantity']
            avg_price = pos['average_price']
            ltp = pos['last_price']
            pnl = pos['pnl']
            total_pnl += pnl

            pnl_emoji = "💰" if pnl > 0 else "📉" if pnl < 0 else "➖"

            print(f"\n{i}. {symbol}")
            print(f"   Qty: {qty} | Avg Price: ₹{avg_price:.2f} | LTP: ₹{ltp:.2f}")
            print(f"   {pnl_emoji} P&L: ₹{pnl:.2f}")

        print("\n" + "─" * 80)
        total_emoji = "💰" if total_pnl > 0 else "📉" if total_pnl < 0 else "➖"
        print(f"{total_emoji} Total P&L: ₹{total_pnl:.2f}")
        print("═" * 80)

    except Exception as e:
        print(f"❌ Error fetching positions: {e}")

def show_orders():
    """Display today's orders"""
    try:
        orders = kite.orders()

        print("\n" + "═" * 80)
        print("  📋 TODAY'S ORDERS  ".center(80))
        print("═" * 80)

        if not orders:
            print("\n✅ No orders today")
            return

        for i, order in enumerate(orders[-10:], 1):  # Last 10 orders
            symbol = order['tradingsymbol']
            side = order['transaction_type']
            qty = order['quantity']
            status = order['status']
            order_type = order['order_type']
            price = order.get('average_price', 0)

            status_emoji = "✅" if status == "COMPLETE" else "⏳" if status == "OPEN" else "❌"
            side_emoji = "📈" if side == "BUY" else "📉"

            print(f"\n{i}. {side_emoji} {side} {qty} {symbol}")
            print(f"   Type: {order_type} | {status_emoji} {status}", end="")
            if price > 0:
                print(f" | Price: ₹{price:.2f}")
            else:
                print()

        print("\n" + "═" * 80)

    except Exception as e:
        print(f"❌ Error fetching orders: {e}")

def close_all_positions():
    """Close all open positions"""
    try:
        positions = kite.positions()
        day_positions = positions.get('day', [])

        closed_count = 0

        for pos in day_positions:
            if pos['quantity'] == 0:
                continue

            symbol = pos['tradingsymbol']
            qty = abs(pos['quantity'])
            side = "SELL" if pos['quantity'] > 0 else "BUY"

            try:
                order_id = kite.place_order(
                    tradingsymbol=symbol,
                    exchange=pos['exchange'],
                    transaction_type=side,
                    quantity=qty,
                    order_type="MARKET",
                    product=pos['product']
                )
                print(f"✅ Closed position: {symbol} (Order ID: {order_id})")
                closed_count += 1
            except Exception as e:
                print(f"❌ Failed to close {symbol}: {e}")

        if closed_count > 0:
            print(f"\n✅ Successfully closed {closed_count} position(s)")
        else:
            print("\n✅ No positions to close")

    except Exception as e:
        print(f"❌ Error closing positions: {e}")

def show_account_summary():
    """Display account summary"""
    try:
        margins = kite.margins()
        equity = margins.get('equity', {})

        print("\n" + "═" * 80)
        print("  💼 ACCOUNT SUMMARY  ".center(80))
        print("═" * 80)

        available = equity.get('available', {}).get('live_balance', 0)
        utilized = equity.get('utilised', {}).get('debits', 0)

        print(f"\nAvailable Balance: ₹{available:,.2f}")
        print(f"Utilized Margin: ₹{utilized:,.2f}")

        print("\n" + "═" * 80)

    except Exception as e:
        print(f"❌ Error fetching account info: {e}")

def main_menu():
    """Display main control menu"""
    while True:
        print("\n" + "═" * 80)
        print("  🎮 NIFTYBOT CONTROL PANEL  ".center(80))
        print("═" * 80)
        print("\n1. View Open Positions")
        print("2. View Today's Orders")
        print("3. View Account Summary")
        print("4. Close All Positions (EMERGENCY)")
        print("5. Exit")
        print("\n" + "─" * 80)

        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == '1':
            show_positions()
        elif choice == '2':
            show_orders()
        elif choice == '3':
            show_account_summary()
        elif choice == '4':
            confirm = input("\n⚠️  Close ALL positions? This will override the bot! (yes/no): ").strip().lower()
            if confirm == 'yes':
                close_all_positions()
            else:
                print("❌ Cancelled")
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("\n❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    print("Connecting to Zerodha Kite...")
    try:
        profile = kite.profile()
        print(f"✅ Connected as: {profile.get('user_name', 'Unknown')}")
    except Exception as e:
        print(f"❌ Failed to authenticate: {e}")
        exit(1)

    main_menu()
