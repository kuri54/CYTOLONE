import os
import argparse
import shutil
from configparser import ConfigParser

CONFIG_PATH = "CYTOLONE/config.ini"
DEFAULT_CONFIG_PATH = "CYTOLONE/default_config/default_config.ini"

def read_config(path=CONFIG_PATH):
    config = ConfigParser()
    config.optionxform = str
    config.read(path)
    return config

def write_config(config, path=CONFIG_PATH):
    with open(path, 'w') as configfile:
        config.write(configfile)

def list_config():
    config = read_config()
    print("Current configuration: ")
    for key in config["SETTINGS"]:
        print(f"{key} = {config['SETTINGS'][key]}")

def reset_config():
    if os.path.exists(DEFAULT_CONFIG_PATH):
        shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
        print("Configuration has been reset to defaults.")
    else:
        print("default_config.ini not found.")

def update_config(args):
    config = read_config()

    for key, value in vars(args).items():
        if key in config["SETTINGS"] and value is not None:
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
    parser.add_argument("--LLM_MODEL", choices=["deepseek-r1", "gpt-oss-120b", "gpt-oss-20b"])
    parser.add_argument("--LLM_GEN", choices=["True", "False"])
    parser.add_argument("--LLM_GEN_THRESHOLD", type=float)
    parser.add_argument("--WEBCAM_IMAGE_SIZE", type=int)
    parser.add_argument("--DEBUG", choices=["True", "False"])

    args = parser.parse_args()

    if args.list:
        list_config()
    elif args.reset:
        reset_config()
    else:
        update_config(args)

if __name__ == "__main__":
    main()
