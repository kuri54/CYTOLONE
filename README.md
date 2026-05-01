<div align="center">
<picture>
  <img alt="cytolone logo" src="/assets/cytolone_logo.jpg" width="80%" height="80%">
</picture> 

_**"Always by you side."**_
  
</div>

<br>

|[日本語](./README_JA.md)|

## ✨ Overview
**CYTOLONE** (Cytology All-in-One) is a real-time AI-powered support tool for **cytotechnologists in cervical cytology**.  
Unlike conventional AI systems that require **whole slide imaging (WSI)**, CYTOLONE operates **without WSI**, enabling **low-cost and high-speed AI support** using just an iPhone and an Apple Silicon Mac.

Key Features:
- **Real-time support**: Provides results in less than 0.5 seconds
- **WSI-free, low-cost operation**: No expensive scanners or GPUs required
- **High-accuracy classification using hierarchical labeling**: Covers Anomaly, Malignancy, Bethesda, and Diagnosis categories
- **Optional LLM-based findings generation**

For more details, see the published paper:  
[🔗 Whole Slide Imaging-Free Supporting Tool for Cytotechnologists in Cervical Cytology (Modern Pathology 2025)](https://doi.org/10.1016/j.modpat.2025.100817)

Below is an example image used in the study:
<div align="center">
  <img src="/assets/sample_study_image.png" alt="Example Study Image" width="60%">
</div>

<br>

<div align="center">
  <img src="/assets/cytolone_app.png" alt="CYTOLONE App Image" width="100%">
</div>

## 🤩 Update History
- **xxxx**
  - Released CYTOLONE v1.1.4!
  - Added the CYTOLONE launcher.
  - You can now open CYTOLONE Main, scale-check, Settings, and Model Download from `cytolone`.

- **2026/02/16**
  - Released CYTOLONE v1.1.3!
  - Made `scale-check` semi-automated!

- **2025/09/10**
  - Released CYTOLONE-v1.1.1!
  - LLM selection is now supported!  
    Available LLMs: MLX versions of `DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit`, `gpt-oss-120b-MXFP4-Q4`, and `gpt-oss-20b-MXFP4-Q8`.
  - UI updated.

- **2025/07/03**
  - Released CYTOLONE-v1.1!
  - Improved performance over v1.0, especially on Bethesda and Diagnosis tasks
  - See the Model Card for details: https://huggingface.co/kuri54/mlx-CYTOLONE-v1.1

- **2025/07/03**
  - Migrated setup from `setup.py` to `pyproject.toml`
  - Added support for `uv` script execution

- **2025/06/13**
  - Public release of this page
  - Publication of the research paper in *Modern Pathology*


## 💡 Usage
- This library is optimized **only** for Apple Silicon Macs and iPhones.
- It does **not support Windows or other operating systems**, and other camera devices are untested.

### 💻 Setup
0. **Preparation**
    - Prepare an Apple Silicon Mac and iPhone, and log in with the **same Apple ID**.  
    - Connect your Mac and iPhone using a **USB-C cable** (**or Thunderbolt cable**) .  
    📝 Note:  
      > Bluetooth is supported, but **a wired connection is recommended for  better stability**.  
    - Connect your iPhone to the microscope using an adapter.
 
<div align="center">
  <img src="/assets/setup.png" alt="Setup" width="80%">
</div>

1. **Install Python**

    📢 Important:  
    > macOS comes with Python pre-installed, but the version is outdated and cannot install the latest libraries required by this app.  
    > Please install **Python 3.12**.

    <br>

    ```bash
    brew install python@3.12
    ```

    **For [uv](https://github.com/astral-sh/uv) users:**
    ```bash
    uv python install 3.12
    ```

2. **Installation**:
    - Clone this repository.
     
    - Move into the cloned directory:
      ```bash
      cd CYTOLONE
      ```

    📝 Note:
    > **For uv users:**
    This section is unnecessary. Install dependencies with `uv sync`, then proceed to step 3.

    <br>

    - Create and activate a virtual environment:
      ```bash
      python3.12 -m venv venv
      source venv/bin/activate
      ```

      📝 Note:  
      > Perform all subsequent steps **within this virtual environment**  

    <br>

    - Install required libraries: 
      ```bash
      pip install -e .
      ```



3. **App Settings**
    - Default settings:
      ```
      LANGUAGE = en --------------- App language setting (en or ja)
      MODEL = v1.1 ---------------- Model version to use (choose v1.0 or v1.1)
      LLM_MODEL = gpt-oss-20b ----- LLM to use (choose deepseek-r1 or gpt-oss-120b or gpt-oss-20b)
      LLM_GEN = False ------------- Enable or disable LLM-based findings generation
      LLM_GEN_THRESHOLD = 0.8 ----- Threshold for enabling LLM output
      WEBCAM_IMAGE_SIZE = 1024 ---- Webcam input image size
      ```

    - How to change settings
      - You can edit settings from the launcher: run `cytolone` or `uv run cytolone`, then open **Settings**.
      - The CLI commands remain available.
      - Display all settings: 
        ```bash
        cytolone-config --list
        ```

      - Set the app language to Japanese: 
        ```bash
        cytolone-config --LANGUAGE ja
        ```

      - Reset to default settings:
        ```bash
        cytolone-config --reset
        ```

        ⚠️ Warning:  
        Enable `LLM_GEN` **only if your Mac has at least 64GB of unified memory**.  
        Insufficient memory **may cause system crashes**.

    - `WEBCAM_IMAGE_SIZE`  
       📢 Important:  
       > `WEBCAM_IMAGE_SIZE` is the **most critical setting** in this app.  
       > Please check [this guide](/CYTOLONE/scale_check/README.md) for details.  

    <br>

    - Download the models
      - You can download models from the launcher: run `cytolone` or `uv run cytolone`, then open **Model Download**.
      - Already installed models are skipped automatically. Use **Force re-download** only when you want to download again.
      - The CLI command remains available.
      ```bash
      download-model
      ```
      - Required models will be downloaded automatically.  
      - If `LLM_GEN` is set to `False`, **language models will not be downloaded**.  
        To use LLM features, change the setting to `True` and run the command again.  

      ⚠️ Warning:  
      > `download-model` **requires an internet connection**.  
      > For offline environments, temporarily connect to the internet or manually download the models on another PC and place them in the specified directories.

      Download links:  
      [kuri54/mlx-CYTOLONE-v1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1)  
      [kuri54/mlx-CYTOLONE-v1.1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1.1)  
      [mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit](https://huggingface.co/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit)  
      [mlx-community/gpt-oss-120b-MXFP4-Q4](https://huggingface.co/mlx-community/gpt-oss-120b-MXFP4-Q4)  
      [mlx-community/gpt-oss-20b-MXFP4-Q8](https://huggingface.co/mlx-community/gpt-oss-20b-MXFP4-Q8)  

      Place the models in the following directories:  
      ```
      CYTOLONE/mlx-models/kuri54/mlx-CYTOLONE-v1/  
      CYTOLONE/mlx-models/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit/
      ```

### 🚀 Launch the App
- Launch:
    ```bash
    cytolone
    ```
    or:
    ```bash
    uv run cytolone
    ```
    - The CYTOLONE launcher opens first.
    - From the launcher, you can open CYTOLONE Main, scale-check, Settings, and Model Download.
    - Only the Launcher tab is shown in the navigation bar; use the launcher buttons to open each page.
    - Open the URL displayed in the terminal in your web browser.
    - Click **CYTOLONE Main** to open the existing analysis screen.
    - Simply select your camera, capture an image, and click the Analyze button to view the results.

    <br>

    📝 Note:  
    > Works offline as well!  

<br>

- Camera Connection  
Click the red button to connect to your iPhone.  
<div align="center">
  <img src="/assets/webcam.png" alt="Webcam" width="60%">
</div>

<br>

💡 Tip:  
> If your face appears using the built-in Mac camera, simply select your iPhone to switch.

<br>

⚠️ Warning:  
> Make sure to use the x10 objective lens when taking photos.  
> Other magnifications are not supported.  

## 🔭 Planned Features
The following features are planned for future updates:

- **Region-of-Interest Highlighting with Red Circles**  
  Users will be able to place a red circle on any part of the image to prompt the model to focus on that specific area during evaluation.  
  _Reference_: [What does CLIP know about a red circle? Visual prompt engineering for VLMs](https://arxiv.org/pdf/2304.06712)

- **Screening Mode**  
  When enabled, this mode will continuously evaluate the "Anomaly" category in real time during microscopic observation.  

## 🎉 Citation
```
@article{kurita2025cytolone,
         title={Whole Slide Imaging-Free Supporting Tool for Cytotechnologists in Cervical Cytology}, 
         author={Yuki Kurita et al.},
         year={2025},
         journal={Modern Pathology},
         doi={10.1016/j.modpat.2025.100817}
}
```
