import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional

class EventDetector:
    """
    Analyzes macroeconomic indicator time series for a specific country/region
    to detect generic macro events (e.g. long_rate_drop, rate_hike, business_contraction)
    along with their priority/severity level (1: minor, 2: moderate, 3: major).
    """

    def detect_events(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Runs all detector rules on the input country-specific macroeconomic data.
        
        Args:
            data: A dictionary containing time series. E.g.:
                {
                    "YIELD_10Y": [3.5, 3.4, 2.9],    # 10Y Yields
                    "POLICY_RATE": [3.0, 3.0, 3.25], # Policy interest rate
                    "CPI": [2.1, 2.5, 3.2],          # YoY CPI percentage values
                    "CONFIDENCE": [50.1, 49.5, 48.2],# Business confidence (PMI or Tankan proxy)
                    "GDP": [2.0, 1.8, 0.5],          # YoY GDP growth percentage
                    "UNEMPLOYMENT": [4.5, 4.4, 4.6]   # Unemployment rate (Optional)
                }
            Alternatively, values can be pandas Series or numpy arrays.
            
        Returns:
            List of triggered event dictionaries:
                [
                    {
                        "event": "rate_hike",
                        "severity": 2,
                        "value": 0.25,
                        "description": "Central bank hiked policy rate by +0.25% points."
                    },
                    ...
                ]
        """
        active_events = []

        # 1. Long-term Interest Rates (long_rate_spike, long_rate_drop)
        rates = self._to_series(data.get("YIELD_10Y"))
        if len(rates) >= 2:
            change = round(float(rates.iloc[-1] - rates.iloc[-2]), 4)
            if change >= 0.25:
                severity = 3 if change >= 1.0 else (2 if change >= 0.5 else 1)
                active_events.append({
                    "event": "long_rate_spike",
                    "severity": severity,
                    "value": change,
                    "description": f"Long-term rate rose by {change:+.2f}% points (Latest: {rates.iloc[-1]:.2f}%)"
                })
            elif change <= -0.25:
                severity = 3 if change <= -1.0 else (2 if change <= -0.5 else 1)
                active_events.append({
                    "event": "long_rate_drop",
                    "severity": severity,
                    "value": change,
                    "description": f"Long-term rate dropped by {change:.2f}% points (Latest: {rates.iloc[-1]:.2f}%)"
                })

        # 2. Central Bank Policy Rate (rate_hike, rate_cut)
        policy = self._to_series(data.get("POLICY_RATE"))
        if len(policy) >= 2:
            change = round(float(policy.iloc[-1] - policy.iloc[-2]), 4)
            if change >= 0.05:
                severity = 3 if change >= 0.5 else (2 if change >= 0.25 else 1)
                active_events.append({
                    "event": "rate_hike",
                    "severity": severity,
                    "value": change,
                    "description": f"Central bank hiked policy rate by {change:+.2f}% (Latest: {policy.iloc[-1]:.2f}%)"
                })
            elif change <= -0.05:
                severity = 3 if change <= -0.5 else (2 if change <= -0.25 else 1)
                active_events.append({
                    "event": "rate_cut",
                    "severity": severity,
                    "value": change,
                    "description": f"Central bank cut policy rate by {change:.2f}% (Latest: {policy.iloc[-1]:.2f}%)"
                })

        # 3. Inflation / CPI (inflation_high, inflation_low)
        cpi_yoy = self._to_series(data.get("CPI"))
        if not cpi_yoy.empty:
            latest_cpi = float(cpi_yoy.iloc[-1])
            if latest_cpi >= 2.0:
                severity = 3 if latest_cpi >= 5.0 else (2 if latest_cpi >= 3.0 else 1)
                active_events.append({
                    "event": "inflation_high",
                    "severity": severity,
                    "value": latest_cpi,
                    "description": f"High inflation detected. YoY CPI is {latest_cpi:.1f}%"
                })
            elif latest_cpi <= 1.5:
                severity = 3 if latest_cpi < 0.0 else (2 if latest_cpi <= 1.0 else 1)
                active_events.append({
                    "event": "inflation_low",
                    "severity": severity,
                    "value": latest_cpi,
                    "description": f"Low inflation/deflation detected. YoY CPI is {latest_cpi:.1f}%"
                })

        # 4. GDP growth (gdp_growth_accelerating, gdp_growth_slowing)
        gdp_yoy = self._to_series(data.get("GDP"))
        if not gdp_yoy.empty:
            latest_gdp = float(gdp_yoy.iloc[-1])
            if latest_gdp >= 2.5:
                severity = 3 if latest_gdp >= 6.0 else (2 if latest_gdp >= 4.0 else 1)
                active_events.append({
                    "event": "gdp_growth_accelerating",
                    "severity": severity,
                    "value": latest_gdp,
                    "description": f"GDP growth accelerating. YoY: {latest_gdp:.1f}%"
                })
            elif latest_gdp <= 1.0:
                severity = 3 if latest_gdp <= -2.0 else (2 if latest_gdp <= 0.0 else 1)
                active_events.append({
                    "event": "gdp_growth_slowing",
                    "severity": severity,
                    "value": latest_gdp,
                    "description": f"GDP growth slowing/contraction. YoY: {latest_gdp:.1f}%"
                })

        # 5. Business Confidence / PMI (business_expansion, business_contraction)
        confidence = self._to_series(data.get("CONFIDENCE"))
        if not confidence.empty:
            latest_conf = float(confidence.iloc[-1])
            # Differentiate PMI (50 threshold) vs OECD BC / Tankan (100 threshold)
            threshold = 50.0 if latest_conf < 75.0 else 100.0
            
            if latest_conf >= threshold:
                severity = 3 if latest_conf >= (threshold * 1.03) else (2 if latest_conf >= (threshold * 1.01) else 1)
                active_events.append({
                    "event": "business_expansion",
                    "severity": severity,
                    "value": latest_conf,
                    "description": f"Business confidence expansion is {latest_conf:.2f} (above {threshold})"
                })
            else:
                severity = 3 if latest_conf <= (threshold * 0.97) else (2 if latest_conf <= (threshold * 0.99) else 1)
                active_events.append({
                    "event": "business_contraction",
                    "severity": severity,
                    "value": latest_conf,
                    "description": f"Business confidence contraction is {latest_conf:.2f} (below {threshold})"
                })

        # 6. Yield Curve Spread (yield_curve_inversion, yield_curve_steepening)
        if not rates.empty and not policy.empty:
            latest_10y = float(rates.iloc[-1])
            latest_policy = float(policy.iloc[-1])
            spread = round(latest_10y - latest_policy, 4)
            if spread <= 0.0:
                active_events.append({
                    "event": "yield_curve_inversion",
                    "severity": 2,
                    "value": spread,
                    "description": f"Yield Curve Inverted! Spread: {spread:+.2f}%"
                })
            elif spread >= 1.5:
                active_events.append({
                    "event": "yield_curve_steepening",
                    "severity": 2,
                    "value": spread,
                    "description": f"Yield Curve Steepened. Spread: {spread:+.2f}%"
                })

        # 7. Labor market (labor_market_tightening, labor_market_slack) - Optional
        unemp = self._to_series(data.get("UNEMPLOYMENT"))
        if len(unemp) >= 2:
            latest_unemp = float(unemp.iloc[-1])
            prev_unemp = float(unemp.iloc[-2])
            change = round(latest_unemp - prev_unemp, 4)
            if change <= -0.2:
                active_events.append({
                    "event": "labor_market_tightening",
                    "severity": 2,
                    "value": latest_unemp,
                    "description": f"Labor market tightening. Unemployment: {latest_unemp:.2f}%"
                })
            elif change >= 0.2:
                active_events.append({
                    "event": "labor_market_slack",
                    "severity": 2,
                    "value": latest_unemp,
                    "description": f"Labor market slack. Unemployment: {latest_unemp:.2f}%"
                })

        # 8. WTI Crude Oil
        oil = self._to_series(data.get("OIL_PRICE"))
        pct_change = self._get_30d_pct_change(oil)
        if pct_change is not None:
            if pct_change >= 10.0:
                severity = 3 if pct_change >= 40.0 else (2 if pct_change >= 20.0 else 1)
                active_events.append({
                    "event": "oil_price_spike",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Oil price spiked by {pct_change:+.1f}% over the last 30d (Latest: ${oil.iloc[-1]:.2f})"
                })
            elif pct_change <= -10.0:
                severity = 3 if pct_change <= -40.0 else (2 if pct_change <= -20.0 else 1)
                active_events.append({
                    "event": "oil_price_crash",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Oil price crashed by {pct_change:.1f}% over the last 30d (Latest: ${oil.iloc[-1]:.2f})"
                })

        # 9. Global Commodities (Gold, Copper, Natural Gas)
        gold = self._to_series(data.get("GOLD_PRICE"))
        pct_change = self._get_30d_pct_change(gold)
        if pct_change is not None:
            if pct_change >= 8.0:
                severity = 3 if pct_change >= 25.0 else (2 if pct_change >= 15.0 else 1)
                active_events.append({
                    "event": "gold_price_spike",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Gold price spiked by {pct_change:+.1f}% over the last 30d (Latest: ${gold.iloc[-1]:.2f})"
                })
            elif pct_change <= -8.0:
                severity = 3 if pct_change <= -25.0 else (2 if pct_change <= -15.0 else 1)
                active_events.append({
                    "event": "gold_price_crash",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Gold price dropped by {pct_change:.1f}% over the last 30d (Latest: ${gold.iloc[-1]:.2f})"
                })

        copper = self._to_series(data.get("COPPER_PRICE"))
        pct_change = self._get_30d_pct_change(copper)
        if pct_change is not None:
            if pct_change >= 10.0:
                severity = 3 if pct_change >= 30.0 else (2 if pct_change >= 20.0 else 1)
                active_events.append({
                    "event": "copper_price_spike",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Copper price spiked by {pct_change:+.1f}% over the last 30d (Latest: ${copper.iloc[-1]:.4f})"
                })
            elif pct_change <= -10.0:
                severity = 3 if pct_change <= -30.0 else (2 if pct_change <= -20.0 else 1)
                active_events.append({
                    "event": "copper_price_crash",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Copper price dropped by {pct_change:.1f}% over the last 30d (Latest: ${copper.iloc[-1]:.4f})"
                })

        nat_gas = self._to_series(data.get("NATURAL_GAS"))
        pct_change = self._get_30d_pct_change(nat_gas)
        if pct_change is not None:
            if pct_change >= 15.0:
                severity = 3 if pct_change >= 50.0 else (2 if pct_change >= 30.0 else 1)
                active_events.append({
                    "event": "natural_gas_spike",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Natural Gas price spiked by {pct_change:+.1f}% over the last 30d (Latest: ${nat_gas.iloc[-1]:.3f})"
                })
            elif pct_change <= -15.0:
                severity = 3 if pct_change <= -50.0 else (2 if pct_change <= -30.0 else 1)
                active_events.append({
                    "event": "natural_gas_crash",
                    "severity": severity,
                    "value": pct_change,
                    "description": f"Natural Gas price dropped by {pct_change:.1f}% over the last 30d (Latest: ${nat_gas.iloc[-1]:.3f})"
                })

        # 10. Local Currency (currency_weakening, currency_strengthening)
        curr = self._to_series(data.get("LOCAL_CURRENCY"))
        quote = data.get("CURRENCY_QUOTE", "indirect")
        pct_change = self._get_30d_pct_change(curr)
        if pct_change is not None:
            weakened = False
            strengthened = False
            
            if quote == "indirect":
                if pct_change >= 2.0:
                    weakened = True
                elif pct_change <= -2.0:
                    strengthened = True
            elif quote == "direct":
                if pct_change <= -2.0:
                    weakened = True
                elif pct_change >= 2.0:
                    strengthened = True
            elif quote == "dollar_index":
                if pct_change >= 2.0:
                    strengthened = True
                elif pct_change <= -2.0:
                    weakened = True
                    
            if weakened:
                severity = 3 if abs(pct_change) >= 6.0 else (2 if abs(pct_change) >= 4.0 else 1)
                active_events.append({
                    "event": "currency_weakening",
                    "severity": severity,
                    "value": abs(pct_change),
                    "description": f"Local currency weakened by {abs(pct_change):.1f}% over the last 30d (Latest quote: {curr.iloc[-1]:.4f})"
                })
            elif strengthened:
                severity = 3 if abs(pct_change) >= 6.0 else (2 if abs(pct_change) >= 4.0 else 1)
                active_events.append({
                    "event": "currency_strengthening",
                    "severity": severity,
                    "value": abs(pct_change),
                    "description": f"Local currency strengthened by {abs(pct_change):.1f}% over the last 30d (Latest quote: {curr.iloc[-1]:.4f})"
                })

        # 11. Money Supply (liquidity_expansion, liquidity_contraction)
        m2_growth = self._to_series(data.get("MONEY_SUPPLY"))
        if not m2_growth.empty:
            latest_m2_yoy = float(m2_growth.iloc[-1])
            if latest_m2_yoy >= 8.0:
                severity = 3 if latest_m2_yoy >= 12.0 else (2 if latest_m2_yoy >= 9.0 else 1)
                active_events.append({
                    "event": "liquidity_expansion",
                    "severity": severity,
                    "value": latest_m2_yoy,
                    "description": f"Liquidity expansion active. YoY M2 growth: {latest_m2_yoy:.1f}%"
                })
            elif latest_m2_yoy <= 1.0:
                severity = 3 if latest_m2_yoy < -2.0 else (2 if latest_m2_yoy <= 0.0 else 1)
                active_events.append({
                    "event": "liquidity_contraction",
                    "severity": severity,
                    "value": latest_m2_yoy,
                    "description": f"Liquidity contraction (quantitative tightening). YoY M2 growth: {latest_m2_yoy:.1f}%"
                })

        # 12. Manual Qualitative Overrides / Global Events
        manual_keys = [
            "ai_investment_boom", "semiconductor_capex_cycle", "defense_spending_increase",
            "china_recovery", "china_slowing", "rate_hike", "rate_cut",
            "business_expansion", "business_contraction", "labor_market_tightening",
            "labor_market_slack", "yield_curve_inversion", "yield_curve_steepening",
            "china_manufacturing_slowdown", "copper_price_spike", "copper_price_crash",
            "gold_price_spike", "gold_price_crash", "natural_gas_spike", "natural_gas_crash",
            "liquidity_expansion", "liquidity_contraction", "currency_weakening", "currency_strengthening"
        ]
        for event_key in manual_keys:
            if data.get(event_key):
                val = data[event_key]
                severity = int(val) if isinstance(val, (int, float)) and val in [1, 2, 3] else 2
                active_events.append({
                    "event": event_key,
                    "severity": severity,
                    "value": float(severity),
                    "description": f"Manual event trigger: {event_key} (severity: {severity})"
                })

        return active_events

    def _get_30d_pct_change(self, series: pd.Series) -> Optional[float]:
        if len(series) < 2:
            return None
        if len(series) == 2:
            val_start = float(series.iloc[0])
            val_end = float(series.iloc[-1])
            if val_start == 0.0:
                return 0.0
            return ((val_end - val_start) / val_start) * 100.0
        try:
            latest_val = float(series.iloc[-1])
            if isinstance(series.index, pd.DatetimeIndex):
                target_date = series.index[-1] - pd.Timedelta(days=30)
                past_dates = series.index[series.index <= target_date]
                if len(past_dates) > 0:
                    past_val = float(series.loc[past_dates[-1]])
                else:
                    past_val = float(series.iloc[0])
            else:
                past_val = float(series.iloc[0])
            if past_val == 0.0:
                return 0.0
            return ((latest_val - past_val) / past_val) * 100.0
        except Exception:
            past_val = float(series.iloc[0])
            latest_val = float(series.iloc[-1])
            if past_val == 0.0:
                return 0.0
            return ((latest_val - past_val) / past_val) * 100.0

    def _to_series(self, val: Any) -> pd.Series:
        """Converts raw list or array formats to pandas Series."""
        if val is None:
            return pd.Series(dtype=float)
        if isinstance(val, pd.Series):
            return val
        return pd.Series(val).astype(float)
