#!/bin/bash
##############################################
# Start Paper Trading
# Quick command to start paper trading mode
##############################################

echo "========================================"
echo "📄 STARTING PAPER TRADING MODE"
echo "========================================"
echo ""
echo "💰 Starting Capital: ₹2,00,000"
echo "🎯 This is FAKE MONEY - no risk!"
echo ""
echo "What this does:"
echo "  ✅ Generates real trading signals"
echo "  ✅ Uses real market prices"
echo "  ✅ Simulates order execution"
echo "  ✅ Tracks P&L and performance"
echo "  ❌ NO real money at risk"
echo ""
echo "Press Ctrl+C to stop trading"
echo ""
read -p "Start paper trading? (y/n): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]
then
    echo ""
    echo "Starting bots..."
    python3 run.py --paper --bot nifty
else
    echo "Cancelled"
fi
