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

## 💡 Usage
- This library is optimized **only** for Apple Silicon Macs and iPhones.
- It does **not support Windows or other operating systems**, and other camera devices are untested.

### 💻 Physical Setup
1. Prepare an Apple Silicon Mac and iPhone, and log in with the **same Apple ID**.
2. Connect your Mac and iPhone using a **USB-C cable** or **Thunderbolt cable**.
3. Connect your iPhone to the microscope using an adapter.

📝 Note:
> Bluetooth is supported, but **a wired connection is recommended for better stability**.

<div align="center">
  <img src="/assets/setup.png" alt="Setup" width="80%">
</div>

### 📦 Recommended Install: GitHub Releases Package
This is the recommended setup for regular users. You do **not** need to clone this repository, install Homebrew, or create a shell alias.

1. Open the [GitHub Releases page](https://github.com/kuri54/CYTOLONE/releases).
2. Download the macOS Apple Silicon package:
   ```text
   CYTOLONE-<version>-mac-arm64.tar.gz
   ```
3. Double-click the downloaded `.tar.gz` file to extract it.
4. Open the extracted folder and double-click:
   ```text
   install.command
   ```
5. When the installer finishes, restart Terminal if needed.
6. Launch CYTOLONE from Terminal:
   ```bash
   cytolone
   ```

The installer places CYTOLONE in:
```text
~/.local/share/cytolone/current
```

It also creates this launcher:
```text
~/.local/bin/cytolone
```

If `uv` is already installed, the installer uses it as-is. If `uv` is not installed, the installer installs `uv` using the official `uv` installer. It does not use Homebrew.

The project virtual environment is normally created at:
```text
~/.local/share/cytolone/current/.venv
```

To uninstall CYTOLONE, double-click:
```text
uninstall.command
```

`uninstall.command` removes only the CYTOLONE install directory and the `~/.local/bin/cytolone` launcher. It does **not** remove `uv`, Python installed by `uv`, or the `uv` cache.

### 🛠 Developer / Source Install
Use this method if you want to run CYTOLONE from a cloned source checkout.

1. Install Python 3.12.

   macOS includes Python, but the preinstalled version is too old for this app.

   ```bash
   brew install python@3.12
   ```

   For [uv](https://github.com/astral-sh/uv) users:
   ```bash
   uv python install 3.12
   ```

2. Clone this repository and move into it:
   ```bash
   git clone https://github.com/kuri54/CYTOLONE.git
   cd CYTOLONE
   ```

3. Install dependencies.

   With `uv`:
   ```bash
   uv sync
   ```

   With `venv` and `pip`:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

4. Launch from the source checkout:
   ```bash
   uv run cytolone
   ```

### ⚙️ App Settings
Default settings:
```text
LANGUAGE = en --------------- App language setting (en or ja)
MODEL = v1.1 ---------------- Model version to use (choose v1.0 or v1.1)
LLM_MODEL = gpt-oss-20b ----- LLM to use (choose deepseek-r1 or gpt-oss-120b or gpt-oss-20b)
LLM_GEN = False ------------- Enable or disable LLM-based findings generation
LLM_GEN_THRESHOLD = 0.8 ----- Threshold for enabling LLM output
WEBCAM_IMAGE_SIZE = 1024 ---- Webcam input image size
```

You can edit settings from the launcher. Run `cytolone` or `uv run cytolone`, then open **Settings**.

The CLI commands remain available:
```bash
cytolone-config --list
cytolone-config --LANGUAGE ja
cytolone-config --reset
```

⚠️ Warning:
> Enable `LLM_GEN` **only if your Mac has at least 64GB of unified memory**.
> Insufficient memory **may cause system crashes**.

`WEBCAM_IMAGE_SIZE` is the **most critical setting** in this app. Please check [this guide](/CYTOLONE/scale_check/README.md) for details.

### ⬇️ Model Download
You can download models from the launcher. Run `cytolone` or `uv run cytolone`, then open **Model Download**.

Already installed models are skipped automatically. Use **Force re-download** only when you want to download again.

The CLI command remains available:
```bash
download-model
```

Required models will be downloaded automatically. If `LLM_GEN` is set to `False`, **language models will not be downloaded**. To use LLM features, change the setting to `True` and download models again.

⚠️ Warning:
> Model download **requires an internet connection**.
> For offline environments, temporarily connect to the internet or manually download the models on another PC and place them in the specified directories.

Download links:
[kuri54/mlx-CYTOLONE-v1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1)
[kuri54/mlx-CYTOLONE-v1.1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1.1)
[mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit](https://huggingface.co/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit)
[mlx-community/gpt-oss-120b-MXFP4-Q4](https://huggingface.co/mlx-community/gpt-oss-120b-MXFP4-Q4)
[mlx-community/gpt-oss-20b-MXFP4-Q8](https://huggingface.co/mlx-community/gpt-oss-20b-MXFP4-Q8)

Place the models in the following directories:
```text
CYTOLONE/mlx-models/kuri54/mlx-CYTOLONE-v1/
CYTOLONE/mlx-models/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit/
```

### 🚀 Launch the App
For package users:
```bash
cytolone
```

To run directly from the installed package directory:
```bash
cd ~/.local/share/cytolone/current
uv run cytolone
```

For source checkout users:
```bash
uv run cytolone
```

- The CYTOLONE launcher opens first.
- From the launcher, you can open CYTOLONE Main, scale-check, Settings, and Model Download.
- Only the Launcher tab is shown in the navigation bar; use the launcher buttons to open each page.
- Open the URL displayed in the terminal in your web browser.
- Click **CYTOLONE Main** to open the existing analysis screen.
- Select your camera and click **Analyze** to evaluate the current view.

📝 Note:
> After dependencies and models are installed, CYTOLONE can run offline.

### 🌐 Network and Storage Notes
- Downloading the `.tar.gz` package from GitHub Releases requires network access.
- `install.command` uses the network only when `uv` is not already installed.
- The first `cytolone` launch may use the network while `uv` installs Python packages.
- Model download uses the network and can require substantial disk space.
- CYTOLONE does not modify Tailscale, Taildrive, Owlfile, or network sharing settings.
- If your home directory is synced or shared by another tool, note that `~/.local/share/cytolone/current/.venv` and downloaded models can be large.
- The top-level `assets/` directory is used for GitHub README images and is not required in the release package.

<br>

### 📷 Camera Connection
Click the red button to connect to your iPhone.
<div align="center">
  <img src="/assets/webcam.png" alt="Webcam" width="60%">
</div>

<br>

💡 Tip:
> If your face appears using the built-in Mac camera, select your iPhone once. CYTOLONE remembers that iPhone in the browser and tries to reconnect it automatically the next time.
> If Center Stage is enabled when using the iPhone camera, turn it off from the Mac menu bar video menu, or from Control Center > Video Effects. This is a macOS Continuity Camera setting, not a CYTOLONE setting.

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
