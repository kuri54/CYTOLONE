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

### 📦 Install the macOS App
For general use, download the Apple Silicon DMG from GitHub Releases:
```text
CYTOLONE-<version>-mac-arm64.dmg
```

1. Open the [GitHub Releases page](https://github.com/kuri54/CYTOLONE/releases).
2. Download the Apple Silicon `.dmg` and drag `CYTOLONE.app` to `Applications`.
3. Double-click `CYTOLONE.app`.

The app requires an Apple Silicon Mac running macOS 13 or later.

CYTOLONE is currently distributed without Apple Developer ID signing or
notarization. On first launch, macOS may report that Apple cannot check the app
for malicious software. If you downloaded the DMG from the official CYTOLONE
GitHub Releases page:

1. Try to open `CYTOLONE.app` once, then close the warning.
2. Open **System Settings > Privacy & Security**.
3. Scroll to **Security** and click **Open Anyway** for CYTOLONE.
4. Confirm **Open**.

This approval is required only for the first launch. See
[Apple's instructions for opening an app from an unknown developer](https://support.apple.com/en-us/guide/mac-help/-mh40616/mac).

### 🚀 First Launch and Later Launches
On first launch, CYTOLONE shows a simple English native setup window. It
prepares the required local environment, then opens the CYTOLONE interface in
your default browser. Model download is a separate action
from the CYTOLONE launcher.

Later launches reuse the prepared environment. If CYTOLONE is already running,
launching the app again opens the existing CYTOLONE interface without starting a
second server. After setup and model download are complete, CYTOLONE can be
used offline.

The CYTOLONE launcher opens first. From the launcher, you can open CYTOLONE
Main, scale-check, Settings, and Model Download. Only the Launcher tab is shown
in the navigation bar; use the launcher buttons to open each page. Click
**CYTOLONE Main** to open the existing analysis screen, then select your camera
and click **Analyze** to evaluate the current view.

### 🔄 Update, Quit, and Removal
To update CYTOLONE, download the newer DMG and replace the existing
`CYTOLONE.app` with the new app. Downloaded models and settings are preserved.

Closing the browser tab does not stop CYTOLONE. To stop it, right-click the
CYTOLONE icon in the Dock and choose **Quit**.

For normal app-only removal, first choose **Quit** from the CYTOLONE Dock icon,
then move `CYTOLONE.app` to the Trash. Managed models and settings remain.

For complete removal, while CYTOLONE is running, right-click its Dock icon,
choose **Remove CYTOLONE Data…**, and complete the confirmation. After the
removal finishes, move `CYTOLONE.app` to the Trash.

If setup cannot be completed, choose **Retry Setup** in the native window and
check that the Mac is connected to the internet. If the problem continues,
quit CYTOLONE and try launching it again later.

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

You can edit settings from the CYTOLONE launcher by opening **Settings**.

⚠️ Warning:
> Enable `LLM_GEN` **only if your Mac has at least 64GB of unified memory**.
> Insufficient memory **may cause system crashes**.

`WEBCAM_IMAGE_SIZE` is the **most critical setting** in this app. Please check [this guide](/CYTOLONE/scale_check/README.md) for details.

### ⬇️ Model Download
You can download models from the CYTOLONE launcher by opening **Model Download**.

Already installed models are skipped automatically. Use **Force re-download** only when you want to download again.

Required models will be downloaded automatically. If `LLM_GEN` is set to `False`, **language models will not be downloaded**. To use LLM features, change the setting to `True` and download models again.

⚠️ Warning:
> Model download **requires an internet connection**.

### 🌐 Network and Offline Use
Downloading the DMG, preparing the app environment, and downloading models
require network access. CYTOLONE does not perform background update checks and
does not modify Tailscale, Taildrive, Owlfile, or network sharing settings.

After setup and model download are complete, CYTOLONE can be used offline.

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
