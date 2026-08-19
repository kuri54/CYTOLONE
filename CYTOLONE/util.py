import pandas as pd

from CYTOLONE.default_config.config_manager import read_config
from CYTOLONE.model import get_llm_spec

def load_config(config_file_path=None):
    parser = read_config(config_file_path)

    return {
        "LANGUAGE": parser["SETTINGS"]["LANGUAGE"],
        "MODEL": parser["SETTINGS"]["MODEL"],
        "LLM_MODEL": parser["SETTINGS"]["LLM_MODEL"],
        "LLM_GEN": parser.getboolean("SETTINGS", "LLM_GEN"),
        "LLM_GEN_THRESHOLD": parser.getfloat("SETTINGS", "LLM_GEN_THRESHOLD"),
        "LLM_MAX_TOKENS": parser.getint("SETTINGS", "LLM_MAX_TOKENS"),
        "LLM_TEMPERATURE": parser.getfloat("SETTINGS", "LLM_TEMPERATURE"),
        "LLM_TOP_P": parser.getfloat("SETTINGS", "LLM_TOP_P"),
        "LLM_TOP_K": parser.getint("SETTINGS", "LLM_TOP_K"),
        "LLM_SEED": parser.getint("SETTINGS", "LLM_SEED"),
        "WEBCAM_IMAGE_SIZE": parser.getint("SETTINGS", "WEBCAM_IMAGE_SIZE"),
        "DEBUG": parser.getboolean("SETTINGS", "DEBUG"),
    }

def build_config_df(config):
    llm_model_key = config.get("LLM_MODEL", "")
    try:
        llm_model_display_name = get_llm_spec(llm_model_key).display_name
    except ValueError:
        llm_model_display_name = str(llm_model_key)

    rows = [
        {"Section": "Language",     "Item": "Language",          "Value": f"{config['LANGUAGE']}"},
        {"Section": "Model",        "Item": "Model",             "Value": f"{config['MODEL']}"},
        {"Section": "Model",        "Item": "LLM Model",          "Value": llm_model_display_name},
        {"Section": "Device",       "Item": "Webcam Image Size", "Value": f"{config['WEBCAM_IMAGE_SIZE']}"},
    ]
    return pd.DataFrame(rows, columns=["Section", "Item", "Value"])
