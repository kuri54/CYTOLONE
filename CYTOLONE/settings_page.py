import gradio as gr

from CYTOLONE.app_paths import config_path
from CYTOLONE.default_config.config_manager import read_config, write_config
from CYTOLONE.model import (
    APP_MODEL_CHOICES,
    LLM_MODEL_CHOICES,
    LLM_MODEL_DISPLAY_CHOICES,
)


def _settings_section():
    config = read_config()
    return config["SETTINGS"]


def get_settings_values():
    settings = _settings_section()
    return (
        settings["LANGUAGE"],
        settings["MODEL"],
        settings["LLM_MODEL"],
        settings.getint("WEBCAM_IMAGE_SIZE"),
        settings.getboolean("DEBUG"),
    )


def _as_bool(value, key):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError(f"{key} must be True or False")


def _as_int(value, key, minimum=None, maximum=None):
    try:
        parsed = int(value)
        if float(value) != parsed:
            raise ValueError
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{key} must be at most {maximum}")
    return parsed


def validate_settings(
    language,
    model,
    llm_model,
    webcam_image_size,
    debug,
):
    if language not in {"en", "ja"}:
        raise ValueError("LANGUAGE must be en or ja")
    if model not in APP_MODEL_CHOICES:
        raise ValueError(f"MODEL must be one of: {', '.join(APP_MODEL_CHOICES)}")
    if llm_model not in LLM_MODEL_CHOICES:
        raise ValueError(f"LLM_MODEL must be one of: {', '.join(LLM_MODEL_CHOICES)}")

    values = {
        "LANGUAGE": language,
        "MODEL": model,
        "LLM_MODEL": llm_model,
        "WEBCAM_IMAGE_SIZE": _as_int(webcam_image_size, "WEBCAM_IMAGE_SIZE", 1, 8192),
        "DEBUG": _as_bool(debug, "DEBUG"),
    }
    return values


def apply_settings(
    language,
    model,
    llm_model,
    webcam_image_size,
    debug,
):
    values = validate_settings(
        language,
        model,
        llm_model,
        webcam_image_size,
        debug,
    )

    # Only normal UI settings are updated. Hidden LLM tuning values are kept.
    config = read_config()
    config["SETTINGS"].update(
        {
            key: str(value) for key, value in values.items()
        }
    )
    write_config(config)

    return (
        *get_settings_values(),
        (
            f"Settings saved to {config_path()}.\n"
            "CYTOLONE Main and Model Management will use the updated settings immediately.\n"
            "The selected LLM can be downloaded independently of manual generation."
        ),
    )


def build_settings_page():
    values = get_settings_values()

    gr.Markdown("# Settings")

    language = gr.Dropdown(
        choices=["en", "ja"],
        value=values[0],
        label="LANGUAGE",
    )
    model = gr.Dropdown(
        choices=APP_MODEL_CHOICES,
        value=values[1],
        label="MODEL",
    )
    llm_model = gr.Dropdown(
        choices=LLM_MODEL_DISPLAY_CHOICES,
        value=values[2],
        label="LLM_MODEL",
    )
    webcam_image_size = gr.Number(
        value=values[3],
        label="WEBCAM_IMAGE_SIZE",
        minimum=1,
        maximum=8192,
        precision=0,
    )
    debug = gr.Checkbox(
        value=values[4],
        label="DEBUG",
    )

    apply_btn = gr.Button("Apply", variant="primary")
    status = gr.Textbox(label="Status", lines=3, interactive=False)

    inputs = [
        language,
        model,
        llm_model,
        webcam_image_size,
        debug,
    ]
    return inputs, apply_btn, status
