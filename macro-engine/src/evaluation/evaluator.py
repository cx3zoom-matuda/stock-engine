from typing import Dict, List, Any

class StockEvaluator:
    """
    Evaluates individual stocks by combining their industry macro scores 
    with their valuation metrics (PER, PBR) to output investment decisions (BUY, WATCH, AVOID).
    """

    def evaluate_stocks(
        self, 
        stock_metrics_list: List[Dict[str, Any]], 
        sector_scores: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Evaluates a list of stocks against calculated sector macro scores.
        
        Args:
            stock_metrics_list: List of stock metrics from MarketDataClient.
            sector_scores: Dict of sector scores from ImpactScorer.
            
        Returns:
            Sorted list of evaluated stock data with scores, decisions, and rationales.
        """
        evaluated_stocks = []

        for stock in stock_metrics_list:
            ticker = stock["ticker"]
            name = stock["name"]
            sector = stock["sector"]
            per = stock["per"]
            pbr = stock["pbr"]
            price = stock["price"]

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
            elif per <= 8.0:
                per_score = 30.0
                val_notes.append("Highly Undervalued PER (<= 8.0)")
            elif per <= 13.0:
                per_score = 15.0
                val_notes.append("Undervalued PER (8.0 - 13.0)")
            elif per <= 20.0:
                per_score = 0.0
                val_notes.append("Fair Value PER (13.0 - 20.0)")
            else:
                per_score = -15.0
                val_notes.append("Overvalued PER (> 20.0)")

            # PBR evaluation
            if pbr <= 0:
                pbr_score = -10.0
                val_notes.append("Negative Book Value (PBR <= 0)")
            elif pbr <= 0.7:
                pbr_score = 20.0
                val_notes.append("Significant Asset Discount PBR (<= 0.7)")
            elif pbr <= 1.0:
                pbr_score = 10.0
                val_notes.append("Asset Discount PBR (0.7 - 1.0)")
            elif pbr <= 1.8:
                pbr_score = 0.0
                val_notes.append("Fair Value PBR (1.0 - 1.8)")
            else:
                pbr_score = -10.0
                val_notes.append("Asset Premium PBR (> 1.8)")

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
            elif macro_score <= -20.0 or valuation_score <= -25.0 or per > 40.0 or per <= 0:
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
