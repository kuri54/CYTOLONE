import gradio as gr
from configparser import ConfigParser

from CYTOLONE.app_paths import config_path
from CYTOLONE.default_config.config_manager import read_config, write_config
from CYTOLONE.model import APP_MODEL_CHOICES, LLM_MODEL_CHOICES


CONFIG_KEYS = [
    "LANGUAGE",
    "MODEL",
    "LLM_MODEL",
    "LLM_GEN",
    "LLM_GEN_THRESHOLD",
    "WEBCAM_IMAGE_SIZE",
    "DEBUG",
]


def _settings_section():
    config = read_config()
    if "SETTINGS" not in config:
        config = read_config(path="CYTOLONE/default_config/default_config.ini", fallback_to_default=False)
    return config["SETTINGS"]


def get_settings_values():
    settings = _settings_section()
    return (
        settings["LANGUAGE"],
        settings["MODEL"],
        settings["LLM_MODEL"],
        settings["LLM_GEN"],
        float(settings["LLM_GEN_THRESHOLD"]),
        int(settings["WEBCAM_IMAGE_SIZE"]),
        settings["DEBUG"],
    )


def apply_settings(language, model, llm_model, llm_gen, llm_threshold, webcam_image_size, debug):
    config = ConfigParser()
    config.optionxform = str
    config["SETTINGS"] = {
        "LANGUAGE": language,
        "MODEL": model,
        "LLM_MODEL": llm_model,
        "LLM_GEN": llm_gen,
        "LLM_GEN_THRESHOLD": str(llm_threshold),
        "WEBCAM_IMAGE_SIZE": str(int(webcam_image_size)),
        "DEBUG": debug,
    }
    write_config(config)

    return (*get_settings_values(), (
        f"Settings saved to {config_path()}.\n"
        "CYTOLONE Main and Model Download will use the updated settings immediately.\n"
        "If scale-check camera sizing looks stale, reload the app before using scale-check."
    ))


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
        choices=LLM_MODEL_CHOICES,
        value=values[2],
        label="LLM_MODEL",
    )
    llm_gen = gr.Dropdown(
        choices=["True", "False"],
        value=values[3],
        label="LLM_GEN",
    )
    llm_threshold = gr.Number(
        value=values[4],
        label="LLM_GEN_THRESHOLD",
        precision=2,
    )
    webcam_image_size = gr.Number(
        value=values[5],
        label="WEBCAM_IMAGE_SIZE",
        precision=0,
    )
    debug = gr.Dropdown(
        choices=["True", "False"],
        value=values[6],
        label="DEBUG",
    )

    apply_btn = gr.Button("Apply", variant="primary")
    status = gr.Textbox(label="Status", lines=3, interactive=False)

    inputs = [
        language,
        model,
        llm_model,
        llm_gen,
        llm_threshold,
        webcam_image_size,
        debug,
    ]
    return inputs, apply_btn, status
