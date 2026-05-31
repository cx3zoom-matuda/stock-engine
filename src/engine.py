from typing import Dict, List, Any
from .schema import CORE_SECTORS, SUBSECTOR_TO_SECTOR_MAP, IMPACT_MATRIX

class RuleEngine:
    """
    Evaluates active macro events against the static translation impact matrix,
    aggregates weights with severity factors, and ranks the 17 core sectors.
    """

    def calculate_industry_scores(self, active_events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates cumulative impact scores for the 17 core sectors.
        
        Formula:
            Core Sector Score = Sum(Event Weight * Severity)
            
        Args:
            active_events: List of triggered events from EventDetector. E.g.:
                [{"event": "long_rate_drop", "severity": 2, "value": -0.6, "description": "..."}]
                
        Returns:
            Dictionary containing:
                "rankings": List of sectors sorted by score descending:
                    [
                        {
                            "sector": "real_estate",
                            "score": 160.0,
                            "normalized_score": 1.0,
                            "breakdown": [{"event": "long_rate_drop", "weight": 50, "severity": 2, "impact": 100}]
                        },
                        ...
                    ]
                "raw_scores": Dict mapping core sector name to float score.
        """
        # Initialize scores and breakdowns for the 17 core sectors
        raw_scores = {sector: 0.0 for sector in CORE_SECTORS}
        breakdowns = {sector: [] for sector in CORE_SECTORS}

        # Calculate raw scores and build breakdowns
        for active in active_events:
            event_name = active["event"]
            severity = active["severity"]
            
            # Lookup in our matrix (check exact match or key aliases)
            # Standardize names just in case (e.g. oil_spike vs oil_price_spike)
            lookup_key = event_name
            if event_name == "oil_price_spike" and "oil_price_spike" not in IMPACT_MATRIX:
                lookup_key = "oil_spike"
            elif event_name == "oil_spike" and "oil_spike" not in IMPACT_MATRIX:
                lookup_key = "oil_price_spike"
            elif event_name == "long_rate_rise" and "long_rate_rise" not in IMPACT_MATRIX:
                lookup_key = "long_rate_spike"
            elif event_name == "long_rate_spike" and "long_rate_spike" not in IMPACT_MATRIX:
                lookup_key = "long_rate_rise"
                
            if lookup_key in IMPACT_MATRIX:
                sector_weights = IMPACT_MATRIX[lookup_key]
                for ind_name, weight in sector_weights.items():
                    # Map granular subsectors to core 17 sectors
                    core_sector = SUBSECTOR_TO_SECTOR_MAP.get(ind_name)
                    if core_sector:
                        impact = weight * severity
                        raw_scores[core_sector] += impact
                        breakdowns[core_sector].append({
                            "event": event_name,
                            "base_weight": weight,
                            "severity": severity,
                            "impact_contribution": impact,
                            "description": active.get("description", "")
                        })

        # Calculate max absolute score for normalization (avoid division by zero)
        max_abs_score = max([abs(score) for score in raw_scores.values()] + [1.0])

        # Build final ranked results
        rankings = []
        for sector in CORE_SECTORS:
            score = raw_scores[sector]
            normalized = score / max_abs_score
            rankings.append({
                "sector": sector,
                "score": score,
                "normalized_score": round(normalized, 4),
                "breakdown": breakdowns[sector]
            })

        # Sort rankings: highest positive impact first, then by absolute value
        rankings.sort(key=lambda x: (-x["score"], -abs(x["score"])))

        return {
            "rankings": rankings,
            "raw_scores": raw_scores
        }
