<div align="center">
<picture>
  <img alt="cytolone logo" src="/assets/cytolone_logo.jpg" width="80%" height="80%">
</picture> 

_**"Always by you side."**_
  
</div>

<br>

## ✨ 概要
**CYTOLONE** (Cytology All-in-One) は、顕微鏡とAIをリアルタイムで連携させることで、**細胞検査士による子宮頸部細胞診のスクリーニングを支援するツール**です。  
従来のAI支援システムで必要とされていた**WSI（全スライド画像）作成を不要**とし、iPhoneとApple Silicon Macだけで運用可能な低コスト・高速AI支援を実現しました。

主な特徴:
- **リアルタイム支援**：0.5秒以内に判定結果を表示
- **WSI不要・低コスト運用**：高価なスキャナーやGPUを必要としません
- **階層ラベル学習による高精度判定**：異常、悪性、ベセスダ分類、診断まで対応
- **LLM（大規模言語モデル）による所見生成（オプション）**

詳細は論文をご参照ください：  
[🔗 Whole Slide Imaging-Free Supporting Tool for Cytotechnologists in Cervical Cytology (Modern Pathology 2025)](https://doi.org/10.1016/j.modpat.2025.100817)

下図は実際の研究で使用した画像例です：
<div align="center">
  <img src="/assets/sample_study_image.png" alt="Example Study Image" width="60%">
</div>

<br>

<div align="center">
  <img src="/assets/cytolone_app.png" alt="CYTOLONE App Image" width="100%">
</div>

## 🤩 アップデート履歴
- **2025年7月10日**
  - CYTOLONE-v1.1 をリリース！
  - v1.0 と比較して、特に Bethesda／Diagnosis タスクの性能を向上
  - 詳細は Model Card をご覧ください：https://huggingface.co/kuri54/mlx-CYTOLONE-v1.1

- **2025年7月3日**
  - セットアップ関係をアップデート
  - uvのスクリプト実行に対応

- **2025年6月13日**
  - ページを公開しました
  - 論文が *Modern Pathology* に掲載されました


## 💡使用方法
- このライブラリは**Apple Silicon MacとiPhoneのみ**に最適化されています。
- Windowsやその他のOSは対応していません。その他のカメラデバイスは未検証です。

### 💻 セットアップ
0. **事前準備**
    - Apple Silicon MacとiPhoneを用意し、同一のApple IDでログインする。  
    - MacとiPhoneをUSB-Cケーブル（もしくはThunderboltケーブル）で接続する。  
      📝 Note:  
      > Bluetoothでも接続が可能ですが、有線接続の方が安定するためおすすめです  
    - iPhoneと顕微鏡をアダプターで接続する。

<div align="center">
  <img src="/assets/setup.png" alt="Setup" width="80%">
</div>

1. **Pythonのインストール**

    📢 Important:  
    > MacにはPythonが標準でインストールされていますが、バージョンが古いため本アプリで使用する主要なライブラリの最新バージョンがインストールできません。  
    > **Python3.12**をインストールしてください。

    <br>

    ```bash
    brew install python@3.12
    ```

    **For [uv](https://github.com/astral-sh/uv) users:**
    ```bash
    uv python install 3.12
    ```

2. **Installation**:
    - リポジトリをcloneする
     
    - cloneしたディレクトリに移動
      ```bash
      cd CYTOLONE
      ```

    📝 Note:
    > **For uv users:**
    このセクションは不要です。`uv sync`で依存関係をインストール後、次のステップ3へ進んでください。

    <br>

    - 仮想環境の構築
        ```bash
        python3.12 -m venv venv
        source venv/bin/activate
        ```

        📝 Note:  
        > 以降の作業は全てこの仮想環境内で実行する  

    <br>

    - 必要なライブラリをインストールする
      ```bash
      pip install -e .
      ```



3. **アプリの設定**
    - デフォルト設定
        ```
        LANGUAGE = en --------------- アプリの言語設定 (en or ja)
        MODEL = v1.1 ---------------- 使用するモデルのバージョン（v1.0 または v1.1）
        LLM_GEN = False ------------- LLMによる鑑別所見出力の有無
        LLM_GEN_THRESHOLD = 0.8 ----- LLM出力を有効にする閾値
        WEBCAM_IMAGE_SIZE = 1024 ---- webcam入力画像サイズ
        ```

    - 設定変更方法
        - 設定一覧を表示: 
          ```bash
          cytolone-config --list
          ```

        - アプリの言語を日本語にする: 
          ```bash
          cytolone-config --LANGUAGE ja
          ```

        - 設定をデフォルトに戻す: 
          ```bash
          cytolone-config --reset
          ```

          ⚠️ Warning:  
          `LLM_GEN`を`True`にする場合は、Macが少なくとも**64GB以上のユニファイドメモリ**を搭載している場合のみにしてください。メモリが少ない場合はMacがクラッシュします。

      - `WEBCAM_IMAGE_SIZE`  
         📢 Important:  
         > `WEBCAM_IMAGE_SIZE`はこのアプリで最も重要な設定です。  
         > 設定方法は[こちらの手順](/CYTOLONE/scale_check/README_JA.md)を確認してください。  

    <br>

    - モデルのダウンロード
      ```bash
      download-model
      ```
      - 自動的に必要なモデルがダウンロードされます。  
      - `LLM_GEN`が`False`の場合、言語モデルはダウンロードされません。LLM機能を利用したい場合は、設定変更後に再実行してください。  

      ⚠️ Warning:  
      > `download-model`実行時は**ネット接続が必要**です。  
      > オフライン環境の場合は、一時的にネットワークに繋げるか、別のネットワークに繋がったPCで以下のリンクからモデルをダウンロードし、指定のディレクトリに配置してください。

        リンク:   
        [kuri54/mlx-CYTOLONE-v1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1)  
        [mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit](https://huggingface.co/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit)

        配置:  
        ```
        CYTOLONE/mlx-models/kuri54/mlx-CYTOLONE-v1/  
        CYTOLONE/mlx-models/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit/
        ```

### 🚀 アプリの起動
- 起動
    ```bash
    cytolone
    ```
    - ターミナルに表示されたアドレスにWebブラウザでアクセスする。  
    - カメラ選択 → 写真撮影 → **Analyze ボタンをクリック** するだけで判定結果が表示されます。

    <br>

    📝 Note:  
    > オフラインでも利用可能です！  

<br>

- カメラの連携  
赤丸部分をクリックしてiPhoneと連携してください。  
<div align="center">
  <img src="/assets/webcam.png" alt="Webcam" width="60%">
</div>

<br>

💡 Tip:  
> 内蔵カメラに自分の顔が映る場合がありますが、iPhoneを選択すれば解決します。

<br>

⚠️ Warning:  
> 写真を撮る際の対物レンズは必ず×10にしてください。それ以外の倍率には対応していません。  

## 🔭 今後の開発計画
以下の機能を今後のアップデートで追加予定です：

- **赤丸による注視領域の指定機能**  
  画像上の任意の部位に赤丸をつけることで、モデルがその領域に注目して判定を行います。  
  _参考論文_: [What does CLIP know about a red circle? Visual prompt engineering for VLMs](https://arxiv.org/pdf/2304.06712)

- **スクリーニングモード**  
  このモードをONにすると、顕微鏡観察中に常時「Anomaly」カテゴリの判定を自動実行します。  

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
