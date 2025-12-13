#!/usr/bin/env python3
"""
TRADE JOURNAL - EXCEL EXPORT
Automatically track all trades in an Excel file for easy review and analysis

Features:
- Auto-creates Excel file in trades/ folder
- Tracks entry/exit for each trade
- Records reasons, P&L, timestamps
- Updates in real-time as trades happen
- Separate sheets for paper and live trading
- Daily summaries
"""

import datetime
import os
import pandas as pd
from pathlib import Path
from typing import Dict, Optional
from common.logger import setup_logger


class TradeJournal:
    """
    Track all trades in Excel format for easy review.
    
    Creates Excel file: trades/trade_journal_YYYY-MM.xlsx
    Separate sheets: Live Trades, Paper Trades, Daily Summary
    """
    
    def __init__(self, mode='LIVE'):
        """
        Initialize trade journal.
        
        Args:
            mode: 'LIVE' or 'PAPER'
        """
        self.logger = setup_logger("JOURNAL")
        self.mode = mode
        
        # Create trades directory if it doesn't exist
        self.trades_dir = Path('/home/user/NiftyBot/trades')
        self.trades_dir.mkdir(exist_ok=True)
        
        # Generate filename with current month
        current_month = datetime.datetime.now().strftime('%Y-%m')
        self.excel_file = self.trades_dir / f'trade_journal_{current_month}.xlsx'
        
        # Initialize data structures
        self.trades = []
        self.daily_summary = []
        
        # Load existing data if file exists
        self._load_existing_journal()
        
        self.logger.info(f"Trade journal initialized: {self.excel_file}")
    
    def _load_existing_journal(self):
        """Load existing journal data if file exists."""
        if self.excel_file.exists():
            try:
                # Load existing trades
                sheet_name = f'{self.mode}_Trades'
                df = pd.read_excel(self.excel_file, sheet_name=sheet_name)
                self.trades = df.to_dict('records')
                self.logger.info(f"Loaded {len(self.trades)} existing trades from journal")
            except Exception as e:
                self.logger.warning(f"Could not load existing journal: {e}")
                self.trades = []
    
    def log_entry(self, 
                  bot_name: str,
                  symbol: str,
                  direction: str,
                  entry_price: float,
                  quantity: int,
                  entry_reason: str,
                  stop_loss: float,
                  target: Optional[float] = None,
                  spot_price: Optional[float] = None,
                  adx: Optional[float] = None,
                  supertrend: Optional[str] = None):
        """
        Log trade entry.
        
        Args:
            bot_name: Bot that took the trade (NIFTYBOT, BANKNIFTYBOT)
            symbol: Option symbol (e.g., NIFTY25D1625800CE)
            direction: BUY_CE or BUY_PE
            entry_price: Entry premium
            quantity: Lot size
            entry_reason: Why trade was taken
            stop_loss: Stop loss price
            target: Target price (optional)
            spot_price: Underlying spot price
            adx: ADX value at entry
            supertrend: Supertrend direction
        """
        trade = {
            'Entry Date': datetime.datetime.now().strftime('%Y-%m-%d'),
            'Entry Time': datetime.datetime.now().strftime('%H:%M:%S'),
            'Bot': bot_name,
            'Symbol': symbol,
            'Direction': direction,
            'Entry Price': entry_price,
            'Quantity': quantity,
            'Investment': entry_price * quantity,
            'Stop Loss': stop_loss,
            'Target': target if target else '',
            'Entry Reason': entry_reason,
            'Spot Price': spot_price if spot_price else '',
            'ADX': adx if adx else '',
            'Supertrend': supertrend if supertrend else '',
            'Exit Date': '',
            'Exit Time': '',
            'Exit Price': '',
            'Exit Reason': '',
            'P&L': '',
            'P&L %': '',
            'Return %': '',
            'Duration (min)': '',
            'Status': 'OPEN'
        }
        
        self.trades.append(trade)
        self._save_to_excel()
        
        self.logger.info(f"📝 Logged entry: {symbol} @ ₹{entry_price:.2f}")
    
    def log_exit(self,
                 symbol: str,
                 exit_price: float,
                 exit_reason: str,
                 pnl: float = None):
        """
        Log trade exit.
        
        Args:
            symbol: Option symbol
            exit_price: Exit premium
            exit_reason: Why trade was exited
            pnl: Profit/Loss (calculated if not provided)
        """
        # Find the open trade with this symbol
        for trade in reversed(self.trades):
            if trade['Symbol'] == symbol and trade['Status'] == 'OPEN':
                # Update exit details
                exit_time = datetime.datetime.now()
                trade['Exit Date'] = exit_time.strftime('%Y-%m-%d')
                trade['Exit Time'] = exit_time.strftime('%H:%M:%S')
                trade['Exit Price'] = exit_price
                trade['Exit Reason'] = exit_reason
                
                # Calculate P&L if not provided
                if pnl is None:
                    pnl = (exit_price - trade['Entry Price']) * trade['Quantity']
                
                trade['P&L'] = pnl
                trade['P&L %'] = ((exit_price - trade['Entry Price']) / trade['Entry Price']) * 100
                trade['Return %'] = (pnl / trade['Investment']) * 100
                
                # Calculate duration
                entry_datetime = datetime.datetime.strptime(
                    f"{trade['Entry Date']} {trade['Entry Time']}", 
                    '%Y-%m-%d %H:%M:%S'
                )
                duration_minutes = (exit_time - entry_datetime).total_seconds() / 60
                trade['Duration (min)'] = int(duration_minutes)
                
                trade['Status'] = 'CLOSED'
                
                self._save_to_excel()
                self._update_daily_summary()
                
                self.logger.info(
                    f"📝 Logged exit: {symbol} @ ₹{exit_price:.2f} | "
                    f"P&L: ₹{pnl:,.0f} ({trade['P&L %']:+.2f}%)"
                )
                return
        
        self.logger.warning(f"Could not find open trade for {symbol}")
    
    def _save_to_excel(self):
        """Save journal to Excel file."""
        try:
            df_trades = pd.DataFrame(self.trades)
            
            # Create Excel writer
            with pd.ExcelWriter(self.excel_file, engine='openpyxl') as writer:
                # Write trades to appropriate sheet
                sheet_name = f'{self.mode}_Trades'
                df_trades.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Auto-adjust column widths
                worksheet = writer.sheets[sheet_name]
                for column in worksheet.columns:
                    max_length = 0
                    column = list(column)
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
                
                # Add daily summary if we have closed trades
                if self.daily_summary:
                    df_summary = pd.DataFrame(self.daily_summary)
                    df_summary.to_excel(writer, sheet_name='Daily_Summary', index=False)
            
            self.logger.debug(f"Journal saved: {self.excel_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save journal: {e}")
    
    def _update_daily_summary(self):
        """Update daily summary statistics."""
        df = pd.DataFrame(self.trades)
        
        # Filter only closed trades
        closed_trades = df[df['Status'] == 'CLOSED'].copy()
        
        if closed_trades.empty:
            return
        
        # Group by date
        summary = closed_trades.groupby('Entry Date').agg({
            'P&L': ['sum', 'mean', 'count'],
            'P&L %': 'mean',
            'Duration (min)': 'mean'
        }).reset_index()
        
        summary.columns = ['Date', 'Total P&L', 'Avg P&L', 'Trades', 'Avg P&L %', 'Avg Duration']
        
        # Calculate win rate per day
        wins_by_date = closed_trades[closed_trades['P&L'] > 0].groupby('Entry Date').size()
        summary['Wins'] = summary['Date'].map(wins_by_date).fillna(0).astype(int)
        summary['Win Rate %'] = (summary['Wins'] / summary['Trades'] * 100).round(1)
        
        self.daily_summary = summary.to_dict('records')
    
    def get_stats(self) -> Dict:
        """Get trading statistics."""
        df = pd.DataFrame(self.trades)
        closed = df[df['Status'] == 'CLOSED']
        
        if closed.empty:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'best_trade': 0,
                'worst_trade': 0
            }
        
        wins = closed[closed['P&L'] > 0]
        
        return {
            'total_trades': len(closed),
            'open_trades': len(df[df['Status'] == 'OPEN']),
            'win_rate': len(wins) / len(closed) * 100,
            'total_pnl': closed['P&L'].sum(),
            'avg_pnl': closed['P&L'].mean(),
            'best_trade': closed['P&L'].max(),
            'worst_trade': closed['P&L'].min(),
            'avg_duration': closed['Duration (min)'].mean()
        }
    
    def print_summary(self):
        """Print trading summary."""
        stats = self.get_stats()
        
        print("\n" + "="*60)
        print(f"TRADE JOURNAL SUMMARY ({self.mode} MODE)")
        print("="*60)
        print(f"Excel File: {self.excel_file}")
        print(f"\nTotal Trades: {stats['total_trades']}")
        print(f"Open Trades: {stats['open_trades']}")
        print(f"Win Rate: {stats['win_rate']:.1f}%")
        print(f"Total P&L: ₹{stats['total_pnl']:,.0f}")
        print(f"Avg P&L: ₹{stats['avg_pnl']:,.0f}")
        print(f"Best Trade: ₹{stats['best_trade']:,.0f}")
        print(f"Worst Trade: ₹{stats['worst_trade']:,.0f}")
        if stats['avg_duration']:
            print(f"Avg Duration: {stats['avg_duration']:.0f} minutes")
        print("="*60 + "\n")


# Global journal instances (initialized when needed)
_live_journal = None
_paper_journal = None


def get_journal(mode='LIVE') -> TradeJournal:
    """Get or create trade journal instance."""
    global _live_journal, _paper_journal
    
    if mode == 'PAPER':
        if _paper_journal is None:
            _paper_journal = TradeJournal(mode='PAPER')
        return _paper_journal
    else:
        if _live_journal is None:
            _live_journal = TradeJournal(mode='LIVE')
        return _live_journal


if __name__ == "__main__":
    # Test the journal
    journal = TradeJournal(mode='PAPER')
    
    # Simulate a trade
    journal.log_entry(
        bot_name='NIFTYBOT',
        symbol='NIFTY25D1625800CE',
        direction='BUY_CE',
        entry_price=200.0,
        quantity=200,
        entry_reason='VWAP+ST+ADX confluence',
        stop_loss=160.0,
        target=280.0,
        spot_price=25800.0,
        adx=35.5,
        supertrend='Bullish'
    )
    
    # Simulate exit
    journal.log_exit(
        symbol='NIFTY25D1625800CE',
        exit_price=250.0,
        exit_reason='Target hit',
        pnl=10000
    )
    
    journal.print_summary()
    print(f"\n✅ Journal created: {journal.excel_file}")
