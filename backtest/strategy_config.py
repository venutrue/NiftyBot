"""
STRATEGY CONFIGURATION SYSTEM
Easy tweaking of all strategy parameters for experimentation

Allows you to:
- Modify indicator parameters (ADX, Supertrend, VWAP)
- Adjust entry/exit conditions
- Tweak position sizing and risk management
- Create custom strategy presets

Usage:
    # Use a preset
    config = StrategyConfig.conservative()

    # Or customize everything
    config = StrategyConfig()
    config.adx_threshold = 25
    config.supertrend_period = 12
    config.stop_loss_percent = 0.15
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass
class StrategyConfig:
    """
    Complete strategy configuration for backtesting and live trading.

    All parameters are exposed and tweakable to help you find patterns
    that work in the market.
    """

    # ========================================
    # INDICATOR PARAMETERS
    # ========================================

    # ADX (Average Directional Index) - Trend strength
    adx_period: int = 14                    # Lookback period for ADX calculation
    adx_threshold: float = 23.0             # Minimum ADX for trend detection (higher = stronger trend required)

    # Supertrend - Trend direction
    supertrend_period: int = 10             # ATR period for Supertrend
    supertrend_multiplier: float = 2.0      # ATR multiplier (higher = fewer signals)

    # VWAP (Volume Weighted Average Price) - Smart money detection
    vwap_buffer_percent: float = 0.002      # 0.2% buffer above/below VWAP for signals

    # Volume analysis
    volume_surge_threshold: float = 1.5     # Volume must be X times average (1.5 = 50% above avg)
    volume_lookback_period: int = 20        # Period for average volume calculation

    # ========================================
    # ENTRY CONDITIONS
    # ========================================

    # Time filters
    entry_start_hour: int = 9               # Start taking entries (IST)
    entry_start_minute: int = 20            # Start taking entries (IST)
    entry_cutoff_hour: int = 14             # Stop taking entries (IST)
    entry_cutoff_minute: int = 30           # Stop taking entries (IST)

    # Option selection
    trade_atm_only: bool = True             # Only trade ATM strikes (recommended for beginners)
    scan_strikes_range: int = 2             # Scan ATM ± N strikes for analysis

    # Signal confirmation (set to True for stronger signals, fewer trades)
    require_volume_confirmation: bool = True    # Require volume surge for entry
    require_vwap_confirmation: bool = True      # Require price above VWAP (for CE) or below (for PE)

    # ========================================
    # EXIT CONDITIONS
    # ========================================

    # Stop loss and target
    stop_loss_percent: float = 0.20         # 20% stop loss from entry
    target_percent: float = 0.40            # 40% target from entry (2:1 R:R)

    # Trailing stop
    enable_trailing_stop: bool = True       # Enable trailing stop after profit threshold
    trailing_stop_activation: float = 0.30  # Activate trailing after 30% profit
    trailing_stop_distance: float = 0.10    # Trail 10% below max price

    # Time-based exit
    exit_at_eod: bool = True                # Exit all positions at end of day
    eod_exit_hour: int = 15                 # End of day exit time (IST)
    eod_exit_minute: int = 15               # End of day exit time (IST)

    # ========================================
    # POSITION SIZING & RISK MANAGEMENT
    # ========================================

    # Capital allocation
    initial_capital: float = 500000         # Starting capital (₹5 Lakh)
    max_risk_per_trade: float = 0.01        # Risk 1% of capital per trade
    max_capital_deployed: float = 0.30      # Max 30% of capital in positions simultaneously

    # Position limits
    max_positions: int = 3                  # Maximum simultaneous positions
    max_daily_loss: float = 0.03            # Stop trading if daily loss exceeds 3%

    # Scaling (for advanced users)
    enable_position_scaling: bool = False   # Scale into positions (add to winners)
    scaling_profit_threshold: float = 0.20  # Add to position after 20% profit
    max_scale_ins: int = 1                  # Maximum number of scale-ins

    # ========================================
    # EXECUTION SETTINGS
    # ========================================

    # Slippage and costs
    slippage_percent: float = 0.005         # 0.5% slippage on entries/exits
    commission_per_trade: float = 40        # ₹40 per trade (approx Zerodha)

    # Order types (for live trading)
    use_market_orders: bool = True          # Market orders (immediate) vs limit orders
    limit_order_buffer: float = 0.002       # 0.2% buffer for limit orders

    # ========================================
    # ADVANCED OPTIONS
    # ========================================

    # Re-entry logic
    allow_reentry_same_day: bool = True     # Allow re-entry in same direction same day
    min_time_between_entries: int = 30      # Minimum minutes between entries (same direction)

    # Correlation filter (future enhancement)
    check_nifty_bank_correlation: bool = False  # Avoid simultaneous NIFTY+BANKNIFTY trades

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return asdict(self)

    def __str__(self) -> str:
        """Pretty print configuration."""
        lines = ["STRATEGY CONFIGURATION", "=" * 80]

        for key, value in self.to_dict().items():
            # Format key nicely
            formatted_key = key.replace('_', ' ').title()
            lines.append(f"{formatted_key:.<50} {value}")

        lines.append("=" * 80)
        return "\n".join(lines)

    @classmethod
    def conservative(cls) -> 'StrategyConfig':
        """
        Conservative preset - Lower risk, higher quality signals.

        Characteristics:
        - Higher ADX threshold (stronger trends only)
        - Tighter stop loss (15%)
        - Smaller position sizes (0.5% risk)
        - Requires volume confirmation
        - Max 2 positions
        """
        config = cls()
        config.adx_threshold = 28.0
        config.stop_loss_percent = 0.15
        config.target_percent = 0.30
        config.max_risk_per_trade = 0.005
        config.max_positions = 2
        config.require_volume_confirmation = True
        config.require_vwap_confirmation = True
        config.volume_surge_threshold = 2.0
        return config

    @classmethod
    def balanced(cls) -> 'StrategyConfig':
        """
        Balanced preset - Default settings, good starting point.

        Characteristics:
        - Moderate ADX threshold (23)
        - Standard stop loss (20%)
        - 1% risk per trade
        - Max 3 positions
        - Basic confirmations
        """
        return cls()  # Default values

    @classmethod
    def aggressive(cls) -> 'StrategyConfig':
        """
        Aggressive preset - Higher risk, more trades.

        Characteristics:
        - Lower ADX threshold (20)
        - Wider stop loss (25%)
        - Larger position sizes (1.5% risk)
        - More positions allowed (5)
        - Fewer confirmations required
        """
        config = cls()
        config.adx_threshold = 20.0
        config.stop_loss_percent = 0.25
        config.target_percent = 0.50
        config.max_risk_per_trade = 0.015
        config.max_positions = 5
        config.require_volume_confirmation = False
        config.allow_reentry_same_day = True
        return config

    @classmethod
    def scalper(cls) -> 'StrategyConfig':
        """
        Scalper preset - Quick in and out, tight stops.

        Characteristics:
        - Lower trend requirement
        - Very tight stop loss (10%)
        - Smaller targets (15%)
        - Quick exits
        - Multiple positions
        """
        config = cls()
        config.adx_threshold = 18.0
        config.stop_loss_percent = 0.10
        config.target_percent = 0.15
        config.max_risk_per_trade = 0.008
        config.max_positions = 4
        config.enable_trailing_stop = False
        config.require_volume_confirmation = False
        return config

    @classmethod
    def trend_follower(cls) -> 'StrategyConfig':
        """
        Trend follower preset - Ride big moves with trailing stops.

        Characteristics:
        - High ADX requirement (strong trends only)
        - Wider stop loss (30%)
        - Large targets (60%)
        - Aggressive trailing stops
        - Fewer positions
        """
        config = cls()
        config.adx_threshold = 30.0
        config.stop_loss_percent = 0.30
        config.target_percent = 0.60
        config.max_positions = 2
        config.enable_trailing_stop = True
        config.trailing_stop_activation = 0.25
        config.trailing_stop_distance = 0.15
        config.require_volume_confirmation = True
        return config


class StrategyLibrary:
    """
    Library of proven strategy configurations.

    Load, save, and share strategy configurations.
    """

    PRESETS = {
        'conservative': StrategyConfig.conservative,
        'balanced': StrategyConfig.balanced,
        'aggressive': StrategyConfig.aggressive,
        'scalper': StrategyConfig.scalper,
        'trend_follower': StrategyConfig.trend_follower,
    }

    @staticmethod
    def list_presets():
        """List all available presets."""
        print("\nAVAILABLE STRATEGY PRESETS:")
        print("=" * 80)
        for name, func in StrategyLibrary.PRESETS.items():
            config = func()
            print(f"\n{name.upper()}")
            print(f"  ADX Threshold: {config.adx_threshold}")
            print(f"  Stop Loss: {config.stop_loss_percent * 100:.0f}%")
            print(f"  Target: {config.target_percent * 100:.0f}%")
            print(f"  Risk/Trade: {config.max_risk_per_trade * 100:.2f}%")
            print(f"  Max Positions: {config.max_positions}")
        print("=" * 80 + "\n")

    @staticmethod
    def load(name: str) -> StrategyConfig:
        """Load a preset by name."""
        if name.lower() not in StrategyLibrary.PRESETS:
            raise ValueError(
                f"Unknown preset '{name}'. "
                f"Available: {', '.join(StrategyLibrary.PRESETS.keys())}"
            )
        return StrategyLibrary.PRESETS[name.lower()]()

    @staticmethod
    def compare_presets():
        """Compare all presets side-by-side."""
        print("\nPRESET COMPARISON:")
        print("=" * 120)

        headers = ["Preset", "ADX", "Stop Loss", "Target", "Risk/Trade", "Max Pos", "Trailing"]
        print(f"{headers[0]:<15} {headers[1]:<8} {headers[2]:<10} {headers[3]:<10} "
              f"{headers[4]:<12} {headers[5]:<8} {headers[6]:<10}")
        print("-" * 120)

        for name, func in StrategyLibrary.PRESETS.items():
            config = func()
            print(
                f"{name:<15} "
                f"{config.adx_threshold:<8.1f} "
                f"{config.stop_loss_percent*100:<10.0f}% "
                f"{config.target_percent*100:<10.0f}% "
                f"{config.max_risk_per_trade*100:<12.2f}% "
                f"{config.max_positions:<8} "
                f"{'Yes' if config.enable_trailing_stop else 'No':<10}"
            )

        print("=" * 120 + "\n")


if __name__ == "__main__":
    # Demo
    print("\n" + "=" * 80)
    print("STRATEGY CONFIGURATION SYSTEM DEMO")
    print("=" * 80 + "\n")

    # List all presets
    StrategyLibrary.list_presets()

    # Compare presets
    StrategyLibrary.compare_presets()

    # Show detailed configuration
    print("\nDETAILED BALANCED PRESET:")
    balanced = StrategyConfig.balanced()
    print(balanced)

    # Custom configuration example
    print("\n\nCUSTOM CONFIGURATION EXAMPLE:")
    print("=" * 80)
    custom = StrategyConfig()
    custom.adx_threshold = 25
    custom.stop_loss_percent = 0.18
    custom.target_percent = 0.35
    custom.max_risk_per_trade = 0.012
    print(f"ADX Threshold: {custom.adx_threshold}")
    print(f"Stop Loss: {custom.stop_loss_percent * 100:.0f}%")
    print(f"Target: {custom.target_percent * 100:.0f}%")
    print(f"Risk per Trade: {custom.max_risk_per_trade * 100:.2f}%")
    print("=" * 80 + "\n")
