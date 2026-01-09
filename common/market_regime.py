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


class DirectionalBias(Enum):
    """Daily directional bias based on multi-day price structure."""
    BULLISH = "bullish"       # Clear bullish structure - only CE trades
    BEARISH = "bearish"       # Clear bearish structure - only PE trades
    NEUTRAL = "neutral"       # No clear bias - require extra confirmation
    UNKNOWN = "unknown"


@dataclass
class BiasAnalysis:
    """Detailed bias analysis with confidence scoring."""
    bias: DirectionalBias
    confidence: int  # 0-100
    reasons: List[str]
    swing_structure: str  # "HH-HL" (bullish), "LH-LL" (bearish), "mixed"
    prev_day_close_position: str  # "strong", "weak", "neutral"
    failed_breakout_direction: Optional[str]  # "up", "down", or None


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
    # New: Directional bias from multi-day structure analysis
    directional_bias: DirectionalBias = DirectionalBias.NEUTRAL
    bias_confidence: int = 0
    bias_reasons: List[str] = None


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

        # Check if executor is connected (for live trading)
        if hasattr(self.executor, 'connected') and not self.executor.connected:
            self.logger.warning("Executor not connected - skipping regime analysis")
            return self._create_unknown_regime(now, "Executor not connected")

        # Step 1: Weekly trend analysis
        weekly_trend = self._analyze_weekly_trend(nifty_token)
        self.logger.info(f"1. Weekly Trend: {weekly_trend.value.upper()}")

        # Step 2: Daily pattern analysis (yesterday's candle)
        daily_pattern = self._analyze_daily_pattern(nifty_token)
        self.logger.info(f"2. Yesterday's Pattern: {daily_pattern.value.upper()}")

        # Step 2b: Calculate directional bias from multi-day structure
        bias_analysis = self._calculate_directional_bias(nifty_token)

        # If both are unknown, we can't analyze regime properly
        if weekly_trend == WeeklyTrend.UNKNOWN and daily_pattern == DailyPattern.UNKNOWN:
            self.logger.warning("Insufficient data for regime analysis - allowing trades with caution")
            return self._create_unknown_regime(now, "Historical data unavailable")

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
            analysis_time=now,
            directional_bias=bias_analysis.bias,
            bias_confidence=bias_analysis.confidence,
            bias_reasons=bias_analysis.reasons
        )

        # Cache the result
        self._regime_cache = regime
        self._regime_cache_time = now

        return regime

    def _create_unknown_regime(self, now: datetime.datetime, reason: str) -> MarketRegime:
        """Create a regime object when analysis isn't possible."""
        regime = MarketRegime(
            weekly_trend=WeeklyTrend.UNKNOWN,
            daily_pattern=DailyPattern.UNKNOWN,
            is_event_day=False,
            event_description="",
            vwap_strategy=VWAPStrategy.SKIP,
            trade_quality_score=0,
            should_trade=True,  # Allow trading but with caution
            skip_reason=reason,
            analysis_time=now
        )
        # Cache it to avoid repeated analysis attempts
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
                self.logger.debug("Insufficient weekly data for trend analysis")
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
                self.logger.debug("Insufficient daily data for pattern analysis")
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

    def _calculate_directional_bias(self, nifty_token: int) -> BiasAnalysis:
        """
        Calculate directional bias using 5-7 days of price structure.

        This is the KEY method that determines CE vs PE bias for the day.
        Unlike the weak weekly trend calculation, this uses:
        1. Swing structure analysis (higher highs/lows vs lower highs/lows)
        2. Previous day close position (strong vs weak close)
        3. Failed breakout detection (strong reversal signal)
        4. Multi-day momentum

        Returns:
            BiasAnalysis with bias direction and confidence score
        """
        try:
            now = datetime.datetime.now()
            from_date = now - datetime.timedelta(days=12)  # Extra days for weekends

            data = self.executor.get_historical_data(
                instrument_token=nifty_token,
                from_date=from_date,
                to_date=now,
                interval="day"
            )

            if not data or len(data) < 5:
                self.logger.debug("Insufficient data for bias calculation")
                return BiasAnalysis(
                    bias=DirectionalBias.UNKNOWN,
                    confidence=0,
                    reasons=["Insufficient historical data"],
                    swing_structure="unknown",
                    prev_day_close_position="unknown",
                    failed_breakout_direction=None
                )

            df = pd.DataFrame(data)
            df = df.tail(7)  # Use last 7 trading days

            reasons = []
            confidence = 50  # Start neutral

            # ============================================
            # 1. SWING STRUCTURE ANALYSIS
            # ============================================
            # Find swing highs and lows in the data
            highs = df['high'].values
            lows = df['low'].values
            closes = df['close'].values

            # Compare recent highs and lows
            recent_high = highs[-1]
            prev_high = max(highs[-4:-1]) if len(highs) >= 4 else highs[-2]
            recent_low = lows[-1]
            prev_low = min(lows[-4:-1]) if len(lows) >= 4 else lows[-2]

            # Determine swing structure
            higher_high = recent_high > prev_high
            higher_low = recent_low > prev_low
            lower_high = recent_high < prev_high
            lower_low = recent_low < prev_low

            if higher_high and higher_low:
                swing_structure = "HH-HL"  # Bullish
                confidence += 20
                reasons.append("Swing structure: Higher Highs + Higher Lows (Bullish)")
            elif lower_high and lower_low:
                swing_structure = "LH-LL"  # Bearish
                confidence -= 20
                reasons.append("Swing structure: Lower Highs + Lower Lows (Bearish)")
            elif higher_high and lower_low:
                swing_structure = "expanding"  # Volatile
                reasons.append("Swing structure: Expanding range (Volatile)")
            elif lower_high and higher_low:
                swing_structure = "contracting"  # Consolidation
                reasons.append("Swing structure: Contracting range (Consolidation)")
            else:
                swing_structure = "mixed"
                reasons.append("Swing structure: Mixed signals")

            # ============================================
            # 2. PREVIOUS DAY CLOSE POSITION
            # ============================================
            yesterday = df.iloc[-2]  # Second to last (yesterday)
            yest_range = yesterday['high'] - yesterday['low']
            yest_close_position = (yesterday['close'] - yesterday['low']) / yest_range if yest_range > 0 else 0.5

            if yest_close_position >= 0.7:
                prev_day_close_position = "strong"
                confidence += 15
                reasons.append(f"Yesterday closed strong (top {int((1-yest_close_position)*100)}% of range)")
            elif yest_close_position <= 0.3:
                prev_day_close_position = "weak"
                confidence -= 15
                reasons.append(f"Yesterday closed weak (bottom {int(yest_close_position*100)}% of range)")
            else:
                prev_day_close_position = "neutral"
                reasons.append("Yesterday closed in middle of range")

            # ============================================
            # 3. FAILED BREAKOUT DETECTION
            # ============================================
            failed_breakout_direction = None
            day_before = df.iloc[-3] if len(df) >= 3 else None

            if day_before is not None:
                # Check if yesterday broke out of prior range but failed
                broke_high = yesterday['high'] > day_before['high']
                broke_low = yesterday['low'] < day_before['low']
                closed_weak = yest_close_position <= 0.3
                closed_strong = yest_close_position >= 0.7

                if broke_high and closed_weak:
                    failed_breakout_direction = "up"
                    confidence -= 25
                    reasons.append("FAILED BREAKOUT UP: Broke high but closed weak (Strong bearish signal)")
                elif broke_low and closed_strong:
                    failed_breakout_direction = "down"
                    confidence += 25
                    reasons.append("FAILED BREAKOUT DOWN: Broke low but closed strong (Strong bullish signal)")

            # ============================================
            # 4. MULTI-DAY MOMENTUM
            # ============================================
            # Check 3-day and 5-day price change
            three_day_change = ((closes[-1] - closes[-4]) / closes[-4] * 100) if len(closes) >= 4 else 0
            five_day_change = ((closes[-1] - closes[0]) / closes[0] * 100) if len(closes) >= 5 else 0

            if three_day_change > 0.5 and five_day_change > 0.8:
                confidence += 15
                reasons.append(f"Positive momentum: 3-day +{three_day_change:.1f}%, 5-day +{five_day_change:.1f}%")
            elif three_day_change < -0.5 and five_day_change < -0.8:
                confidence -= 15
                reasons.append(f"Negative momentum: 3-day {three_day_change:.1f}%, 5-day {five_day_change:.1f}%")

            # ============================================
            # 5. TODAY'S GAP (if market has opened)
            # ============================================
            if len(df) >= 2:
                today_open = df.iloc[-1]['open']
                yesterday_close = df.iloc[-2]['close']
                gap_pct = ((today_open - yesterday_close) / yesterday_close) * 100

                if gap_pct > 0.3:
                    confidence += 10
                    reasons.append(f"Gap up +{gap_pct:.2f}% supports bullish bias")
                elif gap_pct < -0.3:
                    confidence -= 10
                    reasons.append(f"Gap down {gap_pct:.2f}% supports bearish bias")

            # ============================================
            # DETERMINE FINAL BIAS
            # ============================================
            # Confidence ranges: 0-35 = Bearish, 35-65 = Neutral, 65-100 = Bullish
            if confidence >= 65:
                bias = DirectionalBias.BULLISH
            elif confidence <= 35:
                bias = DirectionalBias.BEARISH
            else:
                bias = DirectionalBias.NEUTRAL

            # Normalize confidence to 0-100 for the chosen direction
            if bias == DirectionalBias.BULLISH:
                final_confidence = min(100, confidence)
            elif bias == DirectionalBias.BEARISH:
                final_confidence = min(100, 100 - confidence)
            else:
                final_confidence = 50 - abs(50 - confidence)  # How neutral (50 = most neutral)

            self.logger.info("-" * 60)
            self.logger.info("DIRECTIONAL BIAS ANALYSIS (5-7 Day Structure)")
            self.logger.info("-" * 60)
            for reason in reasons:
                self.logger.info(f"  • {reason}")
            self.logger.info(f"  → BIAS: {bias.value.upper()} (Confidence: {final_confidence}%)")
            self.logger.info("-" * 60)

            return BiasAnalysis(
                bias=bias,
                confidence=final_confidence,
                reasons=reasons,
                swing_structure=swing_structure,
                prev_day_close_position=prev_day_close_position,
                failed_breakout_direction=failed_breakout_direction
            )

        except Exception as e:
            self.logger.error(f"Directional bias calculation failed: {str(e)}")
            return BiasAnalysis(
                bias=DirectionalBias.UNKNOWN,
                confidence=0,
                reasons=[f"Error: {str(e)}"],
                swing_structure="error",
                prev_day_close_position="error",
                failed_breakout_direction=None
            )

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
        Get allowed trade direction based on regime AND directional bias.

        NEW LOGIC: Uses directional bias as PRIMARY filter.
        The multi-day structure analysis determines whether we trade CE or PE.

        Returns:
            'CE' - Only allow CE trades (bullish bias)
            'PE' - Only allow PE trades (bearish bias)
            'BOTH' - Allow both directions (only when truly neutral with low confidence)
            None - No trades allowed
        """
        if not regime.should_trade:
            return None

        # ============================================
        # PRIMARY: Use directional bias from multi-day structure
        # This is the KEY change - bias determines direction, not strategy
        # ============================================
        bias = regime.directional_bias
        bias_confidence = regime.bias_confidence

        # Strong bias (confidence >= 60): Strictly enforce direction
        if bias == DirectionalBias.BULLISH and bias_confidence >= 60:
            self.logger.debug(f"Direction filter: CE only (Bullish bias, confidence {bias_confidence}%)")
            return 'CE'
        elif bias == DirectionalBias.BEARISH and bias_confidence >= 60:
            self.logger.debug(f"Direction filter: PE only (Bearish bias, confidence {bias_confidence}%)")
            return 'PE'

        # Moderate bias (confidence 40-60): Still enforce, but note it
        if bias == DirectionalBias.BULLISH:
            self.logger.debug(f"Direction filter: CE preferred (Bullish bias, confidence {bias_confidence}%)")
            return 'CE'
        elif bias == DirectionalBias.BEARISH:
            self.logger.debug(f"Direction filter: PE preferred (Bearish bias, confidence {bias_confidence}%)")
            return 'PE'

        # NEUTRAL bias: Fall back to strategy-based logic, but require higher ADX
        # This is the ONLY case where we might allow BOTH
        strategy = regime.vwap_strategy
        weekly = regime.weekly_trend

        if strategy == VWAPStrategy.CONTINUATION:
            if weekly == WeeklyTrend.TRENDING_UP:
                return 'CE'
            elif weekly == WeeklyTrend.TRENDING_DOWN:
                return 'PE'
            # Neutral bias + balanced weekly = require ADX > 30 for any trade
            # This is handled in should_trade_signal
            return 'BOTH_STRICT'  # Special flag for stricter requirements

        elif strategy == VWAPStrategy.FADE:
            # Fades are counter-trend - but we need strong confirmation
            if weekly == WeeklyTrend.TRENDING_UP:
                return 'PE'
            elif weekly == WeeklyTrend.TRENDING_DOWN:
                return 'CE'
            return 'BOTH_STRICT'

        elif strategy == VWAPStrategy.MEAN_REVERSION:
            # Mean reversion on neutral days = very risky
            # Only allow with high ADX confirmation
            return 'BOTH_STRICT'

        return None

    def should_trade_signal(
        self,
        regime: MarketRegime,
        signal_type: str,
        adx_value: float = None,
        allow_strong_counter_trend: bool = True
    ) -> Tuple[bool, str]:
        """
        Check if a specific signal should be traded based on regime AND directional bias.

        Args:
            regime: Current market regime
            signal_type: 'BUY_CE' or 'BUY_PE'
            adx_value: Current ADX value (required for BOTH_STRICT mode)
            allow_strong_counter_trend: Allow counter-trend trades with strong ADX (>=40)

        Returns:
            (should_trade, reason)
        """
        if not regime.should_trade:
            return False, regime.skip_reason

        allowed_direction = self.get_trade_direction_filter(regime)

        if allowed_direction is None:
            return False, "No trade direction allowed"

        signal_direction = 'CE' if signal_type == 'BUY_CE' else 'PE'

        # ============================================
        # BOTH_STRICT: Neutral bias, require ADX > 30
        # ============================================
        if allowed_direction == 'BOTH_STRICT':
            min_adx_for_neutral = 30
            if adx_value is None or adx_value < min_adx_for_neutral:
                return False, (
                    f"Neutral bias requires ADX >= {min_adx_for_neutral} for trade. "
                    f"Current ADX: {adx_value:.1f if adx_value else 'N/A'}"
                )
            return True, (
                f"Signal allowed in neutral bias with strong ADX {adx_value:.1f} >= {min_adx_for_neutral}"
            )

        # ============================================
        # Direct bias match
        # ============================================
        if signal_direction == allowed_direction:
            bias_info = f"Directional bias: {regime.directional_bias.value} (confidence: {regime.bias_confidence}%)"
            return True, f"Signal aligned with {bias_info}"

        # ============================================
        # Counter-bias trade - very strict requirements
        # ============================================
        # Only allow counter-bias if ADX >= 40 (very strong intraday momentum)
        if allow_strong_counter_trend and adx_value is not None and adx_value >= 40:
            return True, (
                f"Counter-bias allowed: ADX {adx_value:.1f} >= 40 overrides "
                f"{regime.directional_bias.value} bias"
            )

        return False, (
            f"Signal {signal_type} conflicts with {regime.directional_bias.value.upper()} bias "
            f"(confidence: {regime.bias_confidence}%). "
            f"ADX {adx_value:.1f if adx_value else 'N/A'} < 40 required for counter-bias"
        )

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
