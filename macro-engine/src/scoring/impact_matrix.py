from typing import Dict, List, Any, Tuple

class ImpactScorer:
    """
    Calculates macro influence scores for 16 key industries
    by mapping active macroeconomic signals through an impact matrix.
    """
    
    SECTORS = [
        "Automobiles & Transportation",
        "Financials/Banking",
        "Technology/Electronics",
        "Energy/Oil",
        "Construction/Real Estate",
        "Defensive/Consumer Staples",
        "Shipping/Marine Transportation",
        "Retail",
        "Steel/Non-Ferrous Metals",
        "Trading Houses",
        "Utilities",
        "IT Services/Software",
        "Chemical/Materials",
        "Machinery",
        "Precision Instruments",
        "Services/Entertainment"
    ]

    # The Static Impact Matrix: Macro Signals (columns) x Industry Sectors (rows)
    # Impact range: -50 (severe headwind) to +50 (strong tailwind)
    MATRIX = {
        "YIELD_INVERSION": {
            "Financials/Banking": -30,
            "Construction/Real Estate": -30,
            "Defensive/Consumer Staples": 20,
            "Automobiles & Transportation": -15,
            "Technology/Electronics": -15,
            "Retail": -10,
            "Trading Houses": -10,
            "Utilities": 10,
            "IT Services/Software": -10,
            "Services/Entertainment": -10,
        },
        "YIELD_FLATTENING": {
            "Financials/Banking": -15,
            "Construction/Real Estate": -10,
            "Defensive/Consumer Staples": 10,
            "Automobiles & Transportation": -5,
            "Technology/Electronics": -5,
            "Utilities": 5,
        },
        "YIELD_STEEPENING": {
            "Financials/Banking": 30,
            "Construction/Real Estate": 15,
            "Trading Houses": 20,
            "Steel/Non-Ferrous Metals": 20,
            "Machinery": 15,
            "Defensive/Consumer Staples": -10,
        },
        "RATE_RISING": {
            "Financials/Banking": 40,
            "Construction/Real Estate": -40,
            "IT Services/Software": -25,
            "Technology/Electronics": -20,
            "Utilities": -20,
            "Defensive/Consumer Staples": -15,
            "Automobiles & Transportation": -10,
            "Retail": -10,
        },
        "RATE_FALLING": {
            "Financials/Banking": -30,
            "Construction/Real Estate": 40,
            "IT Services/Software": 30,
            "Technology/Electronics": 25,
            "Utilities": 20,
            "Defensive/Consumer Staples": 15,
            "Automobiles & Transportation": 15,
            "Retail": 15,
        },
        "INFLATION_ACCELERATING": {
            "Energy/Oil": 45,
            "Trading Houses": 30,
            "Steel/Non-Ferrous Metals": 25,
            "Chemical/Materials": 20,
            "Utilities": -35,
            "Retail": -20,
            "Defensive/Consumer Staples": -10,
            "Financials/Banking": 10,
        },
        "INFLATION_DECELERATING": {
            "Utilities": 25,
            "Defensive/Consumer Staples": 20,
            "Retail": 20,
            "Energy/Oil": -25,
            "Trading Houses": -15,
            "Chemical/Materials": -10,
        },
        "ENERGY_SHOCK": {
            "Energy/Oil": 50,
            "Trading Houses": 25,
            "Automobiles & Transportation": -30,
            "Utilities": -45,
            "Shipping/Marine Transportation": -25,
            "Chemical/Materials": -25,
            "Retail": -15,
            "Defensive/Consumer Staples": -10,
        },
        "ENERGY_DECLINE": {
            "Energy/Oil": -50,
            "Trading Houses": -20,
            "Automobiles & Transportation": 30,
            "Utilities": 40,
            "Shipping/Marine Transportation": 25,
            "Chemical/Materials": 20,
            "Retail": 15,
            "Defensive/Consumer Staples": 10,
        },
        "YEN_DEPRECIATING": {
            "Automobiles & Transportation": 45,
            "Technology/Electronics": 35,
            "Precision Instruments": 35,
            "Machinery": 30,
            "Trading Houses": 25,
            "Utilities": -40,
            "Defensive/Consumer Staples": -20,
            "Retail": -15,
        },
        "YEN_APPRECIATING": {
            "Utilities": 30,
            "Defensive/Consumer Staples": 20,
            "Retail": 15,
            "Automobiles & Transportation": -45,
            "Technology/Electronics": -35,
            "Precision Instruments": -35,
            "Machinery": -25,
            "Trading Houses": -20,
        },
        "HIGH_RATE_ENVIRONMENT": {
            "Financials/Banking": 30,
            "Construction/Real Estate": -30,
            "IT Services/Software": -20,
            "Technology/Electronics": -15,
        }
    }

    def calculate_sector_scores(self, active_signals: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Calculates the score and contribution breakdown for each of the 16 sectors.
        
        Args:
            active_signals: Output from SignalDetector.detect_signals
            
        Returns:
            Dict mapping sector name to:
            {
                "score": float (sum of signal impacts),
                "breakdown": List[Dict[str, Any]] (list of contributing signals and their impact points)
            }
        """
        scores = {}
        for sector in self.SECTORS:
            scores[sector] = {
                "score": 0.0,
                "breakdown": []
            }

        for sig_name, sig_info in active_signals.items():
            if not sig_info.get("active"):
                continue
                
            # If this signal has defined impacts in our matrix
            if sig_name in self.MATRIX:
                impacts = self.MATRIX[sig_name]
                for sector, score_diff in impacts.items():
                    if sector in scores:
                        scores[sector]["score"] += score_diff
                        scores[sector]["breakdown"].append({
                            "signal": sig_name,
                            "impact": score_diff,
                            "description": sig_info.get("description", "")
                        })
                        
        return scores
