from configparser import ConfigParser

def load_config(config_file_path="./CYTOLONE/config.ini"):
    parser = ConfigParser()
    parser.read(config_file_path)

    return {
        "LANGUAGE": parser["SETTINGS"]["LANGUAGE"],
        "MODEL": parser["SETTINGS"]["MODEL"],
        "LLM_GEN": parser.getboolean("SETTINGS", "LLM_GEN"),
        "LLM_GEN_THRESHOLD": parser.getfloat("SETTINGS", "LLM_GEN_THRESHOLD"),
        "WEBCAM_IMAGE_SIZE": parser.getint("SETTINGS", "WEBCAM_IMAGE_SIZE"),
        "DEBUG": parser.getboolean("SETTINGS", "DEBUG"),
    }