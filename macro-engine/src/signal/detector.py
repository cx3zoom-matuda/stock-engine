import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple

class SignalDetector:
    """
    Analyzes macroeconomic time series to detect active signals
    such as yield curve changes, rate movements, inflation trends, energy shocks, and currency shifts.
    """
    
    SIGNALS = [
        "YIELD_INVERSION",       # 10Y - 2Y <= 0%
        "YIELD_FLATTENING",      # 0% < 10Y - 2Y < 0.5% or spread narrowing
        "YIELD_STEEPENING",      # 10Y - 2Y >= 1.0% and spread widening
        "RATE_RISING",           # 10Y yield above 50-day SMA
        "RATE_FALLING",          # 10Y yield below 50-day SMA
        "INFLATION_ACCELERATING",# CPI YoY rate rising or MoM > 0.4%
        "INFLATION_DECELERATING",# CPI YoY rate falling or MoM < 0.1%
        "ENERGY_SHOCK",          # Oil price above 50-day SMA by > 10%
        "ENERGY_DECLINE",        # Oil price below 50-day SMA by > 10%
        "YEN_DEPRECIATING",      # USD/JPY above 50-day SMA by > 2% (Yen weakening)
        "YEN_APPRECIATING",      # USD/JPY below 50-day SMA by > 2% (Yen strengthening)
        "HIGH_RATE_ENVIRONMENT"  # 10Y rate > 4.5%
    ]

    @staticmethod
    def clean_series(observations: List[Dict[str, Any]]) -> pd.Series:
        """Converts raw API observations to a clean pandas Series with datetime index."""
        if not observations:
            return pd.Series(dtype=float)
            
        df = pd.DataFrame(observations)
        df["date"] = pd.to_datetime(df["date"])
        # Handle FRED missing value placeholder "."
        df["value"] = df["value"].replace(".", np.nan)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        df = df.set_index("date").sort_index()
        return df["value"]

    def detect_signals(self, raw_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """
        Processes raw series observations and evaluates the 12 macro signals.
        Returns a dict of signals: {signal_name: {"active": bool, "value": float, "description": str}}
        """
        # Clean all Series
        series_10y = self.clean_series(raw_data.get("DGS10", []))
        series_2y = self.clean_series(raw_data.get("DGS2", []))
        series_cpi = self.clean_series(raw_data.get("CPIAUCSL", []))
        series_oil = self.clean_series(raw_data.get("DCOILWTICO", []))
        series_usdjpy = self.clean_series(raw_data.get("DEXJPUS", []))

        # Reindex and forward-fill daily series to align dates (handling weekends/holidays)
        daily_idx = series_10y.index.union(series_2y.index).union(series_oil.index)
        if not series_usdjpy.empty:
            daily_idx = daily_idx.union(series_usdjpy.index)
            
        s_10y = series_10y.reindex(daily_idx).ffill()
        s_2y = series_2y.reindex(daily_idx).ffill()
        s_oil = series_oil.reindex(daily_idx).ffill()
        s_usdjpy = series_usdjpy.reindex(daily_idx).ffill() if not series_usdjpy.empty else pd.Series(dtype=float)

        # Output dictionary
        signals_status = {sig: {"active": False, "value": 0.0, "description": "No data"} for sig in self.SIGNALS}

        if s_10y.empty or s_2y.empty:
            return signals_status

        # 1. Spread Calculation (10Y - 2Y)
        latest_date = s_10y.index[-1]
        latest_10y = s_10y.iloc[-1]
        latest_2y = s_2y.iloc[-1]
        spread = latest_10y - latest_2y
        
        # Historical spread for trend detection (30 days ago)
        hist_date_30d = latest_date - pd.Timedelta(days=30)
        spread_30d = None
        try:
            # find closest date in index
            idx_30d = s_10y.index[s_10y.index <= hist_date_30d][-1]
            spread_30d = s_10y.loc[idx_30d] - s_2y.loc[idx_30d]
        except IndexError:
            pass

        # Yield Inversion
        if spread <= 0:
            signals_status["YIELD_INVERSION"] = {
                "active": True,
                "value": float(spread),
                "description": f"Yield curve inverted. 10Y-2Y spread is {spread:.2f}% (10Y: {latest_10y:.2f}%, 2Y: {latest_2y:.2f}%)"
            }
        # Yield Flattening
        elif 0 < spread < 0.5 or (spread_30d is not None and spread < spread_30d and spread < 0.8):
            signals_status["YIELD_FLATTENING"] = {
                "active": True,
                "value": float(spread),
                "description": f"Yield curve flattening. Spread is {spread:.2f}%"
            }
        # Yield Steepening
        elif spread >= 1.0 and (spread_30d is not None and spread > spread_30d):
            signals_status["YIELD_STEEPENING"] = {
                "active": True,
                "value": float(spread),
                "description": f"Yield curve steepening. Spread expanded to {spread:.2f}%"
            }

        # 2. Rates SMA cross
        sma_50_10y = s_10y.rolling(50).mean()
        if not sma_50_10y.empty and len(s_10y) >= 50:
            latest_sma_50 = sma_50_10y.iloc[-1]
            if latest_10y > latest_sma_50:
                signals_status["RATE_RISING"] = {
                    "active": True,
                    "value": float(latest_10y - latest_sma_50),
                    "description": f"Interest rates rising. 10Y rate ({latest_10y:.2f}%) is above 50-day SMA ({latest_sma_50:.2f}%)"
                }
            else:
                signals_status["RATE_FALLING"] = {
                    "active": True,
                    "value": float(latest_sma_50 - latest_10y),
                    "description": f"Interest rates falling. 10Y rate ({latest_10y:.2f}%) is below 50-day SMA ({latest_sma_50:.2f}%)"
                }

        # High Rate Environment
        if latest_10y > 4.5:
            signals_status["HIGH_RATE_ENVIRONMENT"] = {
                "active": True,
                "value": float(latest_10y),
                "description": f"High rate environment. 10Y Bond Yield is {latest_10y:.2f}% (> 4.5%)"
            }

        # 3. Inflation (CPI)
        if not series_cpi.empty and len(series_cpi) >= 14:
            latest_cpi = series_cpi.iloc[-1]
            cpi_prev_month = series_cpi.iloc[-2]
            cpi_year_ago = series_cpi.iloc[-13]
            
            yoy_inflation = ((latest_cpi - cpi_year_ago) / cpi_year_ago) * 100
            prev_yoy_inflation = ((cpi_prev_month - series_cpi.iloc[-14]) / series_cpi.iloc[-14]) * 100
            mom_inflation_annualized = ((latest_cpi - cpi_prev_month) / cpi_prev_month) * 12 * 100

            if mom_inflation_annualized > 4.0 or yoy_inflation > prev_yoy_inflation + 0.1:
                signals_status["INFLATION_ACCELERATING"] = {
                    "active": True,
                    "value": float(yoy_inflation),
                    "description": f"Inflation accelerating. YoY: {yoy_inflation:.2f}%, Annualized MoM: {mom_inflation_annualized:.2f}%"
                }
            elif mom_inflation_annualized < 2.0 or yoy_inflation < prev_yoy_inflation - 0.1:
                signals_status["INFLATION_DECELERATING"] = {
                    "active": True,
                    "value": float(yoy_inflation),
                    "description": f"Inflation decelerating/stable. YoY: {yoy_inflation:.2f}%, Annualized MoM: {mom_inflation_annualized:.2f}%"
                }

        # 4. Energy Prices (WTI Oil)
        if not s_oil.empty and len(s_oil) >= 50:
            latest_oil = s_oil.iloc[-1]
            sma_50_oil = s_oil.rolling(50).mean().iloc[-1]
            pct_from_sma = ((latest_oil - sma_50_oil) / sma_50_oil) * 100
            
            if pct_from_sma > 10.0:
                signals_status["ENERGY_SHOCK"] = {
                    "active": True,
                    "value": float(pct_from_sma),
                    "description": f"Energy price shock. Oil price (${latest_oil:.2f}) is {pct_from_sma:.1f}% above 50-day SMA (${sma_50_oil:.2f})"
                }
            elif pct_from_sma < -10.0:
                signals_status["ENERGY_DECLINE"] = {
                    "active": True,
                    "value": float(pct_from_sma),
                    "description": f"Energy prices falling. Oil price (${latest_oil:.2f}) is {abs(pct_from_sma):.1f}% below 50-day SMA (${sma_50_oil:.2f})"
                }

        # 5. Currency (USD/JPY)
        if not s_usdjpy.empty and len(s_usdjpy) >= 50:
            latest_usdjpy = s_usdjpy.iloc[-1]
            sma_50_usdjpy = s_usdjpy.rolling(50).mean().iloc[-1]
            pct_from_sma = ((latest_usdjpy - sma_50_usdjpy) / sma_50_usdjpy) * 100

            if pct_from_sma > 2.0:
                signals_status["YEN_DEPRECIATING"] = {
                    "active": True,
                    "value": float(latest_usdjpy),
                    "description": f"Yen depreciating (円安). USD/JPY is {latest_usdjpy:.2f} ({pct_from_sma:+.1f}% vs 50-day SMA)"
                }
            elif pct_from_sma < -2.0:
                signals_status["YEN_APPRECIATING"] = {
                    "active": True,
                    "value": float(latest_usdjpy),
                    "description": f"Yen appreciating (円高). USD/JPY is {latest_usdjpy:.2f} ({pct_from_sma:+.1f}% vs 50-day SMA)"
                }

        return signals_status
