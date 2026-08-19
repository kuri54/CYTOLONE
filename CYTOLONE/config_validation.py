import math


LLM_SETTING_LIMITS = {
    "LLM_GEN_THRESHOLD": (float, 0.0, 1.0),
    "LLM_MAX_TOKENS": (int, 1, 8192),
    "LLM_TEMPERATURE": (float, 0.0, 2.0),
    "LLM_TOP_P": (float, 0.0, 1.0),
    "LLM_TOP_K": (int, 0, 10000),
    "LLM_SEED": (int, 0, 2**32 - 1),
}


def validate_llm_settings(values):
    """Validate and normalize the LLM numeric settings present in values."""

    normalized = {}
    for key, value in values.items():
        if key not in LLM_SETTING_LIMITS:
            continue

        value_type, minimum, maximum = LLM_SETTING_LIMITS[key]
        if isinstance(value, bool):
            raise ValueError(f"{key} must be a number")
        try:
            if value_type is int:
                parsed = int(value)
                if float(value) != parsed:
                    raise ValueError
            else:
                parsed = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{key} must be a {value_type.__name__}") from exc

        if value_type is float and not math.isfinite(parsed):
            raise ValueError(f"{key} must be finite")
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{key} must be between {minimum} and {maximum}")
        normalized[key] = parsed

    return normalized
