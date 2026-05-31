from typing import Dict, List, Any, Optional

class StockEvaluator:
    """
    Evaluates individual stocks by combining their industry macro scores 
    with their valuation metrics (PER, PBR) to output investment decisions (BUY, WATCH, AVOID),
    handling different G20 market criteria dynamically.
    """

    def evaluate_stocks(
        self, 
        stock_metrics_list: List[Dict[str, Any]], 
        sector_scores: Dict[str, Dict[str, Any]],
        market: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a list of stocks against calculated sector macro scores.
        
        Args:
            stock_metrics_list: List of stock metrics from MarketDataClient.
            sector_scores: Dict of sector scores from ImpactScorer.
            market: Specific market country code ("JP", "US", "EZ", "GB", etc.). 
                    If None, auto-detected from ticker suffix.
            
        Returns:
            Sorted list of evaluated stock data with scores, decisions, and rationales.
        """
        evaluated_stocks = []

        # Market valuation profiles definition
        PROFILES = {
            "JP": {
                "per_thresholds": [8.0, 13.0, 20.0],
                "pbr_thresholds": [0.7, 1.0, 1.8],
                "avoid_per": 40.0
            },
            "CN": {
                "per_thresholds": [10.0, 16.0, 24.0],
                "pbr_thresholds": [1.0, 1.8, 3.2],
                "avoid_per": 48.0
            },
            "US": {
                "per_thresholds": [14.0, 22.0, 30.0],
                "pbr_thresholds": [1.5, 3.0, 5.5],
                "avoid_per": 60.0
            }
        }
        # advanced markets share the US standard valuation profile
        PROFILES["GB"] = PROFILES["US"]
        PROFILES["EZ"] = PROFILES["US"]
        PROFILES["CA"] = PROFILES["US"]
        PROFILES["AU"] = PROFILES["US"]

        for stock in stock_metrics_list:
            ticker = stock["ticker"]
            name = stock["name"]
            sector = stock["sector"]
            per = stock["per"]
            pbr = stock["pbr"]
            price = stock["price"]

            # Auto-detect market from ticker suffix if not specified
            current_market = market
            if not current_market:
                if ticker.endswith(".T"):
                    current_market = "JP"
                elif ticker.endswith(".L"):
                    current_market = "GB"
                elif ticker.endswith(".HK"):
                    current_market = "CN"
                elif ticker.endswith(".AX"):
                    current_market = "AU"
                elif ticker.endswith(".TO"):
                    current_market = "CA"
                elif any(ticker.endswith(s) for s in [".PA", ".AS", ".DE"]):
                    current_market = "EZ"
                else:
                    current_market = "US"

            # Fallback to JP if profile not defined
            profile = PROFILES.get(current_market, PROFILES["JP"])
            per_th = profile["per_thresholds"]
            pbr_th = profile["pbr_thresholds"]
            avoid_per_threshold = profile["avoid_per"]

            # Get sector macro score (default to 0 if sector not found)
            sec_data = sector_scores.get(sector, {"score": 0.0, "breakdown": []})
            macro_score = sec_data["score"]

            # 1. Valuation Score Calculation
            per_score = 0.0
            pbr_score = 0.0
            val_notes = []

            # PER evaluation
            if per <= 0:
                per_score = -20.0
                val_notes.append("Negative Earnings (PER <= 0)")
            elif per <= per_th[0]:
                per_score = 30.0
                val_notes.append(f"Highly Undervalued PER (<= {per_th[0]:.1f})")
            elif per <= per_th[1]:
                per_score = 15.0
                val_notes.append(f"Undervalued PER ({per_th[0]:.1f} - {per_th[1]:.1f})")
            elif per <= per_th[2]:
                per_score = 0.0
                val_notes.append(f"Fair Value PER ({per_th[1]:.1f} - {per_th[2]:.1f})")
            else:
                per_score = -15.0
                val_notes.append(f"Overvalued PER (> {per_th[2]:.1f})")

            # PBR evaluation
            if pbr <= 0:
                pbr_score = -10.0
                val_notes.append("Negative Book Value (PBR <= 0)")
            elif pbr <= pbr_th[0]:
                pbr_score = 20.0
                val_notes.append(f"Significant Asset Discount PBR (<= {pbr_th[0]:.2f})")
            elif pbr <= pbr_th[1]:
                pbr_score = 10.0
                val_notes.append(f"Asset Discount PBR ({pbr_th[0]:.2f} - {pbr_th[1]:.2f})")
            elif pbr <= pbr_th[2]:
                pbr_score = 0.0
                val_notes.append(f"Fair Value PBR ({pbr_th[1]:.2f} - {pbr_th[2]:.2f})")
            else:
                pbr_score = -10.0
                val_notes.append(f"Asset Premium PBR (> {pbr_th[2]:.2f})")

            valuation_score = per_score + pbr_score

            # 2. Combined Score Calculation
            combined_score = macro_score + valuation_score

            # 3. Decision Rules
            decision = "WATCH"
            rationale_parts = []

            # Determine decision and rationale
            if macro_score >= 15.0:
                rationale_parts.append(f"Strong industry macroeconomic tailwinds (+{macro_score:.1f})")
            elif macro_score <= -15.0:
                rationale_parts.append(f"Severe industry macroeconomic headwinds ({macro_score:.1f})")
            else:
                rationale_parts.append(f"Neutral/mild industry macro conditions ({macro_score:+.1f})")

            if valuation_score >= 20.0:
                rationale_parts.append(f"deep value valuation metrics (PER: {per:.1f}, PBR: {pbr:.2f})")
            elif valuation_score <= -15.0:
                rationale_parts.append(f"expensive valuation metrics (PER: {per:.1f}, PBR: {pbr:.2f})")
            else:
                rationale_parts.append(f"fair valuation metrics (PER: {per:.1f}, PBR: {pbr:.2f})")

            # Final categorization
            if macro_score >= 15.0 and valuation_score >= 10.0 and per > 0:
                decision = "BUY"
                rationale_parts.append("Recommendation: Accumulate due to strong macro alignment and attractive valuation.")
            elif macro_score <= -20.0 or valuation_score <= -25.0 or per > avoid_per_threshold or per <= 0:
                decision = "AVOID"
                rationale_parts.append("Recommendation: Avoid due to high valuation risk or severe macro headwinds.")
            else:
                decision = "WATCH"
                rationale_parts.append("Recommendation: Monitor. Keep on watchlist pending stronger macro signals or price correction.")

            rationale = ". ".join(rationale_parts)

            evaluated_stocks.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "price": price,
                "per": per,
                "pbr": pbr,
                "macro_score": macro_score,
                "valuation_score": valuation_score,
                "combined_score": combined_score,
                "decision": decision,
                "rationale": rationale,
                "valuation_notes": ", ".join(val_notes)
            })

        # Sort: BUY first, then WATCH, then AVOID. Within decisions, sort by combined_score descending.
        decision_priority = {"BUY": 0, "WATCH": 1, "AVOID": 2}
        evaluated_stocks.sort(
            key=lambda x: (decision_priority[x["decision"]], -x["combined_score"])
        )

        return evaluated_stocks
