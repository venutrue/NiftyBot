#!/bin/bash
# Stop-Loss Comparison Script
# Runs 4 backtests to compare different SL strategies

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                    STOP-LOSS STRATEGY COMPARISON                           ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "This will run 4 backtests to compare stop-loss strategies:"
echo "  1. Fixed 10% SL"
echo "  2. Fixed 15% SL (Current Default)"
echo "  3. Fixed 20% SL"
echo "  4. Technical SL (Option Candle Structure)"
echo ""
echo "Estimated time: 10-15 minutes"
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Configuration
BOT="${1:-NIFTYBOT}"  # Default to NIFTYBOT, or use first argument
DAYS="${2:-90}"       # Default to 90 days, or use second argument
CAPITAL=500000

echo ""
echo "Configuration:"
echo "  Bot: $BOT"
echo "  Period: $DAYS days"
echo "  Capital: ₹$CAPITAL"
echo ""

# Test 1: Fixed 10% SL
echo "═══════════════════════════════════════════════════════════════════════════"
echo "TEST 1/4: Fixed 10% SL (Original Setting)"
echo "═══════════════════════════════════════════════════════════════════════════"
python run_backtest.py \
  --bot "$BOT" \
  --days "$DAYS" \
  --capital "$CAPITAL" \
  --strategy custom \
  --stop-loss 0.10 \
  --sl-method fixed \
  > /tmp/sl_test_10pct.log 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Test 1 complete"
    tail -n 30 /tmp/sl_test_10pct.log | grep -A 20 "PERFORMANCE SUMMARY" || echo "See /tmp/sl_test_10pct.log for details"
else
    echo "✗ Test 1 failed - see /tmp/sl_test_10pct.log for errors"
fi

echo ""

# Test 2: Fixed 15% SL
echo "═══════════════════════════════════════════════════════════════════════════"
echo "TEST 2/4: Fixed 15% SL (NEW DEFAULT)"
echo "═══════════════════════════════════════════════════════════════════════════"
python run_backtest.py \
  --bot "$BOT" \
  --days "$DAYS" \
  --capital "$CAPITAL" \
  --strategy custom \
  --stop-loss 0.15 \
  --sl-method fixed \
  > /tmp/sl_test_15pct.log 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Test 2 complete"
    tail -n 30 /tmp/sl_test_15pct.log | grep -A 20 "PERFORMANCE SUMMARY" || echo "See /tmp/sl_test_15pct.log for details"
else
    echo "✗ Test 2 failed - see /tmp/sl_test_15pct.log for errors"
fi

echo ""

# Test 3: Fixed 20% SL
echo "═══════════════════════════════════════════════════════════════════════════"
echo "TEST 3/4: Fixed 20% SL (Original Backtest Setting)"
echo "═══════════════════════════════════════════════════════════════════════════"
python run_backtest.py \
  --bot "$BOT" \
  --days "$DAYS" \
  --capital "$CAPITAL" \
  --strategy custom \
  --stop-loss 0.20 \
  --sl-method fixed \
  > /tmp/sl_test_20pct.log 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Test 3 complete"
    tail -n 30 /tmp/sl_test_20pct.log | grep -A 20 "PERFORMANCE SUMMARY" || echo "See /tmp/sl_test_20pct.log for details"
else
    echo "✗ Test 3 failed - see /tmp/sl_test_20pct.log for errors"
fi

echo ""

# Test 4: Technical SL
echo "═══════════════════════════════════════════════════════════════════════════"
echo "TEST 4/4: Technical SL (Option Candle Structure)"
echo "═══════════════════════════════════════════════════════════════════════════"
python run_backtest.py \
  --bot "$BOT" \
  --days "$DAYS" \
  --capital "$CAPITAL" \
  --strategy custom \
  --sl-method technical \
  > /tmp/sl_test_technical.log 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Test 4 complete"
    tail -n 30 /tmp/sl_test_technical.log | grep -A 20 "PERFORMANCE SUMMARY" || echo "See /tmp/sl_test_technical.log for details"
else
    echo "✗ Test 4 failed - see /tmp/sl_test_technical.log for errors"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                          ALL TESTS COMPLETE!                               ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Results saved to:"
echo "  - /tmp/sl_test_10pct.log (Fixed 10%)"
echo "  - /tmp/sl_test_15pct.log (Fixed 15%)"
echo "  - /tmp/sl_test_20pct.log (Fixed 20%)"
echo "  - /tmp/sl_test_technical.log (Technical)"
echo ""
echo "To compare results:"
echo "  grep -A 15 'PERFORMANCE SUMMARY' /tmp/sl_test_*.log"
echo ""
echo "Look for:"
echo "  • Highest Total P&L"
echo "  • Best Profit Factor (>1.5)"
echo "  • Best Sharpe Ratio (>1.0)"
echo "  • Lowest Max Drawdown"
echo ""
echo "Next steps:"
echo "  1. Review the metrics above"
echo "  2. Choose the best SL strategy"
echo "  3. Paper trade for 2-4 weeks before going live"
echo ""
