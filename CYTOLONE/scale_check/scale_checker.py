import math
from pathlib import Path

import cv2
import gradio as gr
import numpy as np
from PIL import Image, ImageDraw

from CYTOLONE.default_config.config_manager import read_config, write_config
from CYTOLONE.util import load_config

IMAGE_DIR = Path("CYTOLONE/scale_check/default_images")
REFERENCE_IMAGE_FILES = {
    "Image 1": IMAGE_DIR / "image1.jpg",
    "Image 2": IMAGE_DIR / "image2.jpg",
}

TARGET_SIZE = 1024
MIN_SCALE = 0.5
MAX_SCALE = 2.0


def load_image(name):
    return Image.open(REFERENCE_IMAGE_FILES[name]).convert("RGB")


def normalize_image(image):
    if image is None:
        return None

    if isinstance(image, Image.Image):
        return image.convert("RGB")

    if isinstance(image, np.ndarray):
        if image.ndim == 2:
            image = np.stack([image, image, image], axis=-1)
        if image.shape[-1] == 4:
            image = image[:, :, :3]
        return Image.fromarray(image.astype(np.uint8)).convert("RGB")

    return None


def get_editor_composite(editor_value):
    if editor_value is None:
        return None

    if isinstance(editor_value, dict):
        return normalize_image(editor_value.get("composite"))

    return normalize_image(editor_value)


def normalize_reference(reference_img):
    reference_img = normalize_image(reference_img)

    if reference_img is None:
        return Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), "black")

    if reference_img.size != (TARGET_SIZE, TARGET_SIZE):
        reference_img = reference_img.resize((TARGET_SIZE, TARGET_SIZE))

    return reference_img


def format_scale_info(scale, crop_size, required_input_size, warning=""):
    info = (
        f"🔍 Scale Factor: {scale:.2f}\n"
        f"📐 Cropped size: {crop_size}×{crop_size}px\n"
        f"📷 Recommended original image size: {required_input_size}×{required_input_size}px"
    )
    if warning:
        info += f"\n⚠️ {warning}"

    return info


def overlay_and_calculate(reference_img, input_img, scale=1.0):
    scale = float(np.clip(scale, MIN_SCALE, MAX_SCALE))
    crop_size = int(TARGET_SIZE * scale)
    required_input_size = int(round(TARGET_SIZE / scale))
    warning = ""

    reference_img = normalize_reference(reference_img)
    input_composite = get_editor_composite(input_img)

    if input_composite is None:
        blank = Image.new("RGB", (TARGET_SIZE, TARGET_SIZE), "black")
        info_text = "Please capture/upload an input image first."
        return (reference_img, blank), info_text

    w, h = input_composite.size
    available_size = min(w, h)

    if crop_size > available_size:
        crop_size = available_size
        scale = crop_size / TARGET_SIZE
        required_input_size = int(round(TARGET_SIZE / scale))
        warning = "Crop exceeded input size. Effective scale was adjusted to the maximum available range."

    left = max((w - crop_size) // 2, 0)
    top = max((h - crop_size) // 2, 0)
    cropped_input = input_composite.crop((left, top, left + crop_size, top + crop_size))
    resized_input = cropped_input.resize((TARGET_SIZE, TARGET_SIZE))

    info_text = format_scale_info(scale, crop_size, required_input_size, warning)

    return (reference_img, resized_input), info_text


def parse_click_index(evt):
    if evt is None or evt.index is None:
        return None

    if isinstance(evt.index, (list, tuple)) and len(evt.index) >= 2:
        return int(round(evt.index[0])), int(round(evt.index[1]))

    return None


def draw_click_marker(image, x, y):
    marked = image.copy()
    draw = ImageDraw.Draw(marked)
    radius = max(6, min(image.size) // 80)
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=(255, 0, 0), width=3)
    draw.line((x - radius * 2, y, x + radius * 2, y), fill=(255, 0, 0), width=2)
    draw.line((x, y - radius * 2, x, y + radius * 2), fill=(255, 0, 0), width=2)

    return marked


def extract_nucleus_from_click(image, x, y, patch_radius=96):
    image = normalize_image(image)
    if image is None:
        return None, None, "Image not found."

    np_img = np.array(image)
    h, w = np_img.shape[:2]
    x = int(np.clip(x, 0, w - 1))
    y = int(np.clip(y, 0, h - 1))

    x1 = max(x - patch_radius, 0)
    y1 = max(y - patch_radius, 0)
    x2 = min(x + patch_radius + 1, w)
    y2 = min(y + patch_radius + 1, h)

    patch = np_img[y1:y2, x1:x2]
    if patch.size == 0:
        return None, None, "No patch available around the selected point."

    gray = cv2.cvtColor(patch, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (5, 5), 0)
    _, binary_inv = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    cleaned = cv2.morphologyEx(binary_inv, cv2.MORPH_OPEN, kernel, iterations=1)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel, iterations=1)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned, connectivity=8)
    px = x - x1
    py = y - y1

    candidates = []
    min_area = 40
    max_area = 3500

    for label_id in range(1, num_labels):
        area = int(stats[label_id, cv2.CC_STAT_AREA])
        if area < min_area or area > max_area:
            continue

        mask = (labels == label_id).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        circularity = (4.0 * math.pi * area / (perimeter * perimeter)) if perimeter > 0 else 0.0
        if circularity < 0.2:
            continue

        centroid = centroids[label_id]
        candidates.append(
            {
                "label": label_id,
                "area": area,
                "mask": mask.astype(bool),
                "contour": contour,
                "centroid": (float(centroid[0]), float(centroid[1])),
            }
        )

    if not candidates:
        return None, None, "No valid nucleus candidate found. Please click another squamous epithelial nucleus."

    selected_label = int(labels[py, px]) if 0 <= py < labels.shape[0] and 0 <= px < labels.shape[1] else 0
    selected = next((c for c in candidates if c["label"] == selected_label), None)

    if selected is None:
        selected = min(
            candidates,
            key=lambda c: (c["centroid"][0] - px) ** 2 + (c["centroid"][1] - py) ** 2,
        )

    diameter = math.sqrt(4.0 * selected["area"] / math.pi)
    preview = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    preview[~selected["mask"]] = (preview[~selected["mask"]] * 0.35).astype(np.uint8)
    cv2.drawContours(preview, [selected["contour"]], -1, (0, 255, 0), 2)
    cv2.circle(preview, (px, py), 3, (255, 0, 0), -1)

    return Image.fromarray(preview), diameter, ""


def update_reference_for_semi_auto(name):
    reference = load_image(name)
    return reference, reference, None, None, None, "", f"Reference image changed to {name}. Click a squamous epithelial nucleus."


def update_input_for_semi_auto(input_image):
    input_image = normalize_image(input_image)
    if input_image is None:
        return None, None, None, None, "", "Input image not found. Capture/upload an image first."

    return input_image, None, None, None, "", "Input image updated. Click a squamous epithelial nucleus."


def on_reference_select(reference_image, evt: gr.SelectData):
    reference_image = normalize_image(reference_image)
    if reference_image is None:
        return None, None, None, None, "", "Reference image is not available."

    point = parse_click_index(evt)
    if point is None:
        return reference_image, None, None, None, "", "Click point could not be detected."

    x = int(np.clip(point[0], 0, reference_image.size[0] - 1))
    y = int(np.clip(point[1], 0, reference_image.size[1] - 1))

    preview, diameter, error = extract_nucleus_from_click(reference_image, x, y)
    marked = draw_click_marker(reference_image, x, y)

    if error:
        return marked, (x, y), None, None, "", f"Reference selection failed: {error}"

    diameter_text = f"{diameter:.1f} px"
    status = f"Reference nucleus detected: {diameter_text}"

    return marked, (x, y), preview, diameter, diameter_text, status


def on_input_select(input_image, evt: gr.SelectData):
    input_image = normalize_image(input_image)
    if input_image is None:
        return None, None, None, None, "", "Input image is not available."

    point = parse_click_index(evt)
    if point is None:
        return input_image, None, None, None, "", "Click point could not be detected."

    x = int(np.clip(point[0], 0, input_image.size[0] - 1))
    y = int(np.clip(point[1], 0, input_image.size[1] - 1))

    preview, diameter, error = extract_nucleus_from_click(input_image, x, y)
    marked = draw_click_marker(input_image, x, y)

    if error:
        return marked, (x, y), None, None, "", f"Input selection failed: {error}"

    diameter_text = f"{diameter:.1f} px"
    status = f"Input nucleus detected: {diameter_text}"

    return marked, (x, y), preview, diameter, diameter_text, status


def estimate_scale_from_nuclei(reference_diameter, input_diameter, reference_image, input_image):
    if reference_diameter is None or input_diameter is None:
        return gr.update(), gr.update(), "Select one nucleus on both images before estimation.", (
            "Missing selection. Click one squamous epithelial nucleus in reference and input images."
        )

    raw_scale = float(input_diameter) / float(reference_diameter)
    clamped_scale = float(np.clip(raw_scale, MIN_SCALE, MAX_SCALE))
    warning = ""
    if not math.isclose(raw_scale, clamped_scale):
        warning = f"Estimated scale {raw_scale:.2f} was clamped to {clamped_scale:.2f}."

    comparison, info = overlay_and_calculate(reference_image, input_image, clamped_scale)
    status = f"Estimated scale: {clamped_scale:.2f} (reference={reference_diameter:.1f}px, input={input_diameter:.1f}px)"
    if warning:
        status += f" {warning}"

    return clamped_scale, comparison, info, status


def apply_scale_to_config(scale):
    scale = float(np.clip(scale, MIN_SCALE, MAX_SCALE))
    recommended_input_size = int(round(TARGET_SIZE / scale))
    command = f"cytolone-config --WEBCAM_IMAGE_SIZE {recommended_input_size}"

    try:
        config = read_config()
        if "SETTINGS" not in config:
            return (
                f"❌ Could not update config.ini\nSuggested command:\n{command}",
                "config.ini update failed: [SETTINGS] section not found.",
            )

        config["SETTINGS"]["WEBCAM_IMAGE_SIZE"] = str(recommended_input_size)
        write_config(config)
    except Exception as exc:  # noqa: BLE001
        return (
            f"❌ Could not update config.ini\nSuggested command:\n{command}",
            f"config.ini update failed: {exc}",
        )

    message = (
        "✅ Updated CYTOLONE/config.ini\n"
        f"WEBCAM_IMAGE_SIZE = {recommended_input_size}\n\n"
        f"Equivalent command:\n{command}"
    )
    status = f"Applied WEBCAM_IMAGE_SIZE={recommended_input_size} to config.ini"

    return message, status


def run():
    config = load_config()

    with gr.Blocks() as app:
        gr.Markdown("# Image Scale Checker")

        with gr.Tabs(selected="semi_auto"):
            with gr.Tab("Semi-Auto", id="semi_auto"):
                semi_reference_state = gr.State(load_image("Image 1"))
                semi_input_state = gr.State(None)
                semi_reference_click_state = gr.State(None)
                semi_input_click_state = gr.State(None)
                semi_reference_diameter_state = gr.State(None)
                semi_input_diameter_state = gr.State(None)

                semi_radio = gr.Radio(
                    choices=list(REFERENCE_IMAGE_FILES.keys()),
                    value="Image 1",
                    label="Select Reference Image",
                )

                with gr.Row():
                    semi_reference_image = gr.Image(
                        width=360,
                        height=360,
                        type="pil",
                        label="Reference (Click Squamous Nucleus Center)",
                        value=load_image("Image 1"),
                        interactive=True,
                    )

                    semi_input_image = gr.Image(
                        width=360,
                        height=360,
                        type="pil",
                        image_mode="RGB",
                        sources=["webcam", "upload"],
                        webcam_options=gr.WebcamOptions(
                            constraints={
                                "video": {
                                    "width": config["WEBCAM_IMAGE_SIZE"],
                                    "height": config["WEBCAM_IMAGE_SIZE"],
                                }
                            },
                            mirror=False,
                        ),
                        label="Input (Capture/Upload then Click Squamous Nucleus Center)",
                        interactive=True,
                    )

                with gr.Row():
                    semi_reference_nucleus_preview = gr.Image(
                        width=260,
                        height=260,
                        type="pil",
                        label="Reference Nucleus Preview",
                    )
                    semi_input_nucleus_preview = gr.Image(
                        width=260,
                        height=260,
                        type="pil",
                        label="Input Nucleus Preview",
                    )

                with gr.Row():
                    semi_reference_diameter_text = gr.Textbox(
                        label="Reference Nucleus Diameter",
                        value="",
                        interactive=False,
                    )
                    semi_input_diameter_text = gr.Textbox(
                        label="Input Nucleus Diameter",
                        value="",
                        interactive=False,
                    )

                with gr.Row():
                    semi_estimate_btn = gr.Button("Estimate")
                    semi_scale_slider = gr.Slider(
                        MIN_SCALE,
                        MAX_SCALE,
                        step=0.01,
                        value=1.0,
                        label="Scale Factor (Auto + Fine Tuning)",
                    )
                    semi_apply_btn = gr.Button("Apply", variant="primary")

                semi_result_slider = gr.ImageSlider(label="Compare Reference vs Adjusted")
                semi_result_text = gr.Textbox(label="Scale Info", lines=4)
                semi_status_text = gr.Textbox(label="Status", lines=2, interactive=False)
                semi_apply_text = gr.Textbox(label="Apply Result", lines=5, interactive=False)

                semi_radio.change(
                    fn=update_reference_for_semi_auto,
                    inputs=semi_radio,
                    outputs=[
                        semi_reference_state,
                        semi_reference_image,
                        semi_reference_click_state,
                        semi_reference_nucleus_preview,
                        semi_reference_diameter_state,
                        semi_reference_diameter_text,
                        semi_status_text,
                    ],
                )

                semi_input_image.input(
                    fn=update_input_for_semi_auto,
                    inputs=semi_input_image,
                    outputs=[
                        semi_input_state,
                        semi_input_click_state,
                        semi_input_nucleus_preview,
                        semi_input_diameter_state,
                        semi_input_diameter_text,
                        semi_status_text,
                    ],
                )

                semi_reference_image.select(
                    fn=on_reference_select,
                    inputs=[semi_reference_state],
                    outputs=[
                        semi_reference_image,
                        semi_reference_click_state,
                        semi_reference_nucleus_preview,
                        semi_reference_diameter_state,
                        semi_reference_diameter_text,
                        semi_status_text,
                    ],
                )

                semi_input_image.select(
                    fn=on_input_select,
                    inputs=[semi_input_state],
                    outputs=[
                        semi_input_image,
                        semi_input_click_state,
                        semi_input_nucleus_preview,
                        semi_input_diameter_state,
                        semi_input_diameter_text,
                        semi_status_text,
                    ],
                )

                semi_estimate_btn.click(
                    fn=estimate_scale_from_nuclei,
                    inputs=[
                        semi_reference_diameter_state,
                        semi_input_diameter_state,
                        semi_reference_state,
                        semi_input_state,
                    ],
                    outputs=[
                        semi_scale_slider,
                        semi_result_slider,
                        semi_result_text,
                        semi_status_text,
                    ],
                )

                semi_scale_slider.change(
                    fn=overlay_and_calculate,
                    inputs=[semi_reference_state, semi_input_state, semi_scale_slider],
                    outputs=[semi_result_slider, semi_result_text],
                )

                semi_apply_btn.click(
                    fn=apply_scale_to_config,
                    inputs=[semi_scale_slider],
                    outputs=[semi_apply_text, semi_status_text],
                )

            with gr.Tab("Manual", id="manual"):
                manual_radio = gr.Radio(
                    choices=list(REFERENCE_IMAGE_FILES.keys()),
                    value="Image 1",
                    label="Select Reference Image",
                )

                with gr.Row():
                    manual_reference_image = gr.Image(
                        width=300,
                        height=300,
                        type="pil",
                        label="Reference Image Preview",
                        value=load_image("Image 1"),
                    )

                    manual_adjust_input = gr.ImageEditor(
                        width=300,
                        height=300,
                        type="pil",
                        canvas_size=(
                            config["WEBCAM_IMAGE_SIZE"],
                            config["WEBCAM_IMAGE_SIZE"],
                        ),
                        fixed_canvas=True,
                        webcam_options=gr.WebcamOptions(
                            constraints={
                                "video": {
                                    "width": config["WEBCAM_IMAGE_SIZE"],
                                    "height": config["WEBCAM_IMAGE_SIZE"],
                                }
                            },
                            mirror=False,
                        ),
                        sources=["webcam", "upload"],
                        eraser=False,
                        brush=False,
                        layers=False,
                        label="Adjust Image Preview",
                    )

                with gr.Row():
                    manual_scale_slider = gr.Slider(
                        MIN_SCALE,
                        MAX_SCALE,
                        step=0.01,
                        value=1.0,
                        label="Scale Factor",
                    )
                    manual_compare_btn = gr.Button("Compare")

                manual_result_slider = gr.ImageSlider(label="Compare Reference vs Adjusted")
                manual_result_text = gr.Textbox(label="Scale Info", lines=4)

                manual_radio.change(
                    fn=load_image,
                    inputs=manual_radio,
                    outputs=manual_reference_image,
                )

                manual_compare_btn.click(
                    fn=overlay_and_calculate,
                    inputs=[manual_reference_image, manual_adjust_input, manual_scale_slider],
                    outputs=[manual_result_slider, manual_result_text],
                )

    app.launch()


if __name__ == "__main__":
    run()
