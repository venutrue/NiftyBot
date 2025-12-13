# 📊 Trade Journal - Excel Export System

The trading bot automatically exports all trades to an **Excel file** for easy review, analysis, and record-keeping. No more scrolling through logs!

---

## 📁 Where are the Excel Files?

All trade journals are saved in:
```
/home/user/NiftyBot/trades/
```

Filename format: `trade_journal_YYYY-MM.xlsx` (one file per month)

Example: `trade_journal_2025-12.xlsx`

---

## 📋 What's Included?

Each Excel file contains **two sheets**:

### 1. LIVE_Trades / PAPER_Trades Sheet

Every trade entry and exit with complete details:

| Column | Description |
|--------|-------------|
| **Entry Date** | Date when trade was taken |
| **Entry Time** | Time when trade was taken  |
| **Bot** | Which bot took the trade (NIFTYBOT, BANKNIFTYBOT) |
| **Symbol** | Option symbol (e.g., NIFTY25D1625800CE) |
| **Direction** | BUY_CE or BUY_PE |
| **Entry Price** | Premium at entry |
| **Quantity** | Lot size |
| **Investment** | Total capital deployed (Entry Price × Quantity) |
| **Stop Loss** | SL price |
| **Target** | Target price (if set) |
| **Entry Reason** | Why trade was taken (e.g., "VWAP+ST+ADX confluence") |
| **Spot Price** | Underlying spot price at entry |
| **ADX** | ADX value at entry |
| **Supertrend** | Supertrend direction at entry |
| **Exit Date** | Date when trade was closed |
| **Exit Time** | Time when trade was closed |
| **Exit Price** | Premium at exit |
| **Exit Reason** | Why trade was exited (e.g., "Target hit", "Stop loss") |
| **P&L** | Profit/Loss in rupees |
| **P&L %** | Profit/Loss percentage |
| **Return %** | Return on investment |
| **Duration (min)** | How long trade was held |
| **Status** | OPEN or CLOSED |

### 2. Daily_Summary Sheet

Daily statistics aggregated from all closed trades:

| Column | Description |
|--------|-------------|
| **Date** | Trading date |
| **Total P&L** | Total profit/loss for the day |
| **Avg P&L** | Average profit/loss per trade |
| **Trades** | Number of trades taken |
| **Avg P&L %** | Average profit/loss percentage |
| **Avg Duration** | Average trade duration in minutes |
| **Wins** | Number of winning trades |
| **Win Rate %** | Percentage of winning trades |

---

## 🎯 How It Works

### Automatic Logging

The journal is **completely automatic**:

1. **Trade Entry** → Automatically logged when position opens
2. **Trade Exit** → Automatically updated when position closes
3. **Excel File** → Updates in real-time

No manual intervention needed!

### Paper vs Live Trading

- **Paper Trading**: Creates `PAPER_Trades` sheet
- **Live Trading**: Creates `LIVE_Trades` sheet

Both modes create separate Excel files for easy comparison.

---

## 📊 Using the Excel File

### Review Your Trades

1. Open Excel file in `/home/user/NiftyBot/trades/`
2. Navigate to `LIVE_Trades` or `PAPER_Trades` sheet
3. Sort, filter, analyze as needed

### Find Patterns

**Example Analyses:**
- Filter by Exit Reason to see most common stops
- Sort by P&L% to find best/worst trades
- Filter by Bot to compare NIFTY vs BANKNIFTY
- Check Entry Reason to see which setups work best
- Analyze Duration to optimize holding periods

### Daily Review

Check the `Daily_Summary` sheet to:
- Track daily performance
- Monitor win rate trends
- Identify best/worst trading days
- Calculate monthly totals

---

## 💡 Examples

### Finding Your Best Setups

1. Open Excel → Filter by `Exit Reason` = "Target hit"
2. Check `Entry Reason` column
3. See which entry patterns hit targets most often

### Analyzing Losses

1. Filter trades where `P&L` < 0
2. Check `Exit Reason` to see why they failed
3. Review `Entry Reason` to spot patterns

### Comparing Bots

1. Use Excel pivot tables
2. Group by `Bot` column
3. Compare win rates, avg P&L, etc.

---

## 🔧 Advanced Usage

### Monthly Reports

Each month gets its own file, making it easy to:
- Compare month-over-month performance
- Archive old trading records
- Share specific months with advisors

### Custom Analysis

The Excel format lets you:
- Create pivot tables
- Build charts and graphs
- Calculate custom metrics
- Export to other tools

### Backup & Archiving

Simply copy the `trades/` folder to backup all your trading history.

---

## 📝 Installation Requirements

The trade journal requires these Python packages:

```bash
# Install dependencies
pip install pandas openpyxl
```

These are included in `requirements.txt`, so if you've run:
```bash
pip install -r requirements.txt
```

You're all set!

---

## 🐛 Troubleshooting

### "No such file or directory: trades/"

The folder is created automatically on first trade. If missing:
```bash
mkdir /home/user/NiftyBot/trades
```

### "Permission denied" when opening Excel

Make sure the file isn't already open in another program.

### Excel file not updating

- Check logs for errors
- Verify openpyxl is installed: `pip list | grep openpyxl`
- Restart the bot if needed

---

## ✅ Benefits

### vs. Log Files
- ✅ Easy to read and analyze
- ✅ Sortable and filterable
- ✅ Can create charts
- ✅ Share with others easily

### vs. Manual Tracking
- ✅ 100% automatic
- ✅ Never miss a trade
- ✅ Exact entry/exit prices
- ✅ Accurate P&L calculation

### Record Keeping
- ✅ Perfect for tax purposes
- ✅ Track historical performance
- ✅ Identify strategy weaknesses
- ✅ Demonstrate profitability

---

## 🎓 Best Practices

1. **Review Daily** - Check the Daily_Summary sheet every evening
2. **Analyze Weekly** - Look for patterns in winning/losing trades
3. **Backup Monthly** - Copy the trades/ folder to backup
4. **Archive Yearly** - Move old files to archive folder
5. **Never Edit Manually** - Let the bot update automatically

---

**The trade journal is your trading diary. Review it regularly to improve your strategy!** 📈
