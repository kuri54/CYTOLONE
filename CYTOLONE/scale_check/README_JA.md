# Scale Checker
<div align="center">
  <img src="/assets/scale_check.png" alt="Scale Check" width="60%">
</div>

## ✨ 概要
- Scale Checkerは、CYTOLONEを使用する際に「学習画像」と「カメラ画像」のスケールのズレを直感的に確認・調整するためのツールです。
- 基準画像とカメラ画像を並べて表示し、スライダーでスケールを調整しながら比較することで、最適なカメラ入力サイズを算出できます。

    <br>

    📝 Note: なぜ必要なの？  
    > 顕微鏡・レンズ・iPhoneの機種・アダプタの違いによって、入力画像とモデル学習時の画像スケールが異なります。そのままWebcam画像を判定に使うと、結果がブレる原因になります。  
    > そのため、iPhone画像を適切にクロップする必要があり、その係数を算出するのが本アプリです。

<br>

<div align="center">

<picture>
  <img alt="scale" src="/assets/scale.jpg" width="30%" height="30%">
</picture> 

</div>

<br>

📝 Note:  
> 現在、検証済みの組み合わせは
iPhone 15と[i-NTER LENS](https://www.microscope-net.com/products/smartphone/inter-lens/) のみです。  
> その他の組み合わせはissueで報告してください！

### 🚀 アプリの起動
- 起動
    ```bash
    scale-check
    ```
    ターミナルに表示されたURLにWebブラウザからアクセスしてください。  
    動画？

- 操作手順
    1. 基準画像（Reference Image）を選択
    2. 10倍対物レンズで、正常な扁平上皮細胞が重なりなく見える場所の写真を撮影
    3. スライダーでスケールを調整し、基準画像と比較
    4. 画面下部に表示される「必要なカメラ入力サイズ」を参考に設定を調整

        💡 Tip:  
        > 核の大きさが揃うスケールが最適です。
        > 全画面表示にして拡大しながら確認すると調整しやすくなります。

       - 調整が難しい場合は、画像をIssueで共有してください。こちらで算出しお知らせします。
       - その際は、必ず使用したデバイス情報を記載してください。

    5. 表示された数値で設定を更新
       > 🔍 Scale Factor: 0.87  
       > 📐 Cropped size: 890×890px  
       > 📷 Recommended original image size: 1177×1177px  
       > ```bash
       > cytolone-config --DEBUG False --WEBCAM_IMAGE_SIZE 1177
       > ```