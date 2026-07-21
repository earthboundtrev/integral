"""SPEC-319 practice→symptom correlations."""

from datetime import date, timedelta

from insights.engine import analyze_practice_symptom_correlations


def _day(base: date, offset: int) -> str:
    return (base - timedelta(days=offset)).strftime("%Y-%m-%d")


def _build(today: date):
    """Days 0-5 have practice + low gas; days 6-11 no practice + high gas."""
    entries: dict = {}
    practices: dict = {"items": []}
    for offset in range(0, 6):
        d = _day(today, offset)
        entries[d] = {"Gut Health / Digestion": {"rating": 6, "metrics": {"Gas / bloating (lower = better)": 3}}}
        practices["items"].append({"date": d, "name": "Breathing"})
    for offset in range(6, 12):
        d = _day(today, offset)
        entries[d] = {"Gut Health / Digestion": {"rating": 5, "metrics": {"Gas / bloating (lower = better)": 6}}}
    return entries, practices


def test_correlation_detects_lower_gas_on_practice_days():
    today = date(2026, 7, 21)
    entries, practices = _build(today)
    findings = analyze_practice_symptom_correlations(entries, practices, today)
    assert findings, "expected a correlation finding"
    gas = next(f for f in findings if "Gas" in f.message)
    assert "lower with practice" in gas.message
    # Lower gas on practice days is good → positive severity.
    assert gas.severity == "positive"


def test_no_finding_below_min_samples():
    today = date(2026, 7, 21)
    entries: dict = {}
    practices: dict = {"items": []}
    # Only 2 practice days → below default min_samples (3).
    for offset in range(0, 2):
        d = _day(today, offset)
        entries[d] = {"Gut": {"metrics": {"Gas": 3}}}
        practices["items"].append({"date": d, "name": "X"})
    for offset in range(2, 8):
        entries[_day(today, offset)] = {"Gut": {"metrics": {"Gas": 6}}}
    assert analyze_practice_symptom_correlations(entries, practices, today) == []


def test_no_finding_without_practices():
    today = date(2026, 7, 21)
    entries, _ = _build(today)
    assert analyze_practice_symptom_correlations(entries, {"items": []}, today) == []


def test_higher_energy_on_practice_is_positive():
    today = date(2026, 7, 21)
    entries: dict = {}
    practices: dict = {"items": []}
    for offset in range(0, 5):
        d = _day(today, offset)
        entries[d] = {"Energy & Recovery": {"metrics": {"Morning energy": 8}}}
        practices["items"].append({"date": d, "name": "Rites"})
    for offset in range(5, 11):
        entries[_day(today, offset)] = {"Energy & Recovery": {"metrics": {"Morning energy": 5}}}
    findings = analyze_practice_symptom_correlations(entries, practices, today)
    energy = next(f for f in findings if "energy" in f.message.lower())
    assert "higher with practice" in energy.message
    assert energy.severity == "positive"
