import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from CYTOLONE.app_paths import config_path, debug_path, models_path
from CYTOLONE.default_config.config_manager import read_config, write_config


class AppPathTests(unittest.TestCase):
    def test_unset_environment_preserves_cli_relative_paths(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(config_path(), Path("CYTOLONE/config.ini"))
            self.assertEqual(models_path(), Path("mlx_models"))
            self.assertEqual(debug_path(), Path("debug_images"))

    def test_app_environment_separates_data_from_bundled_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(temporary) / "Data"
            with patch.dict(os.environ, {"CYTOLONE_DATA_ROOT": str(data_root)}):
                self.assertEqual(config_path(), data_root / "config.ini")
                self.assertEqual(models_path(), data_root / "Models")
                self.assertEqual(debug_path(), data_root / "Debug")

    def test_config_manager_uses_app_data_root_without_changing_default_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(temporary) / "Data"
            with patch.dict(os.environ, {"CYTOLONE_DATA_ROOT": str(data_root)}):
                config = read_config()
                self.assertEqual(config["SETTINGS"]["MODEL"], "v1.1")
                config["SETTINGS"]["MODEL"] = "v1.0"
                write_config(config)
                self.assertEqual(read_config()["SETTINGS"]["MODEL"], "v1.0")
                self.assertFalse((Path("CYTOLONE") / "config.ini").exists())


if __name__ == "__main__":
    unittest.main()
