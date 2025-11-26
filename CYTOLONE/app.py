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

from CYTOLONE.util import load_config, build_config_df

model_cache = {}
processor_cache = {}
llm_model_cache = {}
llm_tokenizer_cache = {}

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

    if not (top_labels[0][1] < 0.8 and len(top_labels) > 1 and order_type == "Diagnosis"):
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

    generated_text = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=2000,
        verbose=False
    )

    return clean_llm_output(generated_text)

def run():
    # ----------------- #
    specimen = "cervix"
    # ----------------- #

    config = load_config()

    question, classification_label, order = get_label_caption(specimen, config["LANGUAGE"])

    classify_fn = partial(
        classify_labels,
        specimen=specimen,
        classification_label=classification_label,
        order=order,
        config=config
    )

    with gr.Blocks(title="CYTOLONE") as app:
        gr.Markdown("# CYTOLONE")

        # 入力セクション
        with gr.Row():
            with gr.Column():
                question_selector = gr.Dropdown(
                    question,
                    label="Question Type",
                    scale=1
                    )

                gr.Dataframe(
                    value = build_config_df(config),
                    interactive = False,
                    row_count = (1, "dynamic"),
                    col_count = (3, "fixed"),
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

            if config["LLM_GEN"]:
                with gr.Column(min_width=400):
                    comment_output = gr.Markdown(
                        label="Comments",
                        elem_classes="comment-box"
                    )

        classify_event = submit_btn.click(
            fn=classify_fn,
            inputs=[
                question_selector,
                image_input,
            ],
            outputs=label_output
            )

        if config["LLM_GEN"]:
            classify_event.success(
                fn=partial(generate_comments, specimen=specimen, config=config),
                inputs=[
                    question_selector,
                    label_output
                    ],
                outputs=comment_output
                )

    app.launch()

if __name__ == "__main__":
    run()