#!/usr/bin/env python3
"""
Debug script to verify actual market prices for NIFTY options on Dec 9, 2025.
This will help confirm if the bot captured the correct instrument and prices.
"""

import datetime
import pandas as pd
from kiteconnect import KiteConnect
from common.config import API_KEY, ACCESS_TOKEN

def main():
    print("=" * 80)
    print("NIFTY OPTION PRICE VERIFICATION - December 9, 2025")
    print("=" * 80)

    # Connect to Kite
    kite = KiteConnect(api_key=API_KEY)
    kite.set_access_token(ACCESS_TOKEN)
    print("✓ Connected to Kite\n")

    # Get NFO instruments
    instruments = kite.instruments("NFO")
    print(f"✓ Loaded {len(instruments)} NFO instruments\n")

    # Find NIFTY 25DEC expiry options around 25800 strike
    target_expiry = datetime.date(2025, 12, 25)  # Weekly expiry
    strikes_to_check = [25700, 25750, 25800, 25850, 25900]

    print(f"Target Expiry: {target_expiry}")
    print(f"Strikes to check: {strikes_to_check}")
    print("\n" + "-" * 80)

    # Find instruments
    option_instruments = {}
    for inst in instruments:
        if (inst['name'] == 'NIFTY' and
            inst['instrument_type'] == 'CE' and
            inst['expiry'] == target_expiry and
            inst['strike'] in strikes_to_check):
            option_instruments[inst['strike']] = inst
            print(f"Found: {inst['tradingsymbol']} | Strike: {inst['strike']} | Token: {inst['instrument_token']}")

    if not option_instruments:
        print("\n❌ ERROR: No instruments found for target expiry")
        return

    # Focus on 25800 CE
    if 25800 not in option_instruments:
        print("\n❌ ERROR: 25800 CE not found!")
        return

    atm_instrument = option_instruments[25800]
    print(f"\n" + "=" * 80)
    print(f"ANALYZING: {atm_instrument['tradingsymbol']}")
    print(f"Token: {atm_instrument['instrument_token']}")
    print("=" * 80 + "\n")

    # Fetch historical data for Dec 9, 2025
    target_date = datetime.date(2025, 12, 9)
    from_datetime = datetime.datetime.combine(target_date, datetime.time(9, 15))
    to_datetime = datetime.datetime.combine(target_date, datetime.time(15, 30))

    print(f"Fetching data from {from_datetime} to {to_datetime}...")

    try:
        historical_data = kite.historical_data(
            instrument_token=atm_instrument['instrument_token'],
            from_date=from_datetime,
            to_date=to_datetime,
            interval="minute"
        )

        if not historical_data:
            print("❌ No historical data available")
            return

        df = pd.DataFrame(historical_data)
        print(f"✓ Retrieved {len(df)} minute candles\n")

        # Check the specific time: 11:01 AM
        target_time = datetime.datetime(2025, 12, 9, 11, 1)

        # Find the closest candle to 11:01 AM
        df['time_diff'] = abs((df['date'] - target_time).dt.total_seconds())
        closest_idx = df['time_diff'].idxmin()
        closest_candle = df.loc[closest_idx]

        print("=" * 80)
        print(f"DATA AT ~11:01 AM (Bot Entry Time)")
        print("=" * 80)
        print(f"Timestamp: {closest_candle['date']}")
        print(f"Open:      ₹{closest_candle['open']:.2f}")
        print(f"High:      ₹{closest_candle['high']:.2f}")
        print(f"Low:       ₹{closest_candle['low']:.2f}")
        print(f"Close:     ₹{closest_candle['close']:.2f}")
        print(f"Volume:    {closest_candle['volume']:.0f}")
        print("\n" + "=" * 80)
        print(f"BOT CLAIMED PREMIUM: ₹333.85")
        print(f"ACTUAL CLOSE PRICE:  ₹{closest_candle['close']:.2f}")

        diff = abs(closest_candle['close'] - 333.85)
        diff_pct = (diff / closest_candle['close']) * 100 if closest_candle['close'] > 0 else 0

        if diff < 5:
            print(f"VERDICT: ✓ MATCH (Difference: ₹{diff:.2f}, {diff_pct:.1f}%)")
        elif diff < 20:
            print(f"VERDICT: ⚠ MINOR MISMATCH (Difference: ₹{diff:.2f}, {diff_pct:.1f}%)")
        else:
            print(f"VERDICT: ❌ MAJOR MISMATCH (Difference: ₹{diff:.2f}, {diff_pct:.1f}%)")
        print("=" * 80 + "\n")

        # Show 10:50 - 11:10 range for context
        print("PRICE MOVEMENT AROUND 11:01 AM:")
        print("-" * 80)
        time_window = df[
            (df['date'] >= datetime.datetime(2025, 12, 9, 10, 50)) &
            (df['date'] <= datetime.datetime(2025, 12, 9, 11, 10))
        ]

        if len(time_window) > 0:
            for _, row in time_window.iterrows():
                marker = " ← BOT ENTRY" if row['date'].hour == 11 and row['date'].minute == 1 else ""
                print(f"{row['date'].strftime('%H:%M')} | O: ₹{row['open']:6.2f} | H: ₹{row['high']:6.2f} | "
                      f"L: ₹{row['low']:6.2f} | C: ₹{row['close']:6.2f} | Vol: {row['volume']:5.0f}{marker}")
        else:
            print("No data in time window")

        print("\n" + "=" * 80)
        print("SUMMARY STATISTICS FOR DEC 9, 2025")
        print("=" * 80)
        print(f"Day Open:  ₹{df['open'].iloc[0]:.2f}")
        print(f"Day High:  ₹{df['high'].max():.2f}")
        print(f"Day Low:   ₹{df['low'].min():.2f}")
        print(f"Day Close: ₹{df['close'].iloc[-1]:.2f}")
        print(f"Avg Price: ₹{df['close'].mean():.2f}")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error fetching data: {e}")

if __name__ == "__main__":
    main()
