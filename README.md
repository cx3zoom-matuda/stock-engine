# Macro → Industry Translation Engine (MVP)

A modular Python framework to translate real-time macroeconomic event triggers into ranked impact scores for 17 key industry sectors, strictly matching the specifications in `MEMORY.md` and `MEMORY2.md`.

## System Overview

```
Macro Time-Series
       ↓ (EventDetector)
Macro Events with Severities
       ↓ (RuleEngine + Impact Matrix)
17 Ranked Industry Scores
```

## Directory Structure

```
/Users/p/developer/services/translation-engine/
├── README.md                 # Project documentation
├── requirements.txt          # Python dependencies (pandas, numpy, pytest)
├── main.py                   # Demonstration CLI runner with synthetic data
├── src/
│   ├── __init__.py
│   ├── schema.py             # 17 Core sectors, subsector mapping, and impact matrix weights
│   ├── detector.py           # EventDetector (processes rates, inflation, oil, forex and GDP trends)
│   └── engine.py             # RuleEngine (aggregates weights * severity and outputs rankings)
└── tests/
    ├── __init__.py
    └── test_translation.py   # Unit tests validating thresholds, severities, and score logic
```

## Core Calculations

1. **Severity Scaling:** Macro trend movements are parsed into three severity levels: `1` (minor), `2` (moderate), and `3` (major) based on progressive change thresholds.
2. **Subsector Aggregation:** Granular subsectors and industry labels are mapped back onto the 17 core industry taxonomy classes defined in `MEMORY.md`.
3. **Cumulative Scoring:** Multiple simultaneously active events are aggregated linearly:
   $$\text{Industry Score} = \sum (\text{Base Impact Weight} \times \text{Severity})$$
4. **Normalization:** Scores are normalized relative to the maximum absolute score of any sector during that run to scale the results within $[-1, 1]$.

## Setup & API Configurations

### FRED API Key Configuration
To fetch data using FRED's authenticated JSON API:
1. Register for a free API key at the Federal Reserve Bank of St. Louis: [FRED API Key Signup](https://fred.stlouisfed.org/api_key.html).
2. Configure the key using one of the following methods:
   - **Method A (.env file):** Create a `.env` file in the root of `/Users/p/developer/services/translation-engine/` containing:
     ```env
     FRED_API_KEY=your_actual_fred_api_key_here
     ```
   - **Method B (Environment Variable):** Export it directly in your shell session:
     ```bash
     export FRED_API_KEY="your_actual_fred_api_key_here"
     ```

> [!NOTE]
> **Public Fallback Mode:** If no `FRED_API_KEY` is provided, the data ingestion layer will print a warning and automatically redirect queries to FRED's public CSV export endpoints. This allows the engine to run immediately without requiring manual token registration.

## How to Run

### Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run Demonstration CLI Script
```bash
python main.py
```

### Run Unit Tests
```bash
pytest tests/
```
