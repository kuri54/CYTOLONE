import math
from pathlib import Path

import cv2
import gradio as gr
import numpy as np
from PIL import Image, ImageDraw

from CYTOLONE.app_paths import config_path
from CYTOLONE.default_config.config_manager import read_config, write_config
from CYTOLONE.util import load_config

IMAGE_DIR = Path(__file__).resolve().parent / "default_images"
REFERENCE_IMAGE_FILES = {
    "Image 1": IMAGE_DIR / "image1.jpg",
    "Image 2": IMAGE_DIR / "image2.jpg",
}

TARGET_SIZE = 1024
MIN_SCALE = 0.5
MAX_SCALE = 2.0

LOUPE_ZOOM = 5
LOUPE_SIZE = 180
SEED_RADIUS = 6
MIN_NUCLEUS_AREA = 12
MAX_NUCLEUS_AREA = 3500
LOCAL_BACKGROUND_SIGMA = 7
LARGE_NUCLEUS_BACKGROUND_SIGMA = 14
MIN_BROAD_MARKER_CONTRAST_RATIO = 1.8
MIN_MARKER_OVERLAP = 2
SOFT_DARKNESS_RATIO = 0.45
MAX_SOFT_EXPANSION = 3.0
EXPANSION_CIRCULARITY_FLOOR = 0.35
EXPANSION_ASPECT_LIMIT = 2.4

SCALE_CHECKER_LOUPE_CSS = f"""
.scale-checker-loupe {{
    position: fixed;
    z-index: 10000;
    width: {LOUPE_SIZE}px;
    height: {LOUPE_SIZE}px;
    display: none;
    pointer-events: none;
    border: 3px solid #ff4b4b;
    border-radius: 50%;
    box-sizing: border-box;
    background-color: #222;
    background-repeat: no-repeat;
    box-shadow: 0 2px 14px rgba(0, 0, 0, 0.45);
    overflow: hidden;
}}

.scale-checker-loupe.is-visible {{
    display: block;
}}

.scale-checker-loupe::before,
.scale-checker-loupe::after {{
    position: absolute;
    z-index: 1;
    background: rgba(255, 75, 75, 0.9);
    content: "";
    pointer-events: none;
}}

.scale-checker-loupe::before {{
    top: 50%;
    left: 0;
    width: 100%;
    height: 1px;
    transform: translateY(-50%);
}}

.scale-checker-loupe::after {{
    top: 0;
    left: 50%;
    width: 1px;
    height: 100%;
    transform: translateX(-50%);
}}
"""

SCALE_CHECKER_LOUPE_JS = f"""
(() => {{
    const targetSelectors = [
        "#scale-check-reference-image",
        "#scale-check-input-image",
    ];
    const loupeSize = {LOUPE_SIZE};
    const zoom = {LOUPE_ZOOM};

    const hideLoupe = (loupe) => loupe.classList.remove("is-visible");

    const getImageContentPoint = (image, event) => {{
        if (!image.complete || !image.naturalWidth || !image.naturalHeight) {{
            return null;
        }}

        const rect = image.getBoundingClientRect();
        if (!rect.width || !rect.height) {{
            return null;
        }}

        const imageRatio = image.naturalWidth / image.naturalHeight;
        const boxRatio = rect.width / rect.height;
        let contentWidth = rect.width;
        let contentHeight = rect.height;
        let offsetX = 0;
        let offsetY = 0;

        if (boxRatio > imageRatio) {{
            contentHeight = rect.height;
            contentWidth = contentHeight * imageRatio;
            offsetX = (rect.width - contentWidth) / 2;
        }} else if (boxRatio < imageRatio) {{
            contentWidth = rect.width;
            contentHeight = contentWidth / imageRatio;
            offsetY = (rect.height - contentHeight) / 2;
        }}

        const displayX = event.clientX - rect.left - offsetX;
        const displayY = event.clientY - rect.top - offsetY;
        if (
            displayX < 0 ||
            displayY < 0 ||
            displayX > contentWidth ||
            displayY > contentHeight
        ) {{
            return null;
        }}

        return {{
            displayX,
            displayY,
            contentWidth,
            contentHeight,
        }};
    }};

    const attachLoupe = (root) => {{
        const image = root.querySelector("img");
        if (!image) {{
            return;
        }}
        if (root.__scaleCheckerLoupe?.image === image) {{
            return;
        }}
        root.__scaleCheckerLoupe?.destroy();

        const loupe = document.createElement("div");
        loupe.className = "scale-checker-loupe";
        loupe.setAttribute("aria-hidden", "true");
        document.body.appendChild(loupe);

        let source = null;
        const hide = () => hideLoupe(loupe);
        const move = (event) => {{
            const point = getImageContentPoint(image, event);
            if (!point) {{
                hide();
                return;
            }}

            const imageSource = image.currentSrc || image.src;
            if (!imageSource) {{
                hide();
                return;
            }}
            if (source !== imageSource) {{
                source = imageSource;
                loupe.style.backgroundImage = `url("${{imageSource.replace(/"/g, '\\\\"')}}")`;
            }}

            loupe.style.left = `${{event.clientX - loupeSize / 2}}px`;
            loupe.style.top = `${{event.clientY - loupeSize / 2}}px`;
            loupe.style.backgroundSize = `${{point.contentWidth * zoom}}px ${{point.contentHeight * zoom}}px`;
            loupe.style.backgroundPosition = `${{loupeSize / 2 - point.displayX * zoom}}px ${{loupeSize / 2 - point.displayY * zoom}}px`;
            loupe.classList.add("is-visible");
        }};

        image.addEventListener("pointermove", move, {{ passive: true }});
        image.addEventListener("pointerleave", hide, {{ passive: true }});
        image.addEventListener("pointercancel", hide, {{ passive: true }});
        root.__scaleCheckerLoupe = {{
            image,
            destroy: () => {{
                image.removeEventListener("pointermove", move);
                image.removeEventListener("pointerleave", hide);
                image.removeEventListener("pointercancel", hide);
                loupe.remove();
            }},
        }};
    }};

    const attachAll = () => targetSelectors.forEach((selector) => {{
        const root = document.querySelector(selector);
        if (root) {{
            attachLoupe(root);
        }}
    }});

    attachAll();
    const observer = new MutationObserver(attachAll);
    observer.observe(document.body, {{ childList: true, subtree: true }});
    window.setTimeout(attachAll, 100);
    window.setTimeout(attachAll, 500);
}})();
"""


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


def _selection_failure(reason):
    return (
        None,
        None,
        f"No confident nucleus was found at the clicked seed ({reason}). "
        "Please click the center of another squamous epithelial nucleus.",
    )


def _seeded_nucleus_mask(patch, px, py, seed_radius=SEED_RADIUS):
    """Extract a local nucleus component using the click as a marker.

    The dark component is estimated from the local lightness distribution, not
    from the median color of the click seed. A softer mask can then grow that
    marker to the visible boundary. Every accepted component must intersect the
    click marker; no spatially nearest component is eligible.
    """
    lab = cv2.cvtColor(patch, cv2.COLOR_RGB2LAB).astype(np.float32)
    lightness = lab[:, :, 0]
    seed = np.zeros(lightness.shape, dtype=np.uint8)
    cv2.circle(seed, (px, py), seed_radius, 1, -1)
    seed_pixels = seed.astype(bool)
    if not np.any(seed_pixels):
        return None, None, None, "The click marker is outside the image patch."

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    def find_marker_core(darkness):
        darkness_min = float(np.min(darkness))
        darkness_shifted = np.clip(darkness - darkness_min, 0.0, 255.0).astype(np.uint8)
        otsu_value, _ = cv2.threshold(
            darkness_shifted, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        core_threshold = max(
            float(otsu_value) + darkness_min,
            float(np.percentile(darkness, 75)),
        )
        if not np.isfinite(core_threshold) or core_threshold <= darkness_min:
            return None, None, None, "No local nuclear contrast was found around the click."

        core_binary = cv2.morphologyEx(
            (darkness >= core_threshold).astype(np.uint8), cv2.MORPH_OPEN, kernel
        )
        core_count, core_labels, _, _ = cv2.connectedComponentsWithStats(
            core_binary, connectivity=8
        )
        marker_components = []
        for label in range(1, core_count):
            component = core_labels == label
            overlap = int(np.count_nonzero(component & seed_pixels))
            if overlap >= MIN_MARKER_OVERLAP:
                marker_components.append((overlap, int(np.count_nonzero(component)), label))
        if not marker_components:
            return None, None, core_threshold, "No stained foreground component intersects the click marker."

        marker_components.sort(reverse=True)
        _, core_area, selected_label = marker_components[0]
        return core_labels == selected_label, core_area, core_threshold, ""

    core_mask = None
    core_area = None
    core_threshold = None
    darkness = None
    error = "No stained foreground component intersects the click marker."
    for sigma in (LOCAL_BACKGROUND_SIGMA, LARGE_NUCLEUS_BACKGROUND_SIGMA):
        local_background = cv2.GaussianBlur(lightness, (0, 0), sigma)
        darkness = local_background - lightness
        core_mask, core_area, core_threshold, error = find_marker_core(darkness)
        if core_mask is not None and sigma == LARGE_NUCLEUS_BACKGROUND_SIGMA:
            marker_contrast = float(np.median(darkness[seed_pixels]))
            if marker_contrast < core_threshold * MIN_BROAD_MARKER_CONTRAST_RATIO:
                core_mask = None
                error = "The broad foreground candidate has insufficient marker contrast."
        if core_mask is not None:
            break
    if core_mask is None:
        return None, None, darkness, error

    if core_area < MIN_NUCLEUS_AREA or core_area > MAX_NUCLEUS_AREA:
        return None, None, darkness, "The clicked foreground component has no plausible nucleus scale."

    soft_threshold = core_threshold * SOFT_DARKNESS_RATIO
    soft_binary = cv2.morphologyEx(
        (darkness >= soft_threshold).astype(np.uint8), cv2.MORPH_OPEN, kernel
    )
    soft_count, soft_labels, _, _ = cv2.connectedComponentsWithStats(
        soft_binary, connectivity=8
    )
    selected_mask = core_mask
    soft_area = core_area
    if soft_count > 1:
        soft_components = []
        for label in range(1, soft_count):
            component = soft_labels == label
            core_overlap = int(np.count_nonzero(component & core_mask))
            if core_overlap:
                soft_components.append((core_overlap, int(np.count_nonzero(component)), label))
        if soft_components:
            soft_components.sort(reverse=True)
            core_overlap, candidate_area, soft_label = soft_components[0]
            if core_overlap >= max(MIN_MARKER_OVERLAP, int(round(core_area * 0.8))):
                selected_mask = soft_labels == soft_label
                soft_area = candidate_area

    expansion = soft_area / float(core_area)

    def mask_geometry(mask):
        contours, _ = cv2.findContours(
            mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return 0.0, float("inf")
        contour = max(contours, key=cv2.contourArea)
        perimeter = cv2.arcLength(contour, True)
        area = float(np.count_nonzero(mask))
        circularity = 4.0 * math.pi * area / (perimeter * perimeter) if perimeter else 0.0
        _, _, width, height = cv2.boundingRect(contour)
        aspect_ratio = max(width, height) / max(1, min(width, height))
        return circularity, aspect_ratio

    if selected_mask is not core_mask and expansion > MAX_SOFT_EXPANSION:
        circularity, aspect_ratio = mask_geometry(selected_mask)
        if (
            circularity < EXPANSION_CIRCULARITY_FLOOR
            or aspect_ratio > EXPANSION_ASPECT_LIMIT
        ):
            return (
                None,
                None,
                darkness,
                "The click-connected foreground expands into an ambiguous surrounding region.",
            )

    area = int(np.count_nonzero(selected_mask))
    if area < MIN_NUCLEUS_AREA or area > MAX_NUCLEUS_AREA:
        return None, None, darkness, "The clicked foreground component has no plausible nucleus scale."

    component_y, component_x = np.where(selected_mask)
    if (
        component_x.min() <= 0
        or component_y.min() <= 0
        or component_x.max() >= selected_mask.shape[1] - 1
        or component_y.max() >= selected_mask.shape[0] - 1
    ):
        return None, None, darkness, "The selected region is clipped by the local crop."

    return selected_mask, None, darkness, ""


def _render_nucleus_preview(patch, selected_mask, px, py, seed_radius):
    preview = patch.copy()
    dimmed = (preview.astype(np.float32) * 0.35).astype(np.uint8)
    preview[~selected_mask] = dimmed[~selected_mask]

    highlight = np.array([45, 220, 80], dtype=np.uint8)
    preview[selected_mask] = (
        preview[selected_mask].astype(np.float32) * 0.45 + highlight.astype(np.float32) * 0.55
    ).astype(np.uint8)

    contours, _ = cv2.findContours(selected_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(preview, contours, -1, (0, 255, 0), 2)
    cv2.circle(preview, (px, py), seed_radius, (255, 190, 0), 1)
    cv2.circle(preview, (px, py), 3, (255, 0, 0), -1)
    cv2.line(preview, (px - 8, py), (px + 8, py), (255, 0, 0), 1)
    cv2.line(preview, (px, py - 8), (px, py + 8), (255, 0, 0), 1)
    return Image.fromarray(preview)


def extract_nucleus_from_click(image, x, y, patch_radius=96):
    image = normalize_image(image)
    if image is None:
        return None, None, "Image not found."

    np_img = np.array(image)
    h, w = np_img.shape[:2]
    if w == 0 or h == 0:
        return None, None, "Image is empty."

    x = int(np.clip(x, 0, w - 1))
    y = int(np.clip(y, 0, h - 1))

    x1 = max(x - patch_radius, 0)
    y1 = max(y - patch_radius, 0)
    x2 = min(x + patch_radius + 1, w)
    y2 = min(y + patch_radius + 1, h)
    patch = np_img[y1:y2, x1:x2]
    px = x - x1
    py = y - y1
    if patch.size == 0 or not (0 <= px < patch.shape[1] and 0 <= py < patch.shape[0]):
        return _selection_failure("no local image patch is available")

    selected_mask, _, _, error = _seeded_nucleus_mask(patch, px, py)
    if error:
        return _selection_failure(error)

    area = int(np.count_nonzero(selected_mask))
    diameter = math.sqrt(4.0 * area / math.pi)
    preview = _render_nucleus_preview(patch, selected_mask, px, py, SEED_RADIUS)
    return preview, diameter, ""


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
        f"✅ Updated {config_path()}\n"
        f"WEBCAM_IMAGE_SIZE = {recommended_input_size}\n\n"
        f"Equivalent command:\n{command}"
    )
    status = f"Applied WEBCAM_IMAGE_SIZE={recommended_input_size} to config.ini"

    return message, status


def build_scale_checker_page():
    config = load_config()

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

            gr.HTML(
                value=f"<style>{SCALE_CHECKER_LOUPE_CSS}</style>",
                js_on_load=SCALE_CHECKER_LOUPE_JS,
                visible="hidden",
                show_label=False,
                container=False,
                min_height=0,
            )

            with gr.Row():
                semi_reference_image = gr.Image(
                    width=360,
                    height=360,
                    type="pil",
                    label="Reference (Click Squamous Nucleus Center)",
                    value=load_image("Image 1"),
                    interactive=True,
                    elem_id="scale-check-reference-image",
                    elem_classes=["scale-check-click-image"],
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
                    elem_id="scale-check-input-image",
                    elem_classes=["scale-check-click-image"],
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


def run():
    with gr.Blocks() as app:
        build_scale_checker_page()

    app.launch()


if __name__ == "__main__":
    run()
