<div align="center">
<picture>
  <img alt="cytolone logo" src="/assets/cytolone_logo.jpg" width="80%" height="80%">
</picture>

_**"Always by you side."**_

</div>

<br>

|[English](./README.md)|

## ✨ 概要
**CYTOLONE** (Cytology All-in-One) は、顕微鏡とAIをリアルタイムで連携させることで、**細胞検査士による子宮頸部・尿細胞診を支援するツール**です。
従来のAI支援システムで必要とされていた**WSI（全スライド画像）作成を不要**とし、iPhoneとApple Silicon Macだけで運用可能な低コスト・高速AI支援を実現しました。

主な特徴:
- **リアルタイムの顕微鏡連携**：現在のカメラ視野を判定
- **WSI不要・低コスト運用**：高価なスキャナーやGPUを必要としません
- **検体別の階層分類**：子宮頸部・尿を選択し、共通のv2分類モデルを使用
- **子宮頸部細胞診向けのローカルLLM（大規模言語モデル）による補助情報（オプション）**
- **尿の判定に迷ったときの固定確認フロー**

詳細は論文をご参照ください：

- [Whole Slide Imaging-Free Supporting Tool for Cytotechnologists in Cervical Cytology (Modern Pathology 2025)](https://doi.org/10.1016/j.modpat.2025.100817)
- [A WSI-Independent Inference Framework for Cervical and Urinary Cytology Using Hierarchical Labels (Cytopathology 2026)](https://doi.org/10.1111/cyt.70140)

<div align="center">
  <img src="/assets/sample_study_image.png" alt="Example Study Image" width="60%">
</div>

<br>

<div align="center">
  <img src="/assets/cytolone_app.png" alt="CYTOLONE App Image" width="100%">
</div>

<br>

## 💡 使用方法
- このライブラリは**Apple Silicon MacとiPhoneのみ**に最適化されています。
- Windowsやその他のOSは対応していません。その他のカメラデバイスは未検証です。

<br>

### 💻 事前準備
1. Apple Silicon Mac と iPhone を用意し、同一の Apple ID でログインします。
2. Mac と iPhone を USB-C ケーブル、または Thunderbolt ケーブルで接続します。
3. iPhone と顕微鏡をアダプターで接続します。

📝 Note:
> Bluetooth でも接続できますが、安定性のため有線接続を推奨します。

<div align="center">
  <img src="/assets/setup.png" alt="Setup" width="80%">
</div>

<br>

### 📦 macOSアプリのインストール
通常利用では、GitHub Releases から Apple Silicon 用 DMG を取得してください。

```text
CYTOLONE-<version>-mac-arm64.dmg
```

1. [GitHub Releases ページ](https://github.com/kuri54/CYTOLONE/releases)を開きます。
2. `.dmg` をダウンロードし、`CYTOLONE.app` を `Applications` にドラッグします。
3. `CYTOLONE.app` をダブルクリックします。

Apple Silicon Mac の macOS 13 以降に対応しています。

現在の CYTOLONE は Apple Developer ID による署名・公証を行わずに配布しています。
初回起動時に「Appleは、CYTOLONE.appにMacに損害を与えたり、プライバシーを侵害する
可能性のあるマルウェアが含まれていないことを検証できませんでした」と表示される場合が
あります。公式の CYTOLONE GitHub Releases からDMGを取得した場合は、次の手順で
初回起動を許可してください。

1. `CYTOLONE.app` を一度開き、表示された警告を閉じます。
2. **システム設定 > プライバシーとセキュリティ**を開きます。
3. **セキュリティ**までスクロールし、CYTOLONEの**このまま開く**を選びます。
4. もう一度**このまま開く**を選んで確認します。

この許可操作が必要なのは初回だけです。詳しくは
[Appleの「開発元が不明なMacアプリを開く」](https://support.apple.com/ja-jp/guide/mac-help/-mh40616/mac)
を確認してください。

<br>

### 🚀 初回起動と2回目以降
初回起動時は、文字と進捗だけのシンプルな英語ネイティブセットアップ画面が
表示されます。CYTOLONEの実行に必要な環境を準備し、完了後に既定のブラウザで
CYTOLONE画面を開きます。モデルの取得は CYTOLONE ランチャーから行う
別操作です。

2回目以降は準備済みの環境を再利用します。CYTOLONE がすでに起動している場合に
アプリを再度起動しても、サーバーを二重に起動せず、既存のCYTOLONE画面を開きます。
セットアップとモデル取得が完了した後は、オフラインで利用できます。

最初に CYTOLONE ランチャー画面が開きます。ランチャーから CYTOLONE Main、
scale-check、Settings、Model Management を開けます。ナビゲーションバーには
Launcher タブだけが表示されます。各ページへはランチャー内のボタンから移動し、
**CYTOLONE Main** でラジオボタンから **子宮頸部** または **尿** を選択し、
カメラを選択して **Analyze** を押すと現在の視野を判定できます。

<br>

### 🔬 検体と分類カテゴリ
両検体で共通のv2分類モデルを使用し、検体に応じた階層ラベルで判定します。

- **子宮頸部**（初期選択）：Full、Anomaly、Malignancy、System（ベセスダ分類）、Diagnosis。
- **尿**：Full、Anomaly、Malignancy、Diagnosis。Systemカテゴリはありません。

尿ではLLM生成を無効にしています。**判定に迷ったとき** を押すと参考文献付きの
固定確認フローが開きます。

<br>

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

<br>

### ⚙️ 設定
ランチャーの **Settings** では、アプリモデルはv2を使用し、使用するLLMモデル、言語、
webcam画像サイズを選択できます。
LLM出力は任意で、**子宮頸部のみ**利用できます。**CYTOLONE Main** で判定結果が条件を
満たした場合に、簡潔な鑑別所見または詳細な鑑別所見を選びます。

次の2種類から選べます。

- **簡潔な鑑別所見**：細胞形態学的な鑑別所見のみを4項目で生成し、比較的短時間で出力します。
- **詳細な鑑別所見**：同じ形態鑑別に加え、鑑別のために確認すべき臨床情報と、鑑別に役立つ可能性のある追加検査を生成するため、簡潔版より時間がかかります。

どちらもLLMへ画像を渡さず、分類器の上位2つの正規化済み判定ラベルだけを補助情報として使います。
最終診断ではありません。

`WEBCAM_IMAGE_SIZE` はこのアプリで最も重要な設定です。設定方法は[こちらの手順](/CYTOLONE/scale_check/README_JA.md)を確認してください。

<br>

### ⬇️ モデル管理
ランチャーの **Model Management** を開くと、利用可能なアプリモデルとLLMを
一覧で確認できます。選択状態、インストール状態、ローカル容量、ダウンロード容量、
メモリ目安が表示されます。

両検体の分類モデルは `v2`（`kuri54/mlx-CYTOLONE-v2`）です。
CYTOLONE v2では、既存のv1.0 / v1.1分類モデルは削除のみ可能で、使用・新規ダウンロード・
再ダウンロードはできません。旧モデルの利用には、対応する **CYTOLONE 1.1.xアプリ** が必要です。
この制限は、下記のLegacy LLMには適用されません。

推奨LLMは Qwen3.5-27B-5bit です。使用するLLMモデルは **Settings** で選択し、
アプリモデルとLLMのダウンロード・削除は **Model Management** で行います。

LLM生成はユニファイドメモリ64GB以上のMacを推奨します。64GB未満では、生成が遅い、swapや
不安定化が起きる、またはモデルが収まらない可能性があります。

利用可能なLLM:

| キー | リポジトリ | ダウンロード容量 | ユニファイドメモリ目安 |
|---|---|---:|---:|
| `qwen3.5-27b-5bit`（推奨メイン） | `mlx-community/Qwen3.5-27B-5bit` | 19.4 GB | 64 GB以上 |
| `gpt-oss-120b`（Legacy） | `mlx-community/gpt-oss-120b-MXFP4-Q4` | 約63 GB | 128 GB以上 |
| `gpt-oss-20b`（Legacy互換） | `mlx-community/gpt-oss-20b-MXFP4-Q8` | 12.1 GB | 64 GB以上 |

上記の容量とメモリ値は検証済みの最低条件ではなく、暫定的な選択目安です。対象Macで選択モデルを
確認してから生成してください。

v2アプリモデルまたはLLMを1つ選び、それぞれの **Download** を押してください。
削除する場合は対象を選び、**Delete** を押して表示されたモデルを確認してください。全モデル削除の
操作はありません。
削除してもSettingsは変更されないため、v2または選択したLLMを再利用する場合は再ダウンロード
してください。旧分類モデルはこのアプリでは再ダウンロードできません。

モデルのダウンロードにはインターネット接続が必要です。必要なモデルの準備後は、
ローカル・オフラインで利用できます。

<br>

### 🌐 ネットワークとオフライン利用
DMGの取得、アプリの初回セットアップ、モデルのダウンロードにはネットワークが必要です。
CYTOLONEはバックグラウンド更新確認やネットワーク共有設定の変更を行いません。

LLMの出力は鑑別所見を補助する情報であり、最終診断ではありません。

<br>

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

<br>

## 🎉 Citation
初版の子宮頸部細胞診に関する研究は、以下の論文で報告しています。

```
@article{kurita2025cytolone,
         title={Whole Slide Imaging-Free Supporting Tool for Cytotechnologists in Cervical Cytology},
         author={Yuki Kurita et al.},
         year={2025},
         journal={Modern Pathology},
         doi={10.1016/j.modpat.2025.100817}
}
```

v2の子宮頸部・尿細胞診に関する研究は、[A WSI-Independent Inference Framework for Cervical and Urinary Cytology Using Hierarchical Labels](https://doi.org/10.1111/cyt.70140)です。
2026年10月20日に *Cytopathology* でオンライン公開されました。

```
@article{kurita_cytolone_v2,
         title={A WSI-Independent Inference Framework for Cervical and Urinary Cytology Using Hierarchical Labels},
         author={Kurita, Yuki and Meguro, Shiori and Enomoto, Yasunori and Kawasaki, Hideya and Saitoh, Takeji and Suzuki, Makoto and Sakane, Junichi and Suzuki, Daisuke and Ishidou, Osamu and Shinmura, Kazuya and Iwashita, Toshihide},
         year={2026},
         journal={Cytopathology},
         doi={10.1111/cyt.70140},
         note={First published online October 20, 2026}
}
```
