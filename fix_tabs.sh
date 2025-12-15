#!/bin/bash
# Fix TabError in trade_journal.py by getting clean version from repo

echo "Creating backup..."
cp executor/trade_journal.py executor/trade_journal.py.backup 2>/dev/null

echo "Getting clean version from repository..."
git checkout origin/main -- executor/trade_journal.py

echo "Verifying no tabs remain..."
if grep -q $'\t' executor/trade_journal.py; then
    echo "❌ Still has tabs! Converting them..."
    python3 -c "
import sys
with open('executor/trade_journal.py', 'r') as f:
    content = f.read()
with open('executor/trade_journal.py', 'w') as f:
    f.write(content.expandtabs(4))
"
    echo "✅ Tabs converted to spaces"
else
    echo "✅ File is clean - no tabs found"
fi

echo ""
echo "Checking indentation..."
python3 -m py_compile executor/trade_journal.py && echo "✅ File compiles successfully!" || echo "❌ Still has issues"
