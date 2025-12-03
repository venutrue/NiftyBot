#!/bin/bash
##############################################
# Start Gold Paper Trading
# Test Gold futures strategy with fake money
##############################################

echo "========================================"
echo "🥇 STARTING GOLD PAPER TRADING MODE"
echo "========================================"
echo ""
echo "💰 Starting Capital: ₹2,00,000"
echo "📊 Commodity: MCX Gold Mini (100 grams)"
echo "⏰ Trading Hours: 9 AM - 11:30 PM"
echo "🎯 This is FAKE MONEY - no risk!"
echo ""
echo "Strategy:"
echo "  📈 Timeframe: 15-minute candles"
echo "  🎯 Indicators: Supertrend + ADX + EMA"
echo "  🛡️ Stop Loss: ₹250 per contract"
echo "  📊 Max Trades: 2 per day"
echo ""
echo "What this does:"
echo "  ✅ Generates real Gold futures signals"
echo "  ✅ Uses real MCX Gold prices"
echo "  ✅ Simulates order execution"
echo "  ✅ Tracks P&L and performance"
echo "  ❌ NO real money at risk"
echo ""
echo "⚠️  IMPORTANT:"
echo "  - Verify symbol format works with Zerodha MCX"
echo "  - Check if you have MCX data subscription"
echo "  - Paper trade for 2-4 weeks before going live"
echo ""
echo "Press Ctrl+C to stop trading"
echo ""
read -p "Start Gold paper trading? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Starting GoldBot..."
    python3 run.py --paper --bot gold
else
    echo "Cancelled"
fi
