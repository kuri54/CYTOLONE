import os
import re
import base64
import gc
import numpy as np
import gradio as gr
from io import BytesIO
from functools import partial
from PIL import Image

import torch
from transformers import AutoModel, AutoProcessor

from CYTOLONE.label_caption import (
    get_diagnosis_candidate_labels,
    get_label_caption,
    get_order_type,
    )

from CYTOLONE.model import (
    APP_MODEL_DISPLAY_CHOICES,
    LLM_MODEL_DISPLAY_CHOICES,
    get_model_id,
    get_llm_id,
)
from CYTOLONE.download_models import (
    delete_model_with_status,
    download_model_with_status,
    model_management_summary,
)
from CYTOLONE.llm_prompt import build_prompt_v2
from CYTOLONE.llm_runtime import LLMRuntimeError, LocalLLMRuntime
from CYTOLONE.model_storage import model_directory_is_complete
from CYTOLONE.scale_check.scale_checker import build_scale_checker_page
from CYTOLONE.settings_page import apply_settings, build_settings_page, get_settings_values
from CYTOLONE.theme import CYTOLONE_THEME

from CYTOLONE.app_paths import debug_path, models_path
from CYTOLONE.util import load_config, build_config_df

model_cache = {}
processor_cache = {}
llm_runtime = LocalLLMRuntime()
TARGET_SIZE = 1024

MANUAL_GENERATION_BUTTON_LABELS = {
    "ja": "詳細な鑑別所見を生成",
    "en": "Generate detailed differential findings",
}
MANUAL_GENERATION_GUIDANCE = {
    "ja": "判定が拮抗しています。生成は任意で、時間がかかる場合があります。",
    "en": "The top two diagnoses are close. Generation is optional and may take some time.",
}


def _cytolone_blocks():
    """Create a themed Blocks app across supported Gradio constructor APIs."""

    try:
        app = gr.Blocks(title="CYTOLONE", theme=CYTOLONE_THEME)
    except TypeError as exc:
        if "unexpected keyword argument 'theme'" not in str(exc):
            raise
        app = gr.Blocks(title="CYTOLONE")
    app.theme = CYTOLONE_THEME
    return app

PAGE_TABS_CSS = """
#page-tabs > .tab-wrapper > .tab-container[role="tablist"] > button:not([data-tab-id="launcher"]),
#page-tabs > .tab-wrapper > .tab-container.visually-hidden > button:not(:first-child),
#page-tabs > .tab-wrapper > .overflow-menu {
    display: none !important;
}
"""

CAPTURE_CURRENT_VIEW_JS = """
(choiceCaption, imageValue, capturePayload) => {
    const root = document.querySelector("#cytolone-image-input");
    const video = root?.querySelector("video");

    if (!video || !video.videoWidth || !video.videoHeight) {
        return [choiceCaption, imageValue, null];
    }

    const sourceSize = Math.min(video.videoWidth, video.videoHeight);
    const sourceX = Math.floor((video.videoWidth - sourceSize) / 2);
    const sourceY = Math.floor((video.videoHeight - sourceSize) / 2);
    const canvas = document.createElement("canvas");
    canvas.width = sourceSize;
    canvas.height = sourceSize;
    const context = canvas.getContext("2d");

    context.drawImage(
        video,
        sourceX,
        sourceY,
        sourceSize,
        sourceSize,
        0,
        0,
        sourceSize,
        sourceSize
    );

    return [choiceCaption, imageValue, canvas.toDataURL("image/png")];
}
"""

def build_iphone_camera_preference_js(image_size):
    script = """
(() => {
    const rootSelector = "#cytolone-image-input";
    const storageKey = "cytolone.preferredCamera";
    const iphoneLabelPattern = /iphone|continuity camera/i;
    const imageSize = __IMAGE_SIZE__;
    let applyingPreference = false;
    let lastAppliedDeviceId = null;
    let preferenceApplied = false;
    let preferenceAttempts = 0;
    const retryDelays = [300, 700, 1200, 2000, 3000, 5000];

    const getStoredCamera = () => {
        try {
            return JSON.parse(window.localStorage.getItem(storageKey) || "null");
        } catch {
            return null;
        }
    };

    const storeCamera = (deviceId, label) => {
        if (!deviceId || !label || !iphoneLabelPattern.test(label)) {
            return;
        }
        window.localStorage.setItem(
            storageKey,
            JSON.stringify({ deviceId, label, savedAt: new Date().toISOString() })
        );
    };

    const getVideo = () => document.querySelector(rootSelector)?.querySelector("video");

    const getVideoTrack = (video) => {
        const stream = video?.srcObject;
        return stream?.getVideoTracks?.()[0] || null;
    };

    const rememberCurrentIphoneCamera = () => {
        const track = getVideoTrack(getVideo());
        if (!track) {
            return;
        }
        const settings = track.getSettings?.() || {};
        storeCamera(settings.deviceId, track.label || "");
    };

    const selectStoredDevice = async () => {
        const stored = getStoredCamera();
        if (!stored?.deviceId && !stored?.label) {
            return null;
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        const cameras = devices.filter((device) => device.kind === "videoinput");

        return (
            cameras.find((device) => stored.deviceId && device.deviceId === stored.deviceId) ||
            cameras.find((device) => stored.label && device.label === stored.label) ||
            cameras.find((device) => stored.label && device.label.includes(stored.label)) ||
            null
        );
    };

    const schedulePreferredCameraRetry = () => {
        if (preferenceApplied || preferenceAttempts >= retryDelays.length) {
            return;
        }
        const delay = retryDelays[preferenceAttempts];
        preferenceAttempts += 1;
        window.setTimeout(applyPreferredCamera, delay);
    };

    const applyPreferredCamera = async () => {
        if (preferenceApplied || applyingPreference || !navigator.mediaDevices?.getUserMedia) {
            return;
        }

        const video = getVideo();
        const currentTrack = getVideoTrack(video);
        if (!video || !currentTrack) {
            schedulePreferredCameraRetry();
            return;
        }

        rememberCurrentIphoneCamera();

        const device = await selectStoredDevice();
        if (!device?.deviceId || device.deviceId === lastAppliedDeviceId) {
            schedulePreferredCameraRetry();
            return;
        }

        const currentDeviceId = currentTrack.getSettings?.().deviceId;
        if (currentDeviceId === device.deviceId) {
            lastAppliedDeviceId = device.deviceId;
            preferenceApplied = true;
            storeCamera(device.deviceId, device.label);
            return;
        }

        applyingPreference = true;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    deviceId: { exact: device.deviceId },
                    width: imageSize,
                    height: imageSize
                }
            });
            video.srcObject = stream;
            await video.play();
            lastAppliedDeviceId = device.deviceId;
            preferenceApplied = true;
            storeCamera(device.deviceId, device.label);
        } catch (error) {
            console.warn("CYTOLONE could not reconnect the saved iPhone camera.", error);
            schedulePreferredCameraRetry();
        } finally {
            applyingPreference = false;
        }
    };

    const watchCamera = () => {
        const video = getVideo();
        if (!video) {
            return;
        }
        if (video.dataset.cytoloneCameraPreferenceWatched === "true") {
            return;
        }
        video.dataset.cytoloneCameraPreferenceWatched = "true";

        video.addEventListener("loadedmetadata", () => {
            rememberCurrentIphoneCamera();
        });
        video.addEventListener("play", () => {
            rememberCurrentIphoneCamera();
        });
        schedulePreferredCameraRetry();
    };

    const observer = new MutationObserver(watchCamera);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            schedulePreferredCameraRetry();
        }
    });
    watchCamera();
})();
"""
    return script.replace("__IMAGE_SIZE__", str(image_size))

def get_partial_labels(classification_label, order, order_type):
    if order_type == "Full":
        return classification_label

    else:
        target_index = order.index(order_type)
        partial_labels = set()

        for label in classification_label:
            parts = label.split(" ", 3)
            partial_label = " ".join(parts[:target_index])
            partial_labels.add(partial_label)

        return list(partial_labels)


def get_labels_for_order(specimen, classification_label, order, order_type):
    if order_type == "Diagnosis":
        # Diagnosis candidates are already full hierarchy strings. Keep the
        # registry order while excluding only the Full-only Negative leaf.
        return get_diagnosis_candidate_labels(specimen, classification_label)
    labels = get_partial_labels(classification_label, order, order_type)
    return labels

def split_by_three_spaces(predict_label, order_type, order):
    if order_type == "Full":
        return predict_label

    target_index = order.index(order_type) - 1

    parts = predict_label.split(" ", 3)

    if len(parts) < 4:
        parts += [""] * (4 - len(parts))

    return parts[target_index]

def clean_llm_output(text):
    text = text.replace("\r\n", "\n")

    # 1) 「<|channel|>final<|message|>」以降だけを残す
    if "<|channel|>final<|message|>" in text:
        text = text.split("<|channel|>final<|message|>", 1)[1]

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"<\|channel\|>[^<]*<\|message\|>", "", text)
    text = re.sub(r"<\|[^|]+\|>", "", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    return text.strip()

def data_url_to_pil_image(data_url):
    header, encoded = data_url.split(",", 1)
    if not header.startswith("data:image/"):
        raise gr.Error("Unsupported captured image format. Please try again.")

    return Image.open(BytesIO(base64.b64decode(encoded)))

def as_pil_image(image):
    if image is None:
        raise gr.Error("Please select a webcam or upload an image before analyzing.")

    if isinstance(image, dict):
        background = image.get("background")
        image = background if background is not None else image.get("composite")

    if isinstance(image, np.ndarray):
        image = Image.fromarray(image)
    elif isinstance(image, str):
        if image.startswith("data:image/"):
            image = data_url_to_pil_image(image)
        else:
            image = Image.open(image)

    if not isinstance(image, Image.Image):
        raise gr.Error("Unsupported image input. Please capture or upload an image again.")

    return image.convert("RGB")

def center_crop(image, size):
    image = as_pil_image(image)
    width, height = image.size
    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size
    return image.crop((left, top, right, bottom))

def prepare_inference_image(image, config):
    image = as_pil_image(image)
    input_size = min(image.size)
    configured_size = int(config["WEBCAM_IMAGE_SIZE"])
    scale = TARGET_SIZE / configured_size
    crop_size = int(TARGET_SIZE * scale)
    crop_size = max(1, min(crop_size, input_size))
    cropped_image = center_crop(image, crop_size)

    if cropped_image.size != (TARGET_SIZE, TARGET_SIZE):
        cropped_image = cropped_image.resize((TARGET_SIZE, TARGET_SIZE))

    return cropped_image, {
        "scale": scale,
        "crop_size": crop_size,
        "original_size": image.size,
        "inference_size": cropped_image.size,
    }

def save_debug_preprocess_info(source, preprocess_info, config):
    save_dir = debug_path()
    save_dir.mkdir(parents=True, exist_ok=True)

    with open(save_dir / "preprocess_info.txt", "w", encoding="utf-8") as file:
        file.write(f"source = {source}\n")
        file.write(f"WEBCAM_IMAGE_SIZE = {config['WEBCAM_IMAGE_SIZE']}\n")
        file.write(f"scale = {preprocess_info['scale']:.6f}\n")
        file.write(f"crop_size = {preprocess_info['crop_size']}\n")
        original_size = preprocess_info["original_size"]
        inference_size = preprocess_info["inference_size"]
        file.write(f"original_image_size = {original_size[0]}x{original_size[1]}\n")
        file.write(f"inference_image_size = {inference_size[0]}x{inference_size[1]}\n")

def classify_labels(choice_caption, image, specimen, classification_label, order, config, source="image_input"):
    image = as_pil_image(image)

    if config["DEBUG"]:
        save_dir = debug_path()
        save_dir.mkdir(parents=True, exist_ok=True)

        image.save(save_dir / "original_image.jpg")

    image, preprocess_info = prepare_inference_image(image, config)

    if config["DEBUG"]:
        image.save(save_dir / "cropped_image.jpg")
        save_debug_preprocess_info(source, preprocess_info, config)

    model, processor = load_application_model(config["MODEL"])

    order_type = get_order_type(specimen, config["LANGUAGE"], choice_caption)
    labels = get_labels_for_order(specimen, classification_label, order, order_type)

    inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)

    if next(model.parameters()).device.type == "mps":
        inputs.to("mps")

    with torch.no_grad():
        outputs = model(**inputs)

    logits_per_image = outputs.logits_per_image
    probs = logits_per_image.softmax(dim=1)[0]

    label_probs = {
        split_by_three_spaces(label, order_type, order): round(prob.item(), 4)
        for label, prob in zip(labels, probs)
    }

    return label_probs


def load_application_model(model_key):
    """Load one configured classifier or explain how to restore it."""

    model_id = get_model_id(model_key)
    model_dir = models_path() / model_id
    if not model_directory_is_complete(model_dir):
        raise gr.Error(
            f"The selected application model ({model_key}) is not installed or is "
            "incomplete. Open Model Management and download the selected application "
            "model before analyzing an image."
        )

    if model_id not in model_cache:
        try:
            model_cache[model_id] = AutoModel.from_pretrained(
                model_dir,
                local_files_only=True,
                device_map="auto",
            )
            processor_cache[model_id] = AutoProcessor.from_pretrained(
                model_dir,
                local_files_only=True,
            )
        except Exception as exc:  # noqa: BLE001
            model_cache.pop(model_id, None)
            processor_cache.pop(model_id, None)
            raise gr.Error(
                f"The selected application model ({model_key}) could not be loaded. "
                "Open Model Management and force re-download that model."
            ) from exc

    return model_cache[model_id], processor_cache[model_id]


def release_model_cache(spec):
    """Release the selected application or LLM model before deletion."""

    if spec.role == "application":
        released = model_cache.pop(spec.repo_id, None)
        released_processor = processor_cache.pop(spec.repo_id, None)
        if released is not None or released_processor is not None:
            del released, released_processor
            gc.collect()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
    elif spec.role == "llm":
        llm_runtime.release_model(spec.key)


def _model_management_control_updates(role, key, other_key):
    if role == "application":
        app_key, llm_key = key, other_key
    else:
        app_key, llm_key = other_key, key
    return (
        gr.update(choices=APP_MODEL_DISPLAY_CHOICES, value=app_key),
        gr.update(choices=LLM_MODEL_DISPLAY_CHOICES, value=llm_key),
        gr.update(value=False),
        gr.update(value=False),
    )


def download_model_from_ui(role, key, force, other_key):
    for status, summary in download_model_with_status(role, key, force):
        yield (
            status,
            summary,
            *_model_management_control_updates(role, key, other_key),
        )


def delete_model_from_ui(role, key, confirmation, other_key):
    status, summary = delete_model_with_status(
        role,
        key,
        confirmation,
        release_callback=release_model_cache,
    )
    return (
        status,
        summary,
        *_model_management_control_updates(role, key, other_key),
    )


def reset_delete_confirmation():
    return gr.update(value=False)


def _top_two_label_probs(label_probs):
    if not isinstance(label_probs, dict):
        return []
    return sorted(label_probs.items(), key=lambda item: item[1], reverse=True)[:2]


def _manual_generation_available(choice_caption, label_probs, specimen, config):
    try:
        order_type = get_order_type(specimen, config["LANGUAGE"], choice_caption)
    except (KeyError, TypeError):
        return False

    top_labels = _top_two_label_probs(label_probs)
    threshold = config["LLM_GEN_THRESHOLD"]
    return (
        len(top_labels) > 1
        and top_labels[0][1] < threshold
        and order_type == "Diagnosis"
    )


def _manual_generation_button_update(language, visible=False):
    return gr.update(
        value=MANUAL_GENERATION_BUTTON_LABELS[language],
        visible=visible,
        interactive=True,
    )


def reset_analysis_outputs(language=None):
    if language not in MANUAL_GENERATION_BUTTON_LABELS:
        language = load_config()["LANGUAGE"]

    return (
        gr.update(value=None),
        {},
        gr.update(value="", visible=False),
        _manual_generation_button_update(language),
        gr.update(value=""),
        gr.update(value=""),
    )


def generate_comments(choice_caption, label_probs, specimen, config):
    if not _manual_generation_available(choice_caption, label_probs, specimen, config):
        return ""

    top_labels = _top_two_label_probs(label_probs)

    llm_model_path = get_llm_id(config["LLM_MODEL"])
    prompt = build_prompt_v2(
        specimen,
        config["LANGUAGE"],
        top_labels[0][0],
        top_labels[1][0],
    )

    try:
        generated_text = llm_runtime.generate(
            model_key=config["LLM_MODEL"],
            model_path=models_path() / llm_model_path,
            messages=prompt.messages,
            settings=config,
        )
    except LLMRuntimeError as exc:
        raise gr.Error(str(exc)) from None

    return clean_llm_output(generated_text)

def get_main_context(specimen):
    config = load_config()
    question, classification_label, order = get_label_caption(specimen, config["LANGUAGE"])
    return config, question, classification_label, order

def refresh_main_page(specimen="cervix"):
    config, question, _, _ = get_main_context(specimen)
    choices = list(question.keys())
    image_size = config["WEBCAM_IMAGE_SIZE"]

    return (
        gr.update(choices=choices, value=choices[0] if choices else None),
        build_config_df(config),
        gr.update(
            webcam_options=gr.WebcamOptions(
                constraints={"video": {"width": image_size, "height": image_size}},
                mirror=False,
            ),
        ),
        *reset_analysis_outputs(config["LANGUAGE"]),
    )

def select_image_for_analysis(image, captured_image, config):
    if isinstance(captured_image, str) and captured_image.startswith("data:image/"):
        return captured_image, "webcam_capture"
    return image, "image_input"

def classify_with_current_config(choice_caption, image, captured_image, specimen):
    config, question, classification_label, order = get_main_context(specimen)
    if choice_caption not in question:
        choice_caption = next(iter(question))

    image, source = select_image_for_analysis(image, captured_image, config)

    label_probs = classify_labels(
        choice_caption,
        image,
        specimen=specimen,
        classification_label=classification_label,
        order=order,
        config=config,
        source=source,
    )
    return label_probs, label_probs

def generate_comments_with_current_config(choice_caption, label_probs, specimen):
    config, question, _, _ = get_main_context(specimen)
    if choice_caption not in question:
        choice_caption = next(iter(question))

    return generate_comments(choice_caption, label_probs, specimen=specimen, config=config)


def show_manual_generation_with_current_config(choice_caption, label_probs, specimen):
    config, question, _, _ = get_main_context(specimen)
    if choice_caption not in question:
        choice_caption = next(iter(question))

    if not _manual_generation_available(choice_caption, label_probs, specimen, config):
        return (
            gr.update(value="", visible=False),
            _manual_generation_button_update(config["LANGUAGE"]),
        )

    language = config["LANGUAGE"]
    return (
        gr.update(value=MANUAL_GENERATION_GUIDANCE[language], visible=True),
        _manual_generation_button_update(language, visible=True),
    )

def build_main_page(specimen="cervix"):
    config, question, _, _ = get_main_context(specimen)

    gr.Markdown("# CYTOLONE")

    with gr.Row():
        with gr.Column():
            question_selector = gr.Dropdown(
                list(question.keys()),
                label="Question Type",
                scale=1,
                allow_custom_value=True,
                )

            config_table = gr.Dataframe(
                value = build_config_df(config),
                interactive = False,
                row_count = (1, "dynamic"),
                column_count = (3, "fixed"),
                label = "Settings"
            )

        with gr.Column():
            image_input = gr.Image(
                type="pil",
                image_mode="RGB",
                height=500,
                width=500,
                webcam_options=gr.WebcamOptions(
                    constraints={"video": {
                        "width": config["WEBCAM_IMAGE_SIZE"],
                        "height": config["WEBCAM_IMAGE_SIZE"]
                        }},
                    mirror=False),
                sources=["webcam", "upload"],
                interactive=True,
                label="Image",
                elem_id="cytolone-image-input"
            )
            gr.HTML(
                "",
                js_on_load=build_iphone_camera_preference_js(config["WEBCAM_IMAGE_SIZE"]),
            )
            capture_payload = gr.Textbox(
                value="",
                visible=False,
            )

    submit_btn = gr.Button("Analyze", variant="primary")

    with gr.Row(equal_height=True, variant="panel"):
        with gr.Column(min_width=300):
            label_output = gr.Label(label="Result", show_label=True)
            label_probs_state = gr.State(value={})

        with gr.Column(min_width=400):
            generation_guidance = gr.Markdown(value="", visible=False)
            generation_button = gr.Button(
                MANUAL_GENERATION_BUTTON_LABELS[config["LANGUAGE"]],
                visible=False,
                interactive=True,
            )
            comment_output = gr.Markdown(
                label="Comments",
                elem_classes="comment-box"
            )

    reset_event = submit_btn.click(
        fn=reset_analysis_outputs,
        inputs=None,
        outputs=[
            label_output,
            label_probs_state,
            generation_guidance,
            generation_button,
            comment_output,
            capture_payload,
        ],
    )

    classify_event = reset_event.success(
        fn=partial(classify_with_current_config, specimen=specimen),
        inputs=[
            question_selector,
            image_input,
            capture_payload,
        ],
        outputs=[label_output, label_probs_state],
        js=CAPTURE_CURRENT_VIEW_JS,
        )

    classify_event.success(
        fn=partial(show_manual_generation_with_current_config, specimen=specimen),
        inputs=[
            question_selector,
            label_probs_state,
            ],
        outputs=[generation_guidance, generation_button],
        )

    generation_button.click(
        fn=partial(generate_comments_with_current_config, specimen=specimen),
        inputs=[question_selector, label_probs_state],
        outputs=comment_output,
    )

    for input_component in (question_selector, image_input):
        input_component.change(
            fn=reset_analysis_outputs,
            inputs=None,
            outputs=[
                label_output,
                label_probs_state,
                generation_guidance,
                generation_button,
                comment_output,
                capture_payload,
            ],
        )

    return (
        question_selector,
        config_table,
        image_input,
        label_output,
        label_probs_state,
        generation_guidance,
        generation_button,
        comment_output,
        capture_payload,
    )

def build_model_management_page():
    gr.Markdown("# Model Management")
    gr.Markdown(
        "Manage one application model or LLM at a time. Downloads and deletions "
        "are user initiated and independent of manual LLM generation."
    )
    summary = gr.Markdown(model_management_summary())
    status = gr.Textbox(label="Status", lines=10, interactive=False)

    config = load_config()
    app_model = gr.Dropdown(
        choices=APP_MODEL_DISPLAY_CHOICES,
        value=config["MODEL"],
        label="Application model",
    )
    app_force = gr.Checkbox(label="Force re-download application model", value=False)
    with gr.Row():
        app_download = gr.Button("Download application model", variant="primary")
        app_delete = gr.Button("Delete application model")
    app_confirm = gr.Checkbox(
        label="Confirm deletion of the selected application model",
        value=False,
    )

    llm_model = gr.Dropdown(
        choices=LLM_MODEL_DISPLAY_CHOICES,
        value=config["LLM_MODEL"],
        label="LLM",
    )
    llm_force = gr.Checkbox(label="Force re-download LLM", value=False)
    with gr.Row():
        llm_download = gr.Button("Download LLM", variant="primary")
        llm_delete = gr.Button("Delete LLM")
    llm_confirm = gr.Checkbox(
        label="Confirm deletion of the selected LLM",
        value=False,
    )

    app_model.change(
        fn=reset_delete_confirmation,
        inputs=None,
        outputs=app_confirm,
    )
    llm_model.change(
        fn=reset_delete_confirmation,
        inputs=None,
        outputs=llm_confirm,
    )

    app_download.click(
        fn=partial(download_model_from_ui, "application"),
        inputs=[app_model, app_force, llm_model],
        outputs=[
            status,
            summary,
            app_model,
            llm_model,
            app_confirm,
            llm_confirm,
        ],
    )
    llm_download.click(
        fn=partial(download_model_from_ui, "llm"),
        inputs=[llm_model, llm_force, app_model],
        outputs=[
            status,
            summary,
            app_model,
            llm_model,
            app_confirm,
            llm_confirm,
        ],
    )
    app_delete.click(
        fn=partial(delete_model_from_ui, "application"),
        inputs=[app_model, app_confirm, llm_model],
        outputs=[
            status,
            summary,
            app_model,
            llm_model,
            app_confirm,
            llm_confirm,
        ],
    )
    llm_delete.click(
        fn=partial(delete_model_from_ui, "llm"),
        inputs=[llm_model, llm_confirm, app_model],
        outputs=[
            status,
            summary,
            app_model,
            llm_model,
            app_confirm,
            llm_confirm,
        ],
    )
    return summary, app_model, llm_model, app_confirm, llm_confirm


def build_model_download_page():
    """Compatibility name for the former Model Download page."""

    return build_model_management_page()

def apply_settings_and_refresh_main(
    language,
    model,
    llm_model,
    webcam_image_size,
    debug,
):
    settings_outputs = apply_settings(
        language,
        model,
        llm_model,
        webcam_image_size,
        debug,
    )
    return (*settings_outputs, *refresh_main_page())

def build_app():
    with _cytolone_blocks() as app:
        gr.HTML(f"<style>{PAGE_TABS_CSS}</style>", container=False, show_label=False)
        with gr.Tabs(selected="launcher", elem_id="page-tabs") as pages:
            with gr.Tab("Launcher", id="launcher"):
                gr.Markdown("# CYTOLONE Launcher")
                with gr.Row():
                    main_btn = gr.Button("CYTOLONE Main", variant="primary")
                    scale_btn = gr.Button("scale-check")
                with gr.Row():
                    settings_btn = gr.Button("Settings")
                    model_btn = gr.Button("Model Management")

            with gr.Tab("CYTOLONE Main", id="main"):
                back_from_main = gr.Button("Back to Launcher")
                main_refresh_targets = build_main_page()

            with gr.Tab("scale-check", id="scale"):
                back_from_scale = gr.Button("Back to Launcher")
                build_scale_checker_page()

            with gr.Tab("Settings", id="settings"):
                back_from_settings = gr.Button("Back to Launcher")
                settings_components, settings_apply_btn, settings_status = build_settings_page()

            with gr.Tab("Model Management", id="model"):
                back_from_model = gr.Button("Back to Launcher")
                (
                    model_management_summary_output,
                    app_model_management_choice,
                    llm_model_management_choice,
                    app_model_delete_confirm,
                    llm_model_delete_confirm,
                ) = build_model_management_page()

        def show_launcher():
            return gr.update(selected="launcher")

        def show_main():
            return (gr.update(selected="main"), *refresh_main_page())

        def show_scale():
            return gr.update(selected="scale")

        def show_settings():
            return (gr.update(selected="settings"), *get_settings_values())

        def show_model_management():
            config = load_config()
            return (
                gr.update(selected="model"),
                model_management_summary(),
                gr.update(choices=APP_MODEL_DISPLAY_CHOICES, value=config["MODEL"]),
                gr.update(choices=LLM_MODEL_DISPLAY_CHOICES, value=config["LLM_MODEL"]),
                gr.update(value=False),
                gr.update(value=False),
            )

        main_btn.click(
            fn=show_main,
            inputs=None,
            outputs=[pages, *main_refresh_targets],
        )
        scale_btn.click(
            fn=show_scale,
            inputs=None,
            outputs=pages,
        )
        settings_btn.click(
            fn=show_settings,
            inputs=None,
            outputs=[pages, *settings_components],
        )
        settings_components[0].change(
            fn=reset_analysis_outputs,
            inputs=settings_components[0],
            outputs=main_refresh_targets[3:]
        )
        settings_apply_btn.click(
            fn=apply_settings_and_refresh_main,
            inputs=settings_components,
            outputs=[*settings_components, settings_status, *main_refresh_targets],
        )
        model_btn.click(
            fn=show_model_management,
            inputs=None,
            outputs=[
                pages,
                model_management_summary_output,
                app_model_management_choice,
                llm_model_management_choice,
                app_model_delete_confirm,
                llm_model_delete_confirm,
            ],
        )

        for back_btn in [back_from_main, back_from_scale, back_from_settings, back_from_model]:
            back_btn.click(
                fn=show_launcher,
                inputs=None,
                outputs=pages,
            )

    return app


def run():
    app = build_app()

    launch_kwargs = {"theme": CYTOLONE_THEME}
    if os.environ.get("CYTOLONE_APP_MODE") == "1":
        launch_kwargs.update(
            server_name=os.environ.get("CYTOLONE_SERVER_HOST", "127.0.0.1"),
            server_port=int(os.environ.get("CYTOLONE_SERVER_PORT", "7860")),
            inbrowser=False,
            prevent_thread_lock=False,
        )

    app.launch(**launch_kwargs)

if __name__ == "__main__":
    run()
