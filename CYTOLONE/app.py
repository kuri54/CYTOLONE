import os
import re
import numpy as np
import gradio as gr
from functools import partial
from PIL import Image

import torch
from mlx_lm import load, generate
from transformers import AutoModel, AutoProcessor

from CYTOLONE.label_caption import (
    get_label_caption,
    get_order_type,
    get_caption
    )

from CYTOLONE.model import get_model_id, get_llm_id
from CYTOLONE.download_models import download_models_with_status
from CYTOLONE.scale_check.scale_checker import build_scale_checker_page
from CYTOLONE.settings_page import apply_settings, build_settings_page, get_settings_values

from CYTOLONE.util import load_config, build_config_df

model_cache = {}
processor_cache = {}
llm_model_cache = {}
llm_tokenizer_cache = {}

PAGE_TABS_CSS = """
#page-tabs > .tab-wrapper > .tab-container[role="tablist"] > button:not([data-tab-id="launcher"]),
#page-tabs > .tab-wrapper > .tab-container.visually-hidden > button:not(:first-child),
#page-tabs > .tab-wrapper > .overflow-menu {
    display: none !important;
}
"""

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

def center_crop(image, size=1024):
    if isinstance(image["composite"], np.ndarray):
        image = Image.fromarray(image["composite"])

    width, height = image["composite"].size
    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size
    return image["composite"].crop((left, top, right, bottom))

def classify_labels(choice_caption, image, specimen, classification_label, order, config):
    if config["DEBUG"]:
        save_dir = "debug_images"
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        image["composite"].save(f"{save_dir}/original_image.jpg")

    image = center_crop(image, size=1024)

    if config["DEBUG"]:
        image.save(f"{save_dir}/cropped_image.jpg")

    model_path = get_model_id(config["MODEL"])

    if model_path not in model_cache:
        model = AutoModel.from_pretrained(
            f"mlx_models/{model_path}",
            local_files_only=True,
            device_map="auto")

        processor = AutoProcessor.from_pretrained(
            f"mlx_models/{model_path}",
            local_files_only=True
            )

        model_cache[model_path] = model
        processor_cache[model_path] = processor

    else:
        model = model_cache[model_path]
        processor = processor_cache[model_path]

    order_type = get_order_type(specimen, config["LANGUAGE"], choice_caption)
    labels = get_partial_labels(classification_label, order, order_type)

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

def generate_comments(choice_caption, label_probs, specimen, config):
    order_type = get_order_type(specimen, config["LANGUAGE"], choice_caption)
    top_labels = sorted(label_probs.items(), key=lambda x: x[1], reverse=True)[:2]
    threshold = config["LLM_GEN_THRESHOLD"]

    if not (top_labels[0][1] < threshold and len(top_labels) > 1 and order_type == "Diagnosis"):
        return " "

    llm_model_path = get_llm_id(config["LLM_MODEL"])

    if llm_model_path not in llm_model_cache:
        model, tokenizer = load(f"mlx_models/{llm_model_path}")

        llm_model_cache[llm_model_path] = model
        llm_tokenizer_cache[llm_model_path] = tokenizer
    else:
        model = llm_model_cache[llm_model_path]
        tokenizer = llm_tokenizer_cache[llm_model_path]

    caption = get_caption(specimen, config["LANGUAGE"], top_labels[0][0], top_labels[1][0])

    if hasattr(tokenizer, "apply_chat_template"):
        messages = [{"role": "user", "content": caption}]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    else:
        prompt = caption

    generated_text = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=2000,
        verbose=False
    )

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
            canvas_size=(image_size, image_size),
            webcam_options=gr.WebcamOptions(
                constraints={"video": {"width": image_size, "height": image_size}},
                mirror=False,
            ),
        ),
    )

def classify_with_current_config(choice_caption, image, specimen):
    config, question, classification_label, order = get_main_context(specimen)
    if choice_caption not in question:
        choice_caption = next(iter(question))

    return classify_labels(
        choice_caption,
        image,
        specimen=specimen,
        classification_label=classification_label,
        order=order,
        config=config,
    )

def generate_comments_with_current_config(choice_caption, label_probs, specimen):
    config, question, _, _ = get_main_context(specimen)
    if not config["LLM_GEN"]:
        return ""
    if choice_caption not in question:
        choice_caption = next(iter(question))

    return generate_comments(choice_caption, label_probs, specimen=specimen, config=config)

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
            image_input = gr.ImageEditor(
                type="pil",
                image_mode="RGB",
                height=500,
                width=500,
                canvas_size=(
                    config["WEBCAM_IMAGE_SIZE"],
                    config["WEBCAM_IMAGE_SIZE"]
                    ),
                fixed_canvas=True,
                webcam_options=gr.WebcamOptions(
                    constraints={"video": {
                        "width": config["WEBCAM_IMAGE_SIZE"],
                        "height": config["WEBCAM_IMAGE_SIZE"]
                        }},
                    mirror=False),
                sources=["webcam", "upload"],
                eraser=False,
                brush=False,
                layers=False
            )

    submit_btn = gr.Button("Analyze", variant="primary")

    with gr.Row(equal_height=True, variant="panel"):
        with gr.Column(min_width=300):
            label_output = gr.Label(label="Result", show_label=True)

        with gr.Column(min_width=400):
            comment_output = gr.Markdown(
                label="Comments",
                elem_classes="comment-box"
            )

    classify_event = submit_btn.click(
        fn=partial(classify_with_current_config, specimen=specimen),
        inputs=[
            question_selector,
            image_input,
        ],
        outputs=label_output
        )

    classify_event.success(
        fn=partial(generate_comments_with_current_config, specimen=specimen),
        inputs=[
            question_selector,
            label_output
            ],
        outputs=comment_output
        )

    return question_selector, config_table, image_input

def build_model_download_page():
    gr.Markdown("# Model Download")
    gr.Markdown("Download models using the current CYTOLONE/config.ini settings.")
    force_download = gr.Checkbox(label="Force re-download", value=False)
    download_btn = gr.Button("Download Models", variant="primary")
    status = gr.Textbox(label="Status", lines=10, interactive=False)

    download_btn.click(
        fn=download_models_with_status,
        inputs=force_download,
        outputs=status,
    )

def apply_settings_and_refresh_main(language, model, llm_model, llm_gen, llm_threshold, webcam_image_size, debug):
    settings_outputs = apply_settings(
        language,
        model,
        llm_model,
        llm_gen,
        llm_threshold,
        webcam_image_size,
        debug,
    )
    return (*settings_outputs, *refresh_main_page())

def run():
    with gr.Blocks(title="CYTOLONE") as app:
        gr.HTML(f"<style>{PAGE_TABS_CSS}</style>", container=False, show_label=False)
        with gr.Tabs(selected="launcher", elem_id="page-tabs") as pages:
            with gr.Tab("Launcher", id="launcher"):
                gr.Markdown("# CYTOLONE Launcher")
                with gr.Row():
                    main_btn = gr.Button("CYTOLONE Main", variant="primary")
                    scale_btn = gr.Button("scale-check")
                with gr.Row():
                    settings_btn = gr.Button("Settings")
                    model_btn = gr.Button("Model Download")

            with gr.Tab("CYTOLONE Main", id="main"):
                back_from_main = gr.Button("Back to Launcher")
                main_refresh_targets = build_main_page()

            with gr.Tab("scale-check", id="scale"):
                back_from_scale = gr.Button("Back to Launcher")
                build_scale_checker_page()

            with gr.Tab("Settings", id="settings"):
                back_from_settings = gr.Button("Back to Launcher")
                settings_components, settings_apply_btn, settings_status = build_settings_page()

            with gr.Tab("Model Download", id="model"):
                back_from_model = gr.Button("Back to Launcher")
                build_model_download_page()

        def show_launcher():
            return gr.update(selected="launcher")

        def show_main():
            return (gr.update(selected="main"), *refresh_main_page())

        def show_scale():
            return gr.update(selected="scale")

        def show_settings():
            return (gr.update(selected="settings"), *get_settings_values())

        def show_model_download():
            return gr.update(selected="model")

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
        settings_apply_btn.click(
            fn=apply_settings_and_refresh_main,
            inputs=settings_components,
            outputs=[*settings_components, settings_status, *main_refresh_targets],
        )
        model_btn.click(
            fn=show_model_download,
            inputs=None,
            outputs=pages,
        )

        for back_btn in [back_from_main, back_from_scale, back_from_settings, back_from_model]:
            back_btn.click(
                fn=show_launcher,
                inputs=None,
                outputs=pages,
            )

    app.launch()

if __name__ == "__main__":
    run()
