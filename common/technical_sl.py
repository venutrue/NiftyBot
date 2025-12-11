# Technical Stop-Loss Implementation for Options Trading
# Uses recent candle structure for entry SL, with percentage safety caps

def calculate_entry_stop_loss(
    entry_premium: float,
    entry_spot: float,
    spot_candles: list,
    option_type: str  # 'CE' or 'PE'
) -> tuple:
    """
    Calculate stop-loss using recent price action (last 1-2 candles).

    Logic:
    1. For CE: Use lowest low of last 2 candles (spot support)
    2. For PE: Use highest high of last 2 candles (spot resistance)
    3. Convert spot distance to option premium SL
    4. Cap between 10-20% (safety limits)

    Args:
        entry_premium: Option entry price (₹)
        entry_spot: Spot price at entry
        spot_candles: Recent spot OHLC candles (5-min)
        option_type: 'CE' or 'PE'

    Returns:
        (stop_loss_price, stop_loss_spot, sl_percentage, reason)

    Example:
        For CE entry at spot 59,300:
        - Last 2 candles: low1=59,250, low2=59,220
        - Technical SL: 59,220 (80 points buffer)
        - If spot < 59,220, exit CE
    """
    # Safety caps (percentage-based limits)
    MIN_SL_PERCENT = 0.10  # Never tighter than 10%
    MAX_SL_PERCENT = 0.20  # Never wider than 20%

    # Get last 2 candles (most recent price action)
    if len(spot_candles) < 2:
        # Fallback: use default 15% if not enough data
        sl_price = entry_premium * (1 - 0.15)
        return (sl_price, None, 0.15, "Insufficient candles, using 15% default")

    last_candle = spot_candles[-1]
    prev_candle = spot_candles[-2]

    # Calculate technical stop based on option type
    if option_type == 'CE':
        # For Call: Use lowest low of last 2 candles
        # If spot breaks this support, exit the call
        technical_sl_spot = min(last_candle['low'], prev_candle['low'])
        spot_distance = entry_spot - technical_sl_spot

    else:  # 'PE'
        # For Put: Use highest high of last 2 candles
        # If spot breaks this resistance, exit the put
        technical_sl_spot = max(last_candle['high'], prev_candle['high'])
        spot_distance = technical_sl_spot - entry_spot

    # Convert spot distance to option premium distance
    # ATM options have delta ~0.5, so they move ~50% of spot movement
    # Adjust based on moneyness:
    # - ITM options (delta ~0.7): multiply by 0.7
    # - ATM options (delta ~0.5): multiply by 0.5
    # - OTM options (delta ~0.3): multiply by 0.3
    # For simplicity, use 0.5 (ATM assumption)

    delta_estimate = 0.5  # ATM options
    spot_distance_pct = spot_distance / entry_spot
    technical_sl_pct = spot_distance_pct * delta_estimate

    # Apply safety caps
    capped_sl_pct = max(MIN_SL_PERCENT, min(technical_sl_pct, MAX_SL_PERCENT))

    # Calculate final SL price
    sl_price = entry_premium * (1 - capped_sl_pct)

    # Determine what happened
    if technical_sl_pct < MIN_SL_PERCENT:
        reason = f"Technical SL too tight ({technical_sl_pct:.1%}), using minimum {MIN_SL_PERCENT:.0%}"
    elif technical_sl_pct > MAX_SL_PERCENT:
        reason = f"Technical SL too wide ({technical_sl_pct:.1%}), capped at {MAX_SL_PERCENT:.0%}"
    else:
        reason = f"Using technical SL from spot structure ({capped_sl_pct:.1%})"

    return (sl_price, technical_sl_spot, capped_sl_pct, reason)


# Example Usage
if __name__ == "__main__":
    # Simulate your BANKNIFTY PE trade
    spot_candles = [
        {'high': 59180, 'low': 59120, 'close': 59150},  # 2 candles ago
        {'high': 59200, 'low': 59140, 'close': 59168},  # 1 candle ago (entry candle)
    ]

    entry_premium = 454.00
    entry_spot = 59168
    option_type = 'PE'

    sl_price, sl_spot, sl_pct, reason = calculate_entry_stop_loss(
        entry_premium, entry_spot, spot_candles, option_type
    )

    print(f"Entry: ₹{entry_premium} @ spot {entry_spot}")
    print(f"Stop-Loss: ₹{sl_price:.2f} ({sl_pct:.1%})")
    print(f"Spot SL: {sl_spot} (if spot breaks this level)")
    print(f"Reason: {reason}")
    print()
    print("For PE: Exit if spot breaks above", sl_spot)
    print(f"Old SL (10%): ₹{entry_premium * 0.9:.2f}")
    print(f"New SL ({sl_pct:.1%}): ₹{sl_price:.2f}")

    # Test what would have happened
    print("\n" + "="*60)
    print("What would have happened in your trade:")
    print("="*60)

    # Your actual trade
    old_sl = 407.75
    actual_exit = 403.70
    recovered_to = 419.05

    print(f"With 10% SL (₹{old_sl}):")
    print(f"  - Stopped out at ₹{actual_exit} ❌")
    print(f"  - Loss: ₹{(entry_premium - actual_exit) * 75:,.0f}")

    print(f"\nWith Technical SL (₹{sl_price:.2f}):")
    if sl_price < actual_exit:
        print(f"  - Would ALSO be stopped out ❌")
        print(f"  - Loss: ₹{(entry_premium - sl_price) * 75:,.0f}")
    else:
        print(f"  - Would HOLD through dip ✓")
        print(f"  - When recovered to ₹{recovered_to}:")
        print(f"  - Loss: ₹{(entry_premium - recovered_to) * 75:,.0f} (50% better!)")
