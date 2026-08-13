import os
import argparse
import shutil
from configparser import ConfigParser
from pathlib import Path

from CYTOLONE.app_paths import config_path
from CYTOLONE.config_validation import validate_llm_settings

CONFIG_PATH = "CYTOLONE/config.ini"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "default_config.ini"


def _default_config():
    defaults = ConfigParser()
    defaults.optionxform = str
    if DEFAULT_CONFIG_PATH.exists():
        defaults.read(DEFAULT_CONFIG_PATH)
    return defaults


def _merge_default_settings(config):
    defaults = _default_config()
    if "SETTINGS" not in config:
        config["SETTINGS"] = {}
    if "SETTINGS" in defaults:
        for key, value in defaults["SETTINGS"].items():
            config["SETTINGS"].setdefault(key, value)
    return config


def read_config(path=None, fallback_to_default=True):
    config = ConfigParser()
    config.optionxform = str
    path = config_path() if path is None else Path(path)
    if os.path.exists(path):
        config.read(path)
    elif fallback_to_default and DEFAULT_CONFIG_PATH.exists():
        config.read(DEFAULT_CONFIG_PATH)
    return _merge_default_settings(config)


def write_config(config, path=None):
    path = config_path() if path is None else Path(path)
    config_dir = path.parent
    if config_dir:
        config_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as configfile:
        config.write(configfile)

def list_config():
    config = read_config()
    print("Current configuration: ")
    for key in config["SETTINGS"]:
        print(f"{key} = {config['SETTINGS'][key]}")

def reset_config():
    if DEFAULT_CONFIG_PATH.exists():
        shutil.copy(DEFAULT_CONFIG_PATH, config_path())
        print("Configuration has been reset to defaults.")
    else:
        print("default_config.ini not found.")

def update_config(args):
    config = read_config()
    updates = {
        key: value
        for key, value in vars(args).items()
        if key in config["SETTINGS"] and value is not None
    }
    validate_llm_settings(updates)

    for key, value in updates.items():
        config["SETTINGS"][key] = str(value)

    write_config(config)
    print("Configuration updated.")

def main():
    parser = argparse.ArgumentParser(description="INI Configuration Manager")
    parser.add_argument("--list", action="store_true", help="Display current configuration")
    parser.add_argument("--reset", action="store_true", help="Reset configuration using default_config.ini")

    # Updatable Keys
    parser.add_argument("--LANGUAGE", choices=["ja", "en"])
    parser.add_argument("--MODEL", choices=["v1.0", "v1.1"])
    parser.add_argument(
        "--LLM_MODEL",
        choices=[
            "qwen3.5-9b-4bit",
            "qwen3.5-9b-8bit",
            "qwen3.5-27b-5bit",
            "qwen3.5-27b-8bit",
            "gpt-oss-120b",
            "gpt-oss-20b",
            "deepseek-r1",
        ],
    )
    parser.add_argument("--LLM_GEN", choices=["True", "False"])
    parser.add_argument("--LLM_GEN_THRESHOLD", type=float)
    parser.add_argument("--LLM_MAX_TOKENS", type=int)
    parser.add_argument("--LLM_TEMPERATURE", type=float)
    parser.add_argument("--LLM_TOP_P", type=float)
    parser.add_argument("--LLM_TOP_K", type=int)
    parser.add_argument("--LLM_SEED", type=int)
    parser.add_argument("--WEBCAM_IMAGE_SIZE", type=int)
    parser.add_argument("--DEBUG", choices=["True", "False"])

    args = parser.parse_args()

    if args.list:
        list_config()
    elif args.reset:
        reset_config()
    else:
        try:
            update_config(args)
        except ValueError as exc:
            parser.error(str(exc))

if __name__ == "__main__":
    main()
