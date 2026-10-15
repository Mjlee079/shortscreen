"""JSON schema validation for casino bonus scrape output.

Validates the structure of casinos.json before it is written or consumed
by the frontend, ensuring the 4 required fields are present and correctly
typed.
"""

from typing import Any

# JSON Schema for the casinos.json output file.
CASINOS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Casino Bonus Scrape Output",
    "type": "object",
    "required": ["casinos", "source", "count"],
    "properties": {
        "casinos": {
            "type": "array",
            "minItems": 1,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": [
                    "name",
                    "welcome_bonus",
                    "wagering_requirement",
                    "minimum_deposit",
                    "source_url",
                    "scraped_at",
                ],
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "welcome_bonus": {"type": ["string", "null"]},
                    "wagering_requirement": {"type": ["integer", "null"]},
                    "minimum_deposit": {"type": ["string", "null"]},
                    "source_url": {"type": "string", "format": "uri"},
                    "scraped_at": {"type": "string", "format": "date-time"},
                },
                "additionalProperties": False,
            },
        },
        "source": {"type": "string"},
        "count": {"type": "integer", "minimum": 1, "maximum": 3},
    },
    "additionalProperties": False,
}


def validate_casinos_data(data: dict[str, Any]) -> list[str]:
    """Validate a casinos data dictionary against the schema.

    Args:
        data: The parsed JSON data from casinos.json.

    Returns:
        A list of human-readable error messages. An empty list means valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Top-level JSON must be an object"]

    # Validate required top-level keys
    for key in ("casinos", "source", "count"):
        if key not in data:
            errors.append(f"Missing required top-level field: {key}")

    if errors:
        return errors

    # Validate casinos array
    casinos = data.get("casinos")
    if not isinstance(casinos, list):
        errors.append("Field 'casinos' must be an array")
    else:
        if len(casinos) < 1 or len(casinos) > 3:
            errors.append("Field 'casinos' must contain between 1 and 3 items")
        for idx, casino in enumerate(casinos):
            if not isinstance(casino, dict):
                errors.append(f"casinos[{idx}] must be an object")
                continue
            for field in (
                "name",
                "welcome_bonus",
                "wagering_requirement",
                "minimum_deposit",
                "source_url",
                "scraped_at",
            ):
                if field not in casino:
                    errors.append(f"casinos[{idx}] missing required field: {field}")
            wagering = casino.get("wagering_requirement")
            if wagering is not None and not isinstance(wagering, int):
                errors.append(
                    f"casinos[{idx}].wagering_requirement must be an integer or null, "
                    f"got {type(wagering).__name__}"
                )

    # Validate source
    if not isinstance(data.get("source"), str) or not data["source"]:
        errors.append("Field 'source' must be a non-empty string")

    # Validate count
    count = data.get("count")
    if not isinstance(count, int) or count < 1 or count > 3:
        errors.append("Field 'count' must be an integer between 1 and 3")

    return errors