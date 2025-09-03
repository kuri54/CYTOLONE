import pandas as pd
from configparser import ConfigParser

def load_config(config_file_path="./CYTOLONE/config.ini"):
    parser = ConfigParser()
    parser.read(config_file_path)

    return {
        "LANGUAGE": parser["SETTINGS"]["LANGUAGE"],
        "MODEL": parser["SETTINGS"]["MODEL"],
        "LLM_MODEL": parser["SETTINGS"]["LLM_MODEL"],
        "LLM_GEN": parser.getboolean("SETTINGS", "LLM_GEN"),
        "LLM_GEN_THRESHOLD": parser.getfloat("SETTINGS", "LLM_GEN_THRESHOLD"),
        "WEBCAM_IMAGE_SIZE": parser.getint("SETTINGS", "WEBCAM_IMAGE_SIZE"),
        "DEBUG": parser.getboolean("SETTINGS", "DEBUG"),
    }

def build_config_df(config):
    rows = [
        {"Section": "Language",     "Item": "Language",          "Value": f"{config['LANGUAGE']}"},
        {"Section": "Model",        "Item": "Model",             "Value": f"{config['MODEL']}"},
        {"Section": "",             "Item": "LLM Model",         "Value": f"{config['LLM_MODEL']}"},
        {"Section": "LLM Generate", "Item": "Genenerate",        "Value": f"{config['LLM_GEN']}"},
        {"Section": "",             "Item": "Threshold",         "Value": f"{config['LLM_GEN_THRESHOLD']}"},
        {"Section": "Device",       "Item": "Webcam Image Size", "Value": f"{config['WEBCAM_IMAGE_SIZE']}"},
    ]
    return pd.DataFrame(rows, columns=["Section", "Item", "Value"])
