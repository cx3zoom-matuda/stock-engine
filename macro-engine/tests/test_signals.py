import pytest
from src.signal.detector import SignalDetector

def test_signal_detector_yield_inversion():
    detector = SignalDetector()
    
    # Construct an inverted yield curve mock data (10Y = 3.5%, 2Y = 4.0%)
    mock_dgs10 = [{"date": f"2026-05-{i:02d}", "value": "3.50"} for i in range(1, 10)]
    mock_dgs2 = [{"date": f"2026-05-{i:02d}", "value": "4.00"} for i in range(1, 10)]
    
    raw_data = {
        "DGS10": mock_dgs10,
        "DGS2": mock_dgs2,
        "CPIAUCSL": [],
        "DCOILWTICO": [],
        "DEXJPUS": []
    }
    
    signals = detector.detect_signals(raw_data)
    
    assert signals["YIELD_INVERSION"]["active"] is True
    assert signals["YIELD_INVERSION"]["value"] == -0.5
    assert signals["YIELD_FLATTENING"]["active"] is False

def test_signal_detector_yield_flattening():
    detector = SignalDetector()
    
    # Spread is 0.3% (flat but not inverted)
    mock_dgs10 = [{"date": f"2026-05-{i:02d}", "value": "3.80"} for i in range(1, 10)]
    mock_dgs2 = [{"date": f"2026-05-{i:02d}", "value": "3.50"} for i in range(1, 10)]
    
    raw_data = {
        "DGS10": mock_dgs10,
        "DGS2": mock_dgs2,
        "CPIAUCSL": [],
        "DCOILWTICO": [],
        "DEXJPUS": []
    }
    
    signals = detector.detect_signals(raw_data)
    
    assert signals["YIELD_INVERSION"]["active"] is False
    assert signals["YIELD_FLATTENING"]["active"] is True
    assert signals["YIELD_FLATTENING"]["value"] == pytest.approx(0.3)
