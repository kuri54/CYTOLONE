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

## 💡 使用方法
- このライブラリは**Apple Silicon MacとiPhoneのみ**に最適化されています。
- Windowsやその他のOSは対応していません。その他のカメラデバイスは未検証です。

### 💻 事前準備
1. Apple Silicon Mac と iPhone を用意し、同一の Apple ID でログインします。
2. Mac と iPhone を USB-C ケーブル、または Thunderbolt ケーブルで接続します。
3. iPhone と顕微鏡をアダプターで接続します。

📝 Note:
> Bluetooth でも接続できますが、安定性のため有線接続を推奨します。

<div align="center">
  <img src="/assets/setup.png" alt="Setup" width="80%">
</div>

### 📦 推奨インストール: GitHub Releases パッケージ
通常利用ではこの方法を推奨します。Git clone、Homebrew、alias の設定は不要です。

1. [GitHub Releases ページ](https://github.com/kuri54/CYTOLONE/releases)を開きます。
2. macOS Apple Silicon 用パッケージをダウンロードします。
   ```text
   CYTOLONE-<version>-mac-arm64.tar.gz
   ```
3. ダウンロードした `.tar.gz` をダブルクリックして展開します。
4. 展開されたフォルダを開き、次のファイルをダブルクリックします。
   ```text
   install.command
   ```
5. インストール完了後、必要に応じて Terminal を再起動します。
6. Terminal で次のコマンドを実行して起動します。
   ```bash
   cytolone
   ```

インストーラは CYTOLONE を次の場所に配置します。
```text
~/.local/share/cytolone/current
```

また、次の起動用ラッパーを作成します。
```text
~/.local/bin/cytolone
```

`uv` がすでにインストールされている場合、インストーラは既存の `uv` をそのまま使用します。`uv` がない場合のみ、公式の `uv` インストーラで導入します。Homebrew は使用しません。

uv の仮想環境は通常、次の場所に作成されます。
```text
~/.local/share/cytolone/current/.venv
```

アンインストールする場合は、次のファイルをダブルクリックします。
```text
uninstall.command
```

`uninstall.command` は CYTOLONE の配置先と `~/.local/bin/cytolone` だけを削除します。`uv` 本体、`uv` がインストールした Python、`uv` cache は削除しません。

### 🛠 開発者向け / ソースからのインストール
clone したソースツリーから CYTOLONE を実行したい場合はこちらを使用してください。

1. Python 3.12 をインストールします。

   Mac には Python が標準でインストールされていますが、バージョンが古いため本アプリで使用する主要なライブラリを利用できません。

   ```bash
   brew install python@3.12
   ```

   [uv](https://github.com/astral-sh/uv) を使う場合:
   ```bash
   uv python install 3.12
   ```

2. リポジトリを clone し、ディレクトリに移動します。
   ```bash
   git clone https://github.com/kuri54/CYTOLONE.git
   cd CYTOLONE
   ```

3. 依存関係をインストールします。

   `uv` を使う場合:
   ```bash
   uv sync
   ```

   `venv` と `pip` を使う場合:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate
   pip install -e .
   ```

4. ソースツリーから起動します。
   ```bash
   uv run cytolone
   ```

### ⚙️ アプリの設定
デフォルト設定:
```text
LANGUAGE = en --------------- アプリの言語設定 (en or ja)
MODEL = v1.1 ---------------- 使用するモデルのバージョン（v1.0 または v1.1）
LLM_MODEL = gpt-oss-20b ----- 使用するLLM (deepseek-r1 or gpt-oss-120b or gpt-oss-20b)
LLM_GEN = False ------------- LLMによる鑑別所見出力の有無
LLM_GEN_THRESHOLD = 0.8 ----- LLM出力を有効にする閾値
WEBCAM_IMAGE_SIZE = 1024 ---- webcam入力画像サイズ
```

ランチャーから設定を変更できます。`cytolone` または `uv run cytolone` を実行し、**Settings** を開いてください。

CLI コマンドも引き続き利用できます。
```bash
cytolone-config --list
cytolone-config --LANGUAGE ja
cytolone-config --reset
```

⚠️ Warning:
> `LLM_GEN` を `True` にする場合は、Mac が少なくとも **64GB 以上のユニファイドメモリ**を搭載している場合のみにしてください。メモリが少ない場合は Mac がクラッシュする可能性があります。

`WEBCAM_IMAGE_SIZE` はこのアプリで最も重要な設定です。設定方法は[こちらの手順](/CYTOLONE/scale_check/README_JA.md)を確認してください。

### ⬇️ モデルのダウンロード
ランチャーからモデルをダウンロードできます。`cytolone` または `uv run cytolone` を実行し、**Model Download** を開いてください。

すでにインストール済みのモデルは自動的にスキップされます。再ダウンロードしたい場合のみ **Force re-download** を使用してください。

CLI コマンドも引き続き利用できます。
```bash
download-model
```

自動的に必要なモデルがダウンロードされます。`LLM_GEN` が `False` の場合、言語モデルはダウンロードされません。LLM 機能を利用したい場合は、設定変更後に再度ダウンロードしてください。

⚠️ Warning:
> モデルのダウンロードには**ネット接続が必要**です。
> オフライン環境の場合は、一時的にネットワークに繋げるか、別のネットワークに繋がった PC で以下のリンクからモデルをダウンロードし、指定のディレクトリに配置してください。

リンク:
[kuri54/mlx-CYTOLONE-v1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1)
[kuri54/mlx-CYTOLONE-v1.1](https://huggingface.co/kuri54/mlx-CYTOLONE-v1.1)
[mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit](https://huggingface.co/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit)
[mlx-community/gpt-oss-120b-MXFP4-Q4](https://huggingface.co/mlx-community/gpt-oss-120b-MXFP4-Q4)
[mlx-community/gpt-oss-20b-MXFP4-Q8](https://huggingface.co/mlx-community/gpt-oss-20b-MXFP4-Q8)

配置:
```text
CYTOLONE/mlx-models/kuri54/mlx-CYTOLONE-v1/
CYTOLONE/mlx-models/mlx-community/DeepSeek-R1-Distill-Qwen-32B-Japanese-8bit/
```

### 🚀 アプリの起動
パッケージ利用者:
```bash
cytolone
```

インストール先で直接起動する場合:
```bash
cd ~/.local/share/cytolone/current
uv run cytolone
```

ソースツリーから起動する場合:
```bash
uv run cytolone
```

- 最初に CYTOLONE ランチャー画面が開きます。
- ランチャーから CYTOLONE Main、scale-check、Settings、Model Download を開けます。
- ナビゲーションバーには Launcher タブだけが表示されます。各ページへはランチャー内のボタンから移動してください。
- ターミナルに表示されたアドレスに Web ブラウザでアクセスしてください。
- **CYTOLONE Main** を押すと、従来の解析画面が開きます。
- カメラを選択し、**Analyze** ボタンをクリックすると現在の視野を判定できます。

📝 Note:
> 依存関係とモデルの準備が完了した後は、オフラインでも利用可能です。

### 🌐 ネットワークとストレージに関する注意
- GitHub Releases から `.tar.gz` を取得する時にネットワークを使用します。
- `install.command` は `uv` が未インストールの場合のみネットワークを使用します。
- 初回 `cytolone` 起動時に、`uv` が Python パッケージを取得するためネットワークを使用する場合があります。
- モデルのダウンロードにはネットワークを使用し、ディスク容量も大きくなる場合があります。
- CYTOLONE は Tailscale、Taildrive、Owlfile、ネットワーク共有設定を変更しません。
- ホームディレクトリを別ツールで同期・共有している場合、`~/.local/share/cytolone/current/.venv` やダウンロード済みモデルの容量に注意してください。
- トップレベルの `assets/` は GitHub README 表示用であり、release パッケージの実行には不要です。

### 📷 カメラの連携
赤丸部分をクリックしてiPhoneと連携してください。
<div align="center">
  <img src="/assets/webcam.png" alt="Webcam" width="60%">
</div>

<br>

💡 Tip:
> 内蔵カメラに自分の顔が映る場合は、一度 iPhone を選択してください。CYTOLONE はブラウザにその iPhone を記憶し、次回以降は自動再接続を試みます。
> iPhone カメラ接続時にセンターフレームが有効になる場合は、Mac のメニューバーのビデオメニュー、またはコントロールセンター > ビデオエフェクトからセンターフレームをOFFにしてください。これは CYTOLONE ではなく macOS の連係カメラ設定です。

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
