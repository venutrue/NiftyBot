# Technical Stop-Loss Implementation for Options Trading
# Uses option premium candle structure (not spot) for entry SL

def calculate_entry_stop_loss(
    entry_premium: float,
    option_candles: list,
    option_type: str  # 'CE' or 'PE'
) -> tuple:
    """
    Calculate stop-loss using recent OPTION PREMIUM price action.

    SIMPLE RULE:
    - For CE: SL = Lowest low of last 2 option premium candles
    - For PE: SL = Highest high of last 2 option premium candles
    - Safety caps: 10% minimum, 20% maximum

    This tracks the OPTION's own structure, not spot movement.

    Args:
        entry_premium: Option entry price (₹)
        option_candles: Recent option OHLC candles (5-min)
                       Each candle has: {'high': float, 'low': float, 'close': float}
        option_type: 'CE' or 'PE'

    Returns:
        (stop_loss_price, sl_percentage, reason)

    Example:
        Entry: ₹454 (BANKNIFTY PE)
        Last 2 candles: [{'low': 445, ...}, {'low': 440, ...}]
        Technical SL: ₹440 (lowest low)
        SL%: (454-440)/454 = 3.1% → capped to 10% minimum
        Final SL: ₹408.60 (10% from entry)
    """
    # Safety caps
    MIN_SL_PERCENT = 0.10  # Never tighter than 10%
    MAX_SL_PERCENT = 0.20  # Never wider than 20%

    # Fallback if insufficient data
    if not option_candles or len(option_candles) < 2:
        sl_price = entry_premium * (1 - 0.15)
        return (sl_price, 0.15, "Insufficient option candles, using 15% default")

    # Get last 2 candles
    last_candle = option_candles[-1]
    prev_candle = option_candles[-2]

    # Calculate technical stop from option premium structure
    if option_type == 'CE':
        # For Call: Use lowest low of last 2 premium candles
        # If option premium breaks below this, exit
        technical_sl_price = min(last_candle['low'], prev_candle['low'])

    else:  # 'PE'
        # For Put: Use highest high of last 2 premium candles
        # If option premium breaks above this, exit
        technical_sl_price = max(last_candle['high'], prev_candle['high'])

    # Calculate SL percentage
    if entry_premium > 0:
        technical_sl_pct = abs(entry_premium - technical_sl_price) / entry_premium
    else:
        # Should never happen, but safety fallback
        technical_sl_pct = 0.15

    # Apply safety caps
    capped_sl_pct = max(MIN_SL_PERCENT, min(technical_sl_pct, MAX_SL_PERCENT))

    # Calculate final SL price using capped percentage
    sl_price = entry_premium * (1 - capped_sl_pct)

    # Generate reason
    if technical_sl_pct < MIN_SL_PERCENT:
        reason = f"Technical SL too tight ({technical_sl_pct:.1%}), using {MIN_SL_PERCENT:.0%} minimum"
    elif technical_sl_pct > MAX_SL_PERCENT:
        reason = f"Technical SL too wide ({technical_sl_pct:.1%}), capped at {MAX_SL_PERCENT:.0%}"
    else:
        reason = f"Using technical SL from option structure (₹{technical_sl_price:.2f}, {capped_sl_pct:.1%})"

    return (sl_price, capped_sl_pct, reason)


# Example Usage
if __name__ == "__main__":
    # Simulate your BANKNIFTY PE trade using OPTION PREMIUM candles
    # These are the actual option premium candles (not spot candles)
    option_candles = [
        {'high': 460, 'low': 445, 'close': 450},  # 2 candles ago
        {'high': 458, 'low': 440, 'close': 454},  # 1 candle ago (entry candle)
    ]

    entry_premium = 454.00
    option_type = 'PE'

    sl_price, sl_pct, reason = calculate_entry_stop_loss(
        entry_premium, option_candles, option_type
    )

    print(f"Entry: ₹{entry_premium} (BANKNIFTY PE)")
    print(f"Stop-Loss: ₹{sl_price:.2f} ({sl_pct:.1%})")
    print(f"Reason: {reason}")
    print()
    print("Exit if option premium breaks key level")
    print(f"Old SL (10%): ₹{entry_premium * 0.9:.2f}")
    print(f"New SL ({sl_pct:.1%}): ₹{sl_price:.2f}")

    # Test what would have happened in your actual trade
    print("\n" + "="*60)
    print("Your Actual Trade Analysis:")
    print("="*60)

    # Your actual trade log
    old_sl_10pct = 408.60  # 10% SL
    actual_exit = 403.70
    recovered_to = 419.05
    position_size = 75  # lots

    print(f"\nWith 10% SL (₹{old_sl_10pct:.2f}):")
    print(f"  - Stopped out at ₹{actual_exit} ❌")
    print(f"  - Loss: ₹{(entry_premium - actual_exit) * position_size:,.0f}")

    print(f"\nWith 15% SL (₹{entry_premium * 0.85:.2f}) - NEW DEFAULT:")
    new_sl_15pct = entry_premium * 0.85
    if actual_exit < new_sl_15pct:
        print(f"  - Would ALSO be stopped out ❌")
        print(f"  - Loss: ₹{(entry_premium - new_sl_15pct) * position_size:,.0f}")
    else:
        print(f"  - Would HOLD through dip ✓")
        print(f"  - When recovered to ₹{recovered_to}:")
        print(f"  - Profit/Loss: ₹{(recovered_to - entry_premium) * position_size:,.0f}")

    print(f"\nWith Technical SL (₹{sl_price:.2f}):")
    if actual_exit < sl_price:
        print(f"  - Would ALSO be stopped out ❌")
        print(f"  - Loss: ₹{(entry_premium - sl_price) * position_size:,.0f}")
    else:
        print(f"  - Would HOLD through dip ✓")
        print(f"  - When recovered to ₹{recovered_to}:")
        print(f"  - Profit/Loss: ₹{(recovered_to - entry_premium) * position_size:,.0f}")

    print("\n" + "="*60)
    print("Conclusion: Need 3-4 months backtest to validate approach")
    print("="*60)
