"""Monthly HICP air fare index for Germany, from the Eurostat statistics API."""

from .common import SourceFailed, get_json

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


def parse_index(payload):
    """Decode a JSON-stat response, whose values are keyed by a flattened position."""
    dimensions = payload["id"]
    sizes = payload["size"]
    codes = {
        name: {pos: code for code, pos in payload["dimension"][name]["category"]["index"].items()}
        for name in dimensions
    }

    rows = []
    for flat, value in payload["value"].items():
        remainder = int(flat)
        position = {}
        for name, size in zip(reversed(dimensions), reversed(sizes)):
            remainder, position[name] = divmod(remainder, size)
        rows.append(
            {
                "period": codes["time"][position["time"]],
                "coicop": codes["coicop18"][position["coicop18"]],
                "unit": codes["unit"][position["unit"]],
                "value": value,
            }
        )
    return sorted(rows, key=lambda row: (row["coicop"], row["unit"], row["period"]))


def collect(config, get=get_json):
    params = {
        "format": "JSON",
        "lang": "EN",
        "geo": config["geo"],
        "coicop18": config["coicop"],
        "unit": config["units"],
    }
    rows = parse_index(get(f"{BASE_URL}/{config['dataset']}", params=params))
    if not rows:
        raise SourceFailed("Eurostat returned no values")
    return rows
