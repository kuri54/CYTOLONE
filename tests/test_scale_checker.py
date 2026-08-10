import unittest
from configparser import ConfigParser
from unittest.mock import patch

import cv2
import gradio as gr
import numpy as np
from PIL import Image, ImageEnhance

from CYTOLONE.scale_check.scale_checker import (
    MAX_SCALE,
    MIN_SCALE,
    SCALE_CHECKER_LOUPE_CSS,
    SCALE_CHECKER_LOUPE_JS,
    TARGET_SIZE,
    apply_scale_to_config,
    build_scale_checker_page,
    estimate_scale_from_nuclei,
    extract_nucleus_from_click,
    overlay_and_calculate,
)


def make_synthetic_smear():
    image = np.full((160, 160, 3), (245, 245, 245), dtype=np.uint8)
    cv2.ellipse(image, (70, 80), (35, 25), 0, 0, 360, (205, 150, 150), -1)
    cv2.ellipse(image, (110, 80), (25, 20), 0, 0, 360, (180, 205, 205), -1)
    cv2.ellipse(image, (70, 80), (8, 5), 0, 0, 360, (40, 65, 120), -1)
    cv2.ellipse(image, (110, 80), (7, 5), 0, 0, 360, (45, 70, 125), -1)
    return Image.fromarray(image)


def make_synthetic_cytoplasm_shell_leak():
    image = np.full((160, 160, 3), (245, 245, 245), dtype=np.uint8)
    cv2.ellipse(image, (80, 80), (35, 25), 0, 0, 360, (150, 190, 185), -1)
    # This darker, similarly colored patch makes the click-connected mask look
    # plausible while a real dark nucleus sits off-center inside the cell.
    cv2.ellipse(image, (84, 84), (12, 7), 0, 0, 360, (130, 175, 170), -1)
    cv2.ellipse(image, (68, 78), (7, 5), 0, 0, 360, (40, 70, 110), -1)
    return Image.fromarray(image)


def make_synthetic_jitter_smear():
    image = np.full((180, 180, 3), (245, 245, 245), dtype=np.uint8)
    cv2.ellipse(image, (80, 90), (42, 30), 8, 0, 360, (205, 150, 150), -1)
    cv2.ellipse(image, (130, 75), (30, 24), 0, 0, 360, (180, 205, 205), -1)
    cv2.ellipse(image, (80, 90), (12, 8), 8, 0, 360, (40, 65, 120), -1)
    cv2.ellipse(image, (130, 75), (9, 7), 0, 0, 360, (45, 70, 125), -1)
    return Image.fromarray(image)


def make_synthetic_size_sweep_smear(nucleus_diameter):
    image = np.full((220, 220, 3), (245, 245, 245), dtype=np.uint8)
    cv2.ellipse(image, (110, 110), (70, 55), 0, 0, 360, (205, 150, 150), -1)
    nucleus_axes = (
        max(2, int(round(nucleus_diameter * 0.575))),
        max(2, int(round(nucleus_diameter * 0.425))),
    )
    cv2.ellipse(image, (110, 110), nucleus_axes, 0, 0, 360, (40, 65, 120), -1)
    return Image.fromarray(image)


def make_synthetic_large_nucleus_shell():
    image = np.full((240, 240, 3), (245, 245, 245), dtype=np.uint8)
    cv2.ellipse(image, (120, 120), (80, 58), 0, 0, 360, (190, 205, 195), -1)
    cv2.ellipse(image, (120, 120), (23, 19), 0, 0, 360, (165, 190, 184), -1)
    cv2.ellipse(image, (120, 120), (5, 4), 0, 0, 360, (40, 65, 120), -1)
    return Image.fromarray(image)


class ScaleCheckerExtractionTests(unittest.TestCase):
    def test_click_seed_selects_the_seed_connected_nucleus(self):
        preview, diameter, error = extract_nucleus_from_click(make_synthetic_smear(), 70, 80, patch_radius=48)

        self.assertIsNotNone(preview)
        self.assertIsNotNone(diameter)
        self.assertGreater(diameter, 8.0)
        self.assertLess(diameter, 20.0)
        self.assertEqual(error, "")

    def test_nearby_nucleus_is_not_used_when_click_is_background(self):
        preview, diameter, error = extract_nucleus_from_click(make_synthetic_smear(), 90, 80, patch_radius=48)

        self.assertIsNone(preview)
        self.assertIsNone(diameter)
        self.assertTrue(error)
        self.assertIn("Please click", error)

    def test_low_confidence_cytoplasm_click_fails_closed(self):
        image = np.full((160, 160, 3), (245, 245, 245), dtype=np.uint8)
        cv2.ellipse(image, (80, 80), (40, 28), 0, 0, 360, (205, 170, 170), -1)

        preview, diameter, error = extract_nucleus_from_click(Image.fromarray(image), 80, 80, patch_radius=48)

        self.assertIsNone(preview)
        self.assertIsNone(diameter)
        self.assertIn("Please click", error)

    def test_cytoplasm_shell_around_dark_core_fails_closed(self):
        preview, diameter, error = extract_nucleus_from_click(
            make_synthetic_cytoplasm_shell_leak(), 84, 84, patch_radius=48
        )

        self.assertIsNone(preview)
        self.assertIsNone(diameter)
        self.assertTrue(error)
        self.assertIn("Please click", error)

    def test_clear_nucleus_survives_photometric_variation(self):
        image = make_synthetic_jitter_smear()
        variants = [
            image,
            Image.fromarray(np.clip(np.asarray(image).astype(np.float32) * 0.85, 0, 255).astype(np.uint8)),
            Image.fromarray(np.clip(np.asarray(image).astype(np.float32) * 1.15, 0, 255).astype(np.uint8)),
            ImageEnhance.Contrast(image).enhance(0.85),
            ImageEnhance.Contrast(image).enhance(1.15),
            ImageEnhance.Color(image).enhance(0.8),
            ImageEnhance.Color(image).enhance(1.2),
        ]

        diameters = []
        for variant in variants:
            _, diameter, _ = extract_nucleus_from_click(variant, 80, 90, patch_radius=56)
            if diameter is not None:
                diameters.append(diameter)

        self.assertGreaterEqual(len(diameters), 5)
        self.assertLess(max(diameters) - min(diameters), 0.2 * np.median(diameters))

    def test_clear_nucleus_is_stable_under_internal_click_jitter(self):
        image = make_synthetic_jitter_smear()
        offsets = [(-4, 0), (-3, -2), (-2, 3), (0, -4), (0, 0), (2, 3), (4, 0)]

        diameters = []
        for dx, dy in offsets:
            _, diameter, _ = extract_nucleus_from_click(image, 80 + dx, 90 + dy, patch_radius=56)
            if diameter is not None:
                diameters.append(diameter)

        self.assertGreaterEqual(len(diameters), 6)
        self.assertLess(max(diameters) - min(diameters), 0.2 * np.median(diameters))

    def test_clear_nucleus_size_sweep_has_no_small_hard_cutoff(self):
        requested_diameters = [9, 13, 20, 28, 35, 40, 44]
        measured_diameters = []

        for requested in requested_diameters:
            _, diameter, error = extract_nucleus_from_click(
                make_synthetic_size_sweep_smear(requested), 110, 110, patch_radius=96
            )
            self.assertIsNotNone(diameter, f"{requested}px nucleus rejected: {error}")
            self.assertGreater(diameter, requested * 0.7)
            self.assertLess(diameter, requested * 1.4)
            measured_diameters.append(diameter)

        self.assertGreater(measured_diameters[-1], measured_diameters[0] * 3.0)
        self.assertTrue(
            all(next_diameter > diameter for diameter, next_diameter in zip(measured_diameters, measured_diameters[1:]))
        )

    def test_large_clear_nucleus_is_not_confused_with_pale_shell(self):
        _, diameter, error = extract_nucleus_from_click(
            make_synthetic_large_nucleus_shell(), 120, 120, patch_radius=96
        )

        if diameter is not None:
            self.assertLess(diameter, 20.0, error)
        else:
            self.assertTrue(error)


class ScaleCheckerRegressionTests(unittest.TestCase):
    def test_overlay_scale_factor_contract_is_unchanged(self):
        reference = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), "white")
        input_image = Image.new("RGB", (1200, 1000), "black")

        comparison, info = overlay_and_calculate(reference, {"composite": input_image}, 0.75)

        self.assertEqual(comparison[0].size, (TARGET_SIZE, TARGET_SIZE))
        self.assertEqual(comparison[1].size, (TARGET_SIZE, TARGET_SIZE))
        self.assertIn("Scale Factor: 0.75", info)
        self.assertIn("Cropped size: 768×768px", info)
        self.assertIn("Recommended original image size: 1365×1365px", info)

    def test_estimate_scale_still_clamps_and_uses_existing_overlay(self):
        reference = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), "white")
        input_image = {"composite": Image.new("RGB", (3000, 3000), "black")}

        scale, _, info, status = estimate_scale_from_nuclei(10.0, 30.0, reference, input_image)

        self.assertEqual(scale, MAX_SCALE)
        self.assertIn("Scale Factor: 2.00", info)
        self.assertIn("clamped", status)
        self.assertGreaterEqual(scale, MIN_SCALE)

    def test_apply_writes_the_same_webcam_setting(self):
        config = ConfigParser()
        config["SETTINGS"] = {"WEBCAM_IMAGE_SIZE": "1024"}

        with patch("CYTOLONE.scale_check.scale_checker.read_config", return_value=config) as read_config:
            with patch("CYTOLONE.scale_check.scale_checker.write_config") as write_config:
                message, status = apply_scale_to_config(0.8)

        read_config.assert_called_once_with()
        write_config.assert_called_once_with(config)
        self.assertEqual(config["SETTINGS"]["WEBCAM_IMAGE_SIZE"], "1280")
        self.assertIn("WEBCAM_IMAGE_SIZE = 1280", message)
        self.assertIn("WEBCAM_IMAGE_SIZE=1280", status)


class ScaleCheckerLoupeTests(unittest.TestCase):
    def test_loupe_contract_targets_both_images_without_intercepting_clicks(self):
        self.assertIn("#scale-check-reference-image", SCALE_CHECKER_LOUPE_JS)
        self.assertIn("#scale-check-input-image", SCALE_CHECKER_LOUPE_JS)
        self.assertIn("pointermove", SCALE_CHECKER_LOUPE_JS)
        self.assertIn("pointerleave", SCALE_CHECKER_LOUPE_JS)
        self.assertIn("pointer-events: none", SCALE_CHECKER_LOUPE_CSS)
        self.assertIn("backgroundPosition", SCALE_CHECKER_LOUPE_JS)
        self.assertNotIn("preventDefault", SCALE_CHECKER_LOUPE_JS)
        self.assertNotIn('addEventListener("click"', SCALE_CHECKER_LOUPE_JS)

    def test_page_exposes_loupe_ids_and_source_images(self):
        with gr.Blocks() as app:
            build_scale_checker_page()

        components = app.get_config_file()["components"]
        by_elem_id = {
            component.get("props", {}).get("elem_id"): component for component in components
        }

        for elem_id in ("scale-check-reference-image", "scale-check-input-image"):
            self.assertIn(elem_id, by_elem_id)
            self.assertIn("scale-check-click-image", by_elem_id[elem_id]["props"]["elem_classes"])

        html_components = [
            component for component in components if component.get("props", {}).get("js_on_load")
        ]
        self.assertEqual(len(html_components), 1)
        self.assertIn("pointermove", html_components[0]["props"]["js_on_load"])


if __name__ == "__main__":
    unittest.main()
