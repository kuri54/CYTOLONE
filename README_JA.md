<div align="center">
<picture>
  <img alt="cytolone logo" src="/assets/cytolone_logo.jpg" width="80%" height="80%">
</picture>

_**"Always by you side."**_

</div>

<br>

|[English](./README.md)|

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

### 📦 macOSアプリのインストール
通常利用では、GitHub Releases から Apple Silicon 用 DMG を取得してください。

```text
CYTOLONE-<version>-mac-arm64.dmg
```

1. [GitHub Releases ページ](https://github.com/kuri54/CYTOLONE/releases)を開きます。
2. `.dmg` をダウンロードし、`CYTOLONE.app` を `Applications` にドラッグします。
3. `CYTOLONE.app` をダブルクリックします。

Apple Silicon Mac の macOS 13 以降に対応しています。

### 🚀 初回起動と2回目以降
初回起動時は、文字と進捗だけのシンプルな英語ネイティブセットアップ画面が
表示されます。CYTOLONEの実行に必要な環境を準備し、完了後に既定のブラウザで
CYTOLONE画面を開きます。モデルの取得は CYTOLONE ランチャーから行う
別操作です。

2回目以降は準備済みの環境を再利用します。CYTOLONE がすでに起動している場合に
アプリを再度起動しても、サーバーを二重に起動せず、既存のCYTOLONE画面を開きます。
セットアップとモデル取得が完了した後は、オフラインで利用できます。

最初に CYTOLONE ランチャー画面が開きます。ランチャーから CYTOLONE Main、
scale-check、Settings、Model Download を開けます。ナビゲーションバーには
Launcher タブだけが表示されます。各ページへはランチャー内のボタンから移動し、
**CYTOLONE Main** でカメラを選択して **Analyze** を押すと現在の視野を判定できます。

### 🔄 更新・終了・削除
更新する場合は、新しい DMG を取得し、既存の `CYTOLONE.app` を新しいアプリに
置き換えてください。ダウンロード済みのモデルと設定は保持されます。

ブラウザのタブを閉じても CYTOLONE は停止しません。終了する場合は Dock の
CYTOLONE アイコンを右クリックして **Quit** を選択してください。

通常のアプリ本体だけの削除では、まず Dock の CYTOLONE アイコンを右クリックして
**Quit** を選び、その後 `CYTOLONE.app` をゴミ箱へ移してください。管理データは保持
されます。

完全削除では、CYTOLONE を起動した状態で Dock の CYTOLONE アイコンを右クリックし、
**Remove CYTOLONE Data…** を選んで確認を完了してください。削除が完了した後、
`CYTOLONE.app` をゴミ箱へ移してください。

セットアップを完了できない場合は、ネイティブ画面の **Retry Setup** を選び、Mac が
インターネットに接続されていることを確認して再試行してください。解決しない場合は
CYTOLONE を終了し、時間を置いて再度起動してください。

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

CYTOLONE ランチャーから **Settings** を開いて設定を変更できます。

⚠️ Warning:
> `LLM_GEN` を `True` にする場合は、Mac が少なくとも **64GB 以上のユニファイドメモリ**を搭載している場合のみにしてください。メモリが少ない場合は Mac がクラッシュする可能性があります。

`WEBCAM_IMAGE_SIZE` はこのアプリで最も重要な設定です。設定方法は[こちらの手順](/CYTOLONE/scale_check/README_JA.md)を確認してください。

### ⬇️ モデルのダウンロード
CYTOLONE ランチャーから **Model Download** を開いてモデルをダウンロードできます。

すでにインストール済みのモデルは自動的にスキップされます。再ダウンロードしたい場合のみ **Force re-download** を使用してください。

自動的に必要なモデルがダウンロードされます。`LLM_GEN` が `False` の場合、言語モデルはダウンロードされません。LLM 機能を利用したい場合は、設定変更後に再度ダウンロードしてください。

⚠️ Warning:
> モデルのダウンロードには**ネット接続が必要**です。
### 🌐 ネットワークとオフライン利用
DMG の取得、アプリの初回セットアップ、モデルのダウンロードにはネットワークが
必要です。CYTOLONE はバックグラウンド更新確認を行わず、Tailscale、Taildrive、
Owlfile、ネットワーク共有の設定を変更しません。

セットアップとモデル取得が完了した後は、オフラインで利用できます。

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
