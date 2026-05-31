import pytest
from src.detector import EventDetector
from src.engine import RuleEngine

def test_event_detector_long_rate_change():
    detector = EventDetector()

    # Case A: Interest rates spike by 0.6% points (severity 2)
    events = detector.detect_events({"YIELD_10Y": [3.4, 4.0]})
    spike = next((e for e in events if e["event"] == "long_rate_spike"), None)
    assert spike is not None
    assert spike["severity"] == 2
    assert spike["value"] == pytest.approx(0.6)

    # Case B: Interest rates drop by -1.2% points (severity 3)
    events = detector.detect_events({"YIELD_10Y": [4.2, 3.0]})
    drop = next((e for e in events if e["event"] == "long_rate_drop"), None)
    assert drop is not None
    assert drop["severity"] == 3
    assert drop["value"] == pytest.approx(-1.2)

def test_event_detector_inflation_cpi():
    detector = EventDetector()

    # CPI YoY is 5.5% -> High inflation (severity 3)
    events = detector.detect_events({"CPI": [2.0, 5.5]})
    inf = next((e for e in events if e["event"] == "inflation_high"), None)
    assert inf is not None
    assert inf["severity"] == 3

    # CPI YoY is 0.8% -> Low inflation (severity 2)
    events = detector.detect_events({"CPI": [2.0, 0.8]})
    inf_low = next((e for e in events if e["event"] == "inflation_low"), None)
    assert inf_low is not None
    assert inf_low["severity"] == 2

def test_event_detector_oil_changes():
    detector = EventDetector()

    # Oil spikes from $80 to $100 (+25.0% change -> severity 2)
    events = detector.detect_events({"OIL_PRICE": [80.0, 100.0]})
    oil_spike = next((e for e in events if e["event"] == "oil_price_spike"), None)
    assert oil_spike is not None
    assert oil_spike["severity"] == 2

    # Oil crashes from $80 to $45 (-43.75% change -> severity 3)
    events = detector.detect_events({"OIL_PRICE": [80.0, 45.0]})
    oil_crash = next((e for e in events if e["event"] == "oil_price_crash"), None)
    assert oil_crash is not None
    assert oil_crash["severity"] == 3

def test_rule_engine_single_event():
    engine = RuleEngine()

    active_events = [{
        "event": "long_rate_drop",
        "severity": 2,
        "value": -0.65,
        "description": "Rates dropped"
    }]

    results = engine.calculate_industry_scores(active_events)
    rankings = results["rankings"]

    # Check that real_estate has top ranking (base_weight: 50*2 (real_estate) + 30*2 (housing) = +160)
    real_estate = next((r for r in rankings if r["sector"] == "real_estate"), None)
    assert real_estate is not None
    assert real_estate["score"] == 160.0
    assert real_estate["normalized_score"] == 1.0

    # bank base weight is -30 * severity 2 = -60. Normalized: -60 / 160 = -0.375
    bank = next((r for r in rankings if r["sector"] == "bank"), None)
    assert bank is not None
    assert bank["score"] == -60.0
    assert bank["normalized_score"] == -0.375

def test_rule_engine_multiple_events_summation():
    engine = RuleEngine()

    # Firing multiple events:
    # 1. long_rate_drop with severity 2 (real_estate gets +160, bank gets -60)
    # 2. inflation_high with severity 1 (materials gets +30, retail gets -70)
    # 3. ai_investment_boom with severity 2 (semiconductor gets +200, telecom gets +80)
    active_events = [
        {"event": "long_rate_drop", "severity": 2, "value": -0.65},
        {"event": "inflation_high", "severity": 1, "value": 3.2},
        {"event": "ai_investment_boom", "severity": 2, "value": 2.0}
    ]

    results = engine.calculate_industry_scores(active_events)
    rankings = results["rankings"]

    semi = next((r for r in rankings if r["sector"] == "semiconductor"), None)
    assert semi is not None
    assert semi["score"] == 200.0

    re = next((r for r in rankings if r["sector"] == "real_estate"), None)
    assert re is not None
    assert re["score"] == 160.0

    mat = next((r for r in rankings if r["sector"] == "materials"), None)
    assert mat is not None
    assert mat["score"] == 30.0

    ret = next((r for r in rankings if r["sector"] == "retail"), None)
    assert ret is not None
    assert ret["score"] == -70.0

def test_event_detector_g20_events():
    detector = EventDetector()

    # 1. CB Rate hike from 0.1% to 0.35% (diff 0.25 -> severity 2)
    events = detector.detect_events({"POLICY_RATE": [0.1, 0.35]})
    hike = next((e for e in events if e["event"] == "rate_hike"), None)
    assert hike is not None
    assert hike["severity"] == 2
    assert hike["value"] == pytest.approx(0.25)

    # 2. CB Rate cut from 0.5% to 0.25% (diff -0.25 -> severity 2)
    events = detector.detect_events({"POLICY_RATE": [0.5, 0.25]})
    cut = next((e for e in events if e["event"] == "rate_cut"), None)
    assert cut is not None
    assert cut["severity"] == 2
    assert cut["value"] == pytest.approx(-0.25)

    # 3. Confidence contraction (below 100 threshold -> contraction severity 2)
    events = detector.detect_events({"CONFIDENCE": [98.5]})
    contraction = next((e for e in events if e["event"] == "business_contraction"), None)
    assert contraction is not None
    assert contraction["severity"] == 2

    # 4. Labor Tightening (unemployment drop 2.5% to 2.2% -> severity 2)
    events = detector.detect_events({"UNEMPLOYMENT": [2.5, 2.2]})
    labor = next((e for e in events if e["event"] == "labor_market_tightening"), None)
    assert labor is not None

    # 5. Yield Curve Inversion (10Y = 0.5, Policy = 0.6 -> spread -0.1 -> inverted severity 2)
    events = detector.detect_events({"YIELD_10Y": [0.5], "POLICY_RATE": [0.6, 0.6]})
    inv = next((e for e in events if e["event"] == "yield_curve_inversion"), None)
    assert inv is not None

def test_rule_engine_g20_rate_hike():
    engine = RuleEngine()

    active_events = [
        {"event": "rate_hike", "severity": 2, "value": 0.25}
    ]

    results = engine.calculate_industry_scores(active_events)
    rankings = results["rankings"]

    # Check bank gets 30 * 2 = 60
    bank = next((r for r in rankings if r["sector"] == "bank"), None)
    assert bank is not None
    assert bank["score"] == 60.0

    # Check real_estate gets -30 * 2 = -60
    re = next((r for r in rankings if r["sector"] == "real_estate"), None)
    assert re is not None
    assert re["score"] == -60.0


def test_event_detector_commodity_futures():
    detector = EventDetector()

    # Gold price spikes from 2000 to 2200 (+10% change -> severity 1)
    events = detector.detect_events({"GOLD_PRICE": [2000.0, 2200.0]})
    gold_spike = next((e for e in events if e["event"] == "gold_price_spike"), None)
    assert gold_spike is not None
    assert gold_spike["severity"] == 1

    # Copper price drops from 4.0 to 3.5 (-12.5% change -> severity 1)
    events = detector.detect_events({"COPPER_PRICE": [4.0, 3.5]})
    copper_crash = next((e for e in events if e["event"] == "copper_price_crash"), None)
    assert copper_crash is not None
    assert copper_crash["severity"] == 1

    # Natural Gas spikes from 2.0 to 3.0 (+50% change -> severity 3)
    events = detector.detect_events({"NATURAL_GAS": [2.0, 3.0]})
    gas_spike = next((e for e in events if e["event"] == "natural_gas_spike"), None)
    assert gas_spike is not None
    assert gas_spike["severity"] == 3


def test_event_detector_currency_and_liquidity():
    detector = EventDetector()

    # Case A: Local currency weakening (indirect quote USD/JPY rises by +3% -> severity 1)
    events = detector.detect_events({"LOCAL_CURRENCY": [150.0, 154.5], "CURRENCY_QUOTE": "indirect"})
    weakening = next((e for e in events if e["event"] == "currency_weakening"), None)
    assert weakening is not None
    assert weakening["severity"] == 1
    assert weakening["value"] == pytest.approx(3.0)

    # Case B: Local currency strengthening (direct quote EUR/USD rises by +3% -> severity 1)
    events = detector.detect_events({"LOCAL_CURRENCY": [1.08, 1.1124], "CURRENCY_QUOTE": "direct"})
    strengthening = next((e for e in events if e["event"] == "currency_strengthening"), None)
    assert strengthening is not None
    assert strengthening["severity"] == 1
    assert strengthening["value"] == pytest.approx(3.0)

    # Case C: Liquidity contraction (M2 YoY growth = 0.5% -> severity 1)
    events = detector.detect_events({"MONEY_SUPPLY": [5.0, 0.5]})
    liquidity = next((e for e in events if e["event"] == "liquidity_contraction"), None)
    assert liquidity is not None
    assert liquidity["severity"] == 1
