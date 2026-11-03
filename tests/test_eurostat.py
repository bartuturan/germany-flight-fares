import json
from pathlib import Path

import pytest

from scraper import eurostat
from scraper.common import SourceFailed

FIXTURE = Path(__file__).parent / "fixtures" / "eurostat_index.json"
CONFIG = {"dataset": "x", "geo": "DE", "coicop": ["CP0733"], "units": ["I25"]}


def load():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_decodes_every_value_to_its_own_dimensions():
    rows = eurostat.parse_index(load())
    values = {(r["coicop"], r["unit"], r["period"]): r["value"] for r in rows}
    assert len(rows) == 8
    # Each figure was also read from Eurostat directly, per code and unit.
    assert values["CP0733", "I25", "2026-09"] == 100.49
    assert values["CP07331", "I25", "2026-09"] == 112.79
    assert values["CP0733", "I15", "2026-09"] == 129.51
    assert values["CP07331", "I15", "2026-09"] == 153.81


def test_no_values_is_a_failure():
    payload = load()
    payload["value"] = {}
    with pytest.raises(SourceFailed):
        eurostat.collect(CONFIG, get=lambda url, params: payload)
