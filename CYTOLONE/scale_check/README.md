# Scale Checker
<div align="center">
  <img src="/assets/scale_check.png" alt="Scale Check" width="60%">
</div>

|[日本語]()|

## ✨ Overview
- Scale Checker is a tool designed to **visually check and adjust scale differences** between training images and camera-captured images when using CYTOLONE.
- By **displaying the reference image and camera image side by side** and adjusting the scale with a slider, you can **calculate the optimal camera input size**.

    <br>

    📝 Note: Why is this needed?  
    > The scale of input images may differ from training images depending on the microscope, lens type, iPhone model, and adapter. Using raw webcam images without adjustment can lead to inaccurate results.  
    > This tool helps you **calculate the appropriate cropping factor** for your iPhone camera input.

<br>

<div align="center">

<picture>
  <img alt="scale" src="/assets/scale.jpg" width="30%" height="30%">
</picture> 

</div>

<br>

📝 Note:  
> Currently, the only **verified setup** is **iPhone 15 × [i-NTER LENS](https://www.microscope-net.com/products/smartphone/inter-lens/)**.  
> Please report other device combinations via **Issues**!

### 🚀 How to Launch the App
- Launch: 
    ```bash
    scale-check
    ```
    Access the URL displayed in the terminal using your web browser.  
    動画？

- Usage
    1. **Select the reference image** using the radio buttons.
    2. **Capture an image** of **normal squamous epithelial cells** with a **10x objective lens**, making sure the cells are clearly visible without overlapping.
    3. **Adjust the scale using the slider** and compare with the reference image.
    4. Check the **"Recommended Camera Input Size"** displayed at the bottom of the screen.

        💡 Tip:  
        > The **ideal scale** is when the **nuclei sizes** match between the two images.  
        > It is easier to check if you **expand to full screen** and **zoom in**.

       - If you find it difficult to adjust, feel free to **share your images via Issues**. We can calculate the scale for you.
       - Please **include your device information** when reporting.

    5. Update your settings using the values shown on the screen.
       > 🔍 Scale Factor: 0.87  
       > 📐 Cropped size: 890×890px  
       > 📷 Recommended original image size: 1177×1177px  
       > ```bash
       > cytolone-config --DEBUG False --WEBCAM_IMAGE_SIZE 1177
       > ```