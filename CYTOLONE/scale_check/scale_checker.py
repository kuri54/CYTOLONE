import os
import gradio as gr
from pathlib import Path
from PIL import Image

from CYTOLONE.util import load_config

IMAGE_DIR = Path("CYTOLONE/scale_check/default_images")
REFERENCE_IMAGE_FILES = {
    "Image 1": IMAGE_DIR / "image1.jpg",
    "Image 2": IMAGE_DIR / "image2.jpg"
}

def load_image(name):
    return Image.open(REFERENCE_IMAGE_FILES[name])

def overlay_and_calculate(reference_img, input_img, scale=1.0):
    crop_size = int(1024 * scale)
    required_input_size = int(1024 / scale)

    w, h = input_img["composite"].size
    left = max((w - crop_size) // 2, 0)
    top = max((h - crop_size) // 2, 0)
    cropped_input = input_img["composite"].crop((left, top, left + crop_size, top + crop_size))
    resized_input = cropped_input.resize((1024, 1024))

    if reference_img.size != (1024, 1024):
        reference_img = reference_img.resize((1024, 1024))

    info_text = (
        f"🔍 Scale Factor: {scale:.2f}\n"
        f"📐 Cropped size: {crop_size}×{crop_size}px\n"
        f"📷 Recommended original image size: {required_input_size}×{required_input_size}px"
    )

    return (reference_img, resized_input), info_text

def run():
    config = load_config(config_file_path="./CYTOLONE/default_config/default_config.ini")

    with gr.Blocks() as app:
        gr.Markdown("# Image Scale Checker")

        radio = gr.Radio(
            choices=list(REFERENCE_IMAGE_FILES.keys()),
            value="Image 1",
            label="Select Reference Image"
        )

        with gr.Row():
            reference_image_display = gr.Image(
                width=300, height=300,
                type="pil",
                label="Reference Image Preview",
                value=load_image("Image 1"),
            )
            # adjust_input = gr.Image(
            #     width=300, height=300,
            #     type="pil",
            #     label="Adjust Image Preview"
            #     )

            adjust_input = gr.ImageEditor(
                width=300, height=300,
                type="pil",
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
                layers=False, 
                label="Adjust Image Preview"
            )

        with gr.Row():
            scale_slider = gr.Slider(0.5, 2.0, step=0.01, value=1.0, label="Scale Factor")
            compare_btn = gr.Button("Compare")

        result_slider = gr.ImageSlider(label="Compare Reference vs Adjusted")
        result_text = gr.Textbox(label="Scale Info", lines=3)

        radio.change(fn=load_image, inputs=radio, outputs=reference_image_display)

        compare_btn.click(
            fn=overlay_and_calculate,
            inputs=[reference_image_display, adjust_input, scale_slider],
            outputs=[result_slider, result_text]
        )

    app.launch()

if __name__ == "__main__":
    run()
