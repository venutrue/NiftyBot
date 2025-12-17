##############################################
# MARKET REGIME ANALYZER
# Weekly + Daily -> VWAP Bias Matrix
#
# Mental Model:
#   Weekly sets the battlefield
#   Daily sets the rules
#   VWAP executes the trade
#
# If any layer is missing - no trade
##############################################

import datetime
import pandas as pd
import numpy as np
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass
from enum import Enum

from common.logger import setup_logger


class WeeklyTrend(Enum):
    """Weekly market regime classification."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    BALANCED = "balanced"
    UNKNOWN = "unknown"


class DailyPattern(Enum):
    """Daily candle pattern classification."""
    EXPANSION = "expansion"       # Range > average, strong directional move
    INSIDE = "inside"             # Range < previous day, consolidation
    FAILED_BREAKOUT = "failed_breakout"  # Breakout attempt that reversed
    NORMAL = "normal"             # No special pattern
    UNKNOWN = "unknown"


class VWAPStrategy(Enum):
    """VWAP trading strategy based on regime."""
    CONTINUATION = "continuation"      # VWAP pullback continuation trades
    MEAN_REVERSION = "mean_reversion"  # Fade moves away from VWAP
    FADE = "fade"                      # Strong VWAP fades on failed breakouts
    SKIP = "skip"                      # No VWAP trades - unclear edge
    NO_TRADE = "no_trade"              # Avoid trading completely


@dataclass
class MarketRegime:
    """Complete market regime assessment."""
    weekly_trend: WeeklyTrend
    daily_pattern: DailyPattern
    is_event_day: bool
    event_description: str
    vwap_strategy: VWAPStrategy
    trade_quality_score: int  # 0-100, higher is better
    should_trade: bool
    skip_reason: str
    analysis_time: datetime.datetime


class MarketRegimeAnalyzer:
    """
    Analyzes market regime using Weekly + Daily confluence.

    Pre-market checklist (5 minutes):
    1. Weekly trend or balance?
    2. Yesterday: expansion, inside, or failure?
    3. Any event risk today?
    4. Based on above: VWAP continuation? mean reversion? or no VWAP trades?

    If you can't answer clearly -> don't trade.
    Skipping days is part of the strategy.
    """

    # Known event days (RBI policy, major expiries, elections, budget)
    # Format: (month, day) or specific dates
    KNOWN_EVENTS_2025 = [
        # RBI MPC meetings (tentative 2025 dates)
        (2, 5), (2, 6), (2, 7),      # Feb MPC
        (4, 7), (4, 8), (4, 9),      # Apr MPC
        (6, 4), (6, 5), (6, 6),      # Jun MPC
        (8, 6), (8, 7), (8, 8),      # Aug MPC
        (10, 6), (10, 7), (10, 8),   # Oct MPC
        (12, 3), (12, 4), (12, 5),   # Dec MPC
        # Budget day
        (2, 1),
        # Monthly expiry Thursdays are handled dynamically
    ]

    def __init__(self, executor):
        """
        Initialize market regime analyzer.

        Args:
            executor: Trade executor with market data access
        """
        self.executor = executor
        self.logger = setup_logger("REGIME")

        # Cache for daily calculations
        self._weekly_data_cache = None
        self._weekly_cache_date = None
        self._daily_data_cache = None
        self._daily_cache_date = None
        self._regime_cache = None
        self._regime_cache_time = None

    def analyze(self, nifty_token: int, force_refresh: bool = False) -> MarketRegime:
        """
        Perform complete market regime analysis.

        This should be called once at market open (pre-market) and cached.

        Args:
            nifty_token: NIFTY 50 instrument token
            force_refresh: Force recalculation even if cached

        Returns:
            MarketRegime with complete analysis
        """
        now = datetime.datetime.now()
        today = now.date()

        # Use cache if available and fresh (within same trading day, before 9:30 AM refresh)
        if (self._regime_cache is not None and
            self._regime_cache_time is not None and
            self._regime_cache_time.date() == today and
            not force_refresh):
            return self._regime_cache

        self.logger.info("=" * 60)
        self.logger.info("MARKET REGIME ANALYSIS - Pre-Market Checklist")
        self.logger.info("=" * 60)

        # Step 1: Weekly trend analysis
        weekly_trend = self._analyze_weekly_trend(nifty_token)
        self.logger.info(f"1. Weekly Trend: {weekly_trend.value.upper()}")

        # Step 2: Daily pattern analysis (yesterday's candle)
        daily_pattern = self._analyze_daily_pattern(nifty_token)
        self.logger.info(f"2. Yesterday's Pattern: {daily_pattern.value.upper()}")

        # Step 3: Event day check
        is_event_day, event_desc = self._check_event_day(today)
        event_status = f"YES - {event_desc}" if is_event_day else "No"
        self.logger.info(f"3. Event Day: {event_status}")

        # Step 4: Determine VWAP strategy from matrix
        vwap_strategy, should_trade, skip_reason, quality_score = self._apply_bias_matrix(
            weekly_trend, daily_pattern, is_event_day
        )

        self.logger.info("-" * 60)
        self.logger.info(f"4. VWAP Strategy: {vwap_strategy.value.upper()}")
        self.logger.info(f"   Trade Quality Score: {quality_score}/100")
        self.logger.info(f"   Should Trade: {'YES' if should_trade else 'NO'}")
        if not should_trade:
            self.logger.info(f"   Skip Reason: {skip_reason}")
        self.logger.info("=" * 60)

        # Build regime object
        regime = MarketRegime(
            weekly_trend=weekly_trend,
            daily_pattern=daily_pattern,
            is_event_day=is_event_day,
            event_description=event_desc,
            vwap_strategy=vwap_strategy,
            trade_quality_score=quality_score,
            should_trade=should_trade,
            skip_reason=skip_reason,
            analysis_time=now
        )

        # Cache the result
        self._regime_cache = regime
        self._regime_cache_time = now

        return regime

    def _analyze_weekly_trend(self, nifty_token: int) -> WeeklyTrend:
        """
        Analyze weekly trend using price vs weekly VWAP and structure.

        Trending: Price consistently above/below weekly VWAP with directional bias
        Balanced: Price oscillating around weekly VWAP, no clear direction
        """
        try:
            # Fetch last 5 trading days of daily data
            now = datetime.datetime.now()
            from_date = now - datetime.timedelta(days=10)  # Extra days for weekends

            data = self.executor.get_historical_data(
                instrument_token=nifty_token,
                from_date=from_date,
                to_date=now,
                interval="day"
            )

            if not data or len(data) < 5:
                self.logger.warning("Insufficient weekly data for trend analysis")
                return WeeklyTrend.UNKNOWN

            df = pd.DataFrame(data)

            # Use last 5 trading days
            df = df.tail(5)

            # Calculate weekly metrics
            week_high = df['high'].max()
            week_low = df['low'].min()
            week_range = week_high - week_low
            week_midpoint = (week_high + week_low) / 2

            # Current price position
            current_close = df['close'].iloc[-1]
            first_open = df['open'].iloc[0]

            # Calculate weekly change
            weekly_change_pct = ((current_close - first_open) / first_open) * 100

            # Position in weekly range (0 = at low, 1 = at high)
            range_position = (current_close - week_low) / week_range if week_range > 0 else 0.5

            # Count closes above/below midpoint
            closes_above_mid = (df['close'] > week_midpoint).sum()
            closes_below_mid = (df['close'] < week_midpoint).sum()

            # Determine trend
            # Trending Up: Weekly change > 0.5%, price in upper 60% of range, mostly closes above mid
            # Trending Down: Weekly change < -0.5%, price in lower 40% of range, mostly closes below mid
            # Balanced: Everything else

            if weekly_change_pct > 0.5 and range_position > 0.6 and closes_above_mid >= 3:
                trend = WeeklyTrend.TRENDING_UP
            elif weekly_change_pct < -0.5 and range_position < 0.4 and closes_below_mid >= 3:
                trend = WeeklyTrend.TRENDING_DOWN
            else:
                trend = WeeklyTrend.BALANCED

            self.logger.debug(
                f"Weekly Analysis: Change={weekly_change_pct:+.2f}%, "
                f"Range Position={range_position:.2f}, "
                f"Above Mid={closes_above_mid}/5"
            )

            return trend

        except Exception as e:
            self.logger.error(f"Weekly trend analysis failed: {str(e)}")
            return WeeklyTrend.UNKNOWN

    def _analyze_daily_pattern(self, nifty_token: int) -> DailyPattern:
        """
        Analyze yesterday's daily candle pattern.

        Expansion: Range > 1.2x average range, strong directional close
        Inside: Range < previous day's range, close within previous range
        Failed Breakout: Broke previous high/low but closed back inside
        """
        try:
            now = datetime.datetime.now()
            from_date = now - datetime.timedelta(days=15)  # Get enough history

            data = self.executor.get_historical_data(
                instrument_token=nifty_token,
                from_date=from_date,
                to_date=now,
                interval="day"
            )

            if not data or len(data) < 5:
                self.logger.warning("Insufficient daily data for pattern analysis")
                return DailyPattern.UNKNOWN

            df = pd.DataFrame(data)

            # Calculate ranges
            df['range'] = df['high'] - df['low']
            df['body'] = abs(df['close'] - df['open'])

            # Get last few days
            if len(df) < 3:
                return DailyPattern.UNKNOWN

            yesterday = df.iloc[-2]  # Yesterday (most recent complete day)
            day_before = df.iloc[-3]  # Day before yesterday

            # Calculate average range (last 10 days excluding yesterday)
            avg_range = df['range'].iloc[-12:-2].mean() if len(df) >= 12 else df['range'].iloc[:-2].mean()

            yesterday_range = yesterday['range']
            day_before_range = day_before['range']
            day_before_high = day_before['high']
            day_before_low = day_before['low']

            # Pattern detection

            # 1. INSIDE DAY: Yesterday's range contained within day before
            if (yesterday['high'] <= day_before_high and
                yesterday['low'] >= day_before_low):
                self.logger.debug(
                    f"Inside Day: Yesterday H={yesterday['high']:.0f} L={yesterday['low']:.0f} "
                    f"within D-2 H={day_before_high:.0f} L={day_before_low:.0f}"
                )
                return DailyPattern.INSIDE

            # 2. FAILED BREAKOUT: Broke out but closed back inside previous range
            broke_high = yesterday['high'] > day_before_high
            broke_low = yesterday['low'] < day_before_low
            closed_inside = day_before_low <= yesterday['close'] <= day_before_high

            if (broke_high or broke_low) and closed_inside:
                direction = "up" if broke_high else "down"
                self.logger.debug(
                    f"Failed Breakout {direction}: Broke {'high' if broke_high else 'low'} "
                    f"but closed at {yesterday['close']:.0f} inside range"
                )
                return DailyPattern.FAILED_BREAKOUT

            # 3. EXPANSION DAY: Range > 1.2x average with strong directional body
            if yesterday_range > avg_range * 1.2:
                body_ratio = yesterday['body'] / yesterday_range if yesterday_range > 0 else 0
                if body_ratio > 0.5:  # Strong directional candle (body > 50% of range)
                    self.logger.debug(
                        f"Expansion Day: Range={yesterday_range:.0f} > "
                        f"1.2x Avg={avg_range*1.2:.0f}, Body Ratio={body_ratio:.2f}"
                    )
                    return DailyPattern.EXPANSION

            # 4. Default: Normal day
            return DailyPattern.NORMAL

        except Exception as e:
            self.logger.error(f"Daily pattern analysis failed: {str(e)}")
            return DailyPattern.UNKNOWN

    def _check_event_day(self, today: datetime.date) -> Tuple[bool, str]:
        """
        Check if today is a known event day.

        Event days include:
        - RBI MPC meetings
        - Budget day
        - Monthly F&O expiry (last Thursday)
        - Major elections
        """
        # Check known events
        for event_date in self.KNOWN_EVENTS_2025:
            if today.month == event_date[0] and today.day == event_date[1]:
                # Determine event type
                if today.month == 2 and today.day == 1:
                    return True, "Union Budget Day"
                else:
                    return True, "RBI MPC Meeting"

        # Check for monthly expiry (last Thursday of month)
        if self._is_monthly_expiry(today):
            return True, "Monthly F&O Expiry"

        # Check for weekly expiry (every Thursday) - less severe but noteworthy
        if today.weekday() == 3:  # Thursday
            # Weekly expiry is not a full skip, but we note it
            # We'll let the matrix decide the impact
            pass

        return False, ""

    def _is_monthly_expiry(self, today: datetime.date) -> bool:
        """Check if today is the last Thursday of the month (monthly expiry)."""
        if today.weekday() != 3:  # Not Thursday
            return False

        # Check if there's another Thursday this month
        next_week = today + datetime.timedelta(days=7)
        return next_week.month != today.month

    def _apply_bias_matrix(
        self,
        weekly: WeeklyTrend,
        daily: DailyPattern,
        is_event_day: bool
    ) -> Tuple[VWAPStrategy, bool, str, int]:
        """
        Apply the Weekly + Daily -> VWAP bias matrix.

        Matrix Rules:
        | Weekly      | Daily            | VWAP Strategy          |
        |-------------|------------------|------------------------|
        | Trending    | Expansion        | VWAP pullback continuation |
        | Trending    | Inside           | Trade light or skip    |
        | Balanced    | Inside           | VWAP mean reversion    |
        | Balanced    | Failed breakout  | Strong VWAP fades      |
        | Any         | Event day        | Avoid VWAP completely  |

        Returns:
            (strategy, should_trade, skip_reason, quality_score)
        """
        # Event day overrides everything
        if is_event_day:
            return (
                VWAPStrategy.NO_TRADE,
                False,
                "Event day - volatility unpredictable, avoid VWAP trades",
                0
            )

        # Handle unknown conditions
        if weekly == WeeklyTrend.UNKNOWN or daily == DailyPattern.UNKNOWN:
            return (
                VWAPStrategy.SKIP,
                False,
                "Insufficient data for regime analysis",
                0
            )

        # Trending week scenarios
        if weekly in [WeeklyTrend.TRENDING_UP, WeeklyTrend.TRENDING_DOWN]:
            if daily == DailyPattern.EXPANSION:
                # Best setup: Trend continuation after expansion
                return (
                    VWAPStrategy.CONTINUATION,
                    True,
                    "",
                    90  # High quality
                )

            elif daily == DailyPattern.INSIDE:
                # Consolidation in trend - trade light or skip
                return (
                    VWAPStrategy.SKIP,
                    False,
                    "Trending week + Inside day = consolidation, wait for breakout",
                    30  # Low quality
                )

            elif daily == DailyPattern.FAILED_BREAKOUT:
                # Trend exhaustion signal - be cautious
                return (
                    VWAPStrategy.SKIP,
                    False,
                    "Trending week + Failed breakout = potential reversal, skip",
                    20  # Very low quality
                )

            elif daily == DailyPattern.NORMAL:
                # Normal trend day - can trade with caution
                return (
                    VWAPStrategy.CONTINUATION,
                    True,
                    "",
                    70  # Moderate quality
                )

        # Balanced week scenarios
        elif weekly == WeeklyTrend.BALANCED:
            if daily == DailyPattern.INSIDE:
                # Range trading setup - mean reversion
                return (
                    VWAPStrategy.MEAN_REVERSION,
                    True,
                    "",
                    75  # Good for mean reversion
                )

            elif daily == DailyPattern.FAILED_BREAKOUT:
                # Perfect fade setup
                return (
                    VWAPStrategy.FADE,
                    True,
                    "",
                    85  # High quality fade
                )

            elif daily == DailyPattern.EXPANSION:
                # Breakout from balance - could be start of trend
                return (
                    VWAPStrategy.CONTINUATION,
                    True,
                    "",
                    65  # Moderate - need confirmation
                )

            elif daily == DailyPattern.NORMAL:
                # Normal balanced day - mean reversion
                return (
                    VWAPStrategy.MEAN_REVERSION,
                    True,
                    "",
                    60  # Moderate quality
                )

        # Fallback
        return (
            VWAPStrategy.SKIP,
            False,
            "Matrix conditions unclear - skipping",
            0
        )

    def get_trade_direction_filter(self, regime: MarketRegime) -> Optional[str]:
        """
        Get allowed trade direction based on regime.

        Returns:
            'CE' - Only allow CE trades (bullish)
            'PE' - Only allow PE trades (bearish)
            'BOTH' - Allow both directions
            None - No trades allowed
        """
        if not regime.should_trade:
            return None

        strategy = regime.vwap_strategy
        weekly = regime.weekly_trend

        if strategy == VWAPStrategy.CONTINUATION:
            # In trend continuation, only trade with the trend
            if weekly == WeeklyTrend.TRENDING_UP:
                return 'CE'
            elif weekly == WeeklyTrend.TRENDING_DOWN:
                return 'PE'
            else:
                return 'BOTH'  # Balanced with expansion

        elif strategy == VWAPStrategy.MEAN_REVERSION:
            # Mean reversion can go both ways
            return 'BOTH'

        elif strategy == VWAPStrategy.FADE:
            # Fades are counter-trend
            if weekly == WeeklyTrend.TRENDING_UP:
                return 'PE'  # Fade the up move
            elif weekly == WeeklyTrend.TRENDING_DOWN:
                return 'CE'  # Fade the down move
            else:
                return 'BOTH'

        return None

    def should_trade_signal(
        self,
        regime: MarketRegime,
        signal_type: str
    ) -> Tuple[bool, str]:
        """
        Check if a specific signal should be traded based on regime.

        Args:
            regime: Current market regime
            signal_type: 'BUY_CE' or 'BUY_PE'

        Returns:
            (should_trade, reason)
        """
        if not regime.should_trade:
            return False, regime.skip_reason

        allowed_direction = self.get_trade_direction_filter(regime)

        if allowed_direction is None:
            return False, "No trade direction allowed"

        if allowed_direction == 'BOTH':
            return True, f"Signal aligned with {regime.vwap_strategy.value} strategy"

        signal_direction = 'CE' if signal_type == 'BUY_CE' else 'PE'

        if signal_direction == allowed_direction:
            return True, f"Signal aligned with weekly {regime.weekly_trend.value}"
        else:
            return False, f"Signal {signal_type} conflicts with weekly {regime.weekly_trend.value} trend"

    def format_regime_summary(self, regime: MarketRegime) -> str:
        """Format regime for logging/display."""
        lines = [
            f"Weekly: {regime.weekly_trend.value}",
            f"Daily: {regime.daily_pattern.value}",
            f"Event: {'Yes - ' + regime.event_description if regime.is_event_day else 'No'}",
            f"Strategy: {regime.vwap_strategy.value}",
            f"Quality: {regime.trade_quality_score}/100",
            f"Trade: {'YES' if regime.should_trade else 'NO - ' + regime.skip_reason}"
        ]
        return " | ".join(lines)
