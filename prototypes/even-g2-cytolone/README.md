# CYTOLONE × Even G2 プロトタイプ

Even Realities公式のEven Hub SDKとEven Hub Simulatorを使い、未購入のG2/R1だけを置き換える購入説明用デモです。画像入力とCLIP ViT-B/16推論は、Mac上の実際のCYTOLONEを使用します。

```text
顕微鏡＋CマウントiPhone / インポート画像
                    ↓ 現在視野
             Mac上のCYTOLONE
             実CLIP ViT-B/16推論
                    ↓ 判定ラベル＋確率
        公式Even Hub Simulator（G2代用）
                    ↑
          Simulator操作（R1代用）
```

仕様の確定内容は[DESIGN.md](./DESIGN.md)を参照してください。

## 実装済み

- CYTOLONE Mainに`External output: None / Even G2`を追加
- CYTOLONE Mainに検体選択を追加（現在は`cervix`のみ）
- G2側からAnomaly / Malignancy / Bethesda / Diagnosisを選択し、Macへ同期
- `Full`はMac側に残し、G2側の選択肢から除外
- インポート済み画像をSimulatorのClickで実際にCLIP推論
- iPhoneカメラ接続中は、SimulatorのClickごとにブラウザの現在フレームを取得して推論
- 判定ラベルを確率順で全件表示（先頭3件以上を即時表示し、残りはスクロール）
- LLM生成結果、鑑別所見、画像、患者識別情報はG2 APIへ出力しない
- `External output=None`ではG2 Analyze要求を拒否

フットペダル、尿モデル、実機G2/R1は今回の範囲外です。将来のR1/ペダル入力は同じAnalyze命令へ接続します。

## 必要環境

- macOS
- CYTOLONEを通常起動できるPython環境
- Node.js `^20.0.0 || >=22.0.0`
- npm

主要な公式依存は再現性のため固定しています。

- `@evenrealities/even_hub_sdk`: `0.0.12`
- `@evenrealities/evenhub-simulator`: `0.8.0`

## 起動

ターミナル1でCYTOLONEを起動します。

```bash
cd /Users/Kurita/Desktop/CYTOLONE
uv run cytolone
```

ターミナル2で公式Simulatorを起動します。

```bash
cd /Users/Kurita/Desktop/CYTOLONE/prototypes/even-g2-cytolone
npm install
npm run demo
```

使用するローカルポートは次の通りです。

- CYTOLONE UI: `http://127.0.0.1:7860`
- CYTOLONE hands-free API: `http://127.0.0.1:8765`
- G2 SDKホスト（表示・操作画面なし）: `http://127.0.0.1:5173`
- Simulator自動操作API: `http://127.0.0.1:9898`

## 購入説明用デモ

デモ画像には`/Users/Kurita/Downloads/Ad002_16.jpg`を使用します。

1. CYTOLONE Mainで画像をインポートする。
2. `External output`を`Even G2`へ変更する。
3. Simulatorで`MODE`をClickし、候補一覧からQuestion Typeを選んでClickで確定する。
4. Mac側のQuestion Typeが同期することを見せる。
5. Simulatorの`ANALYZE`でClickする。
6. Mac上で実CLIP推論が走り、MacとG2に同じ判定結果が出ることを見せる。
7. G2の先頭3ラベルを確認し、Downで残りのラベルも表示する。
8. Double clickで待機画面へ戻る。

この画像をBethesdaで検証した際の実行例は`ADC 99.7% / SCC 0.2% / HSIL 0.1% / NILM 0.0% / LSIL 0.0%`でした。これはデモ時のモデル出力であり、臨床診断を示すものではありません。

## Simulator自動操作

```bash
curl http://127.0.0.1:9898/api/ping
curl -X POST http://127.0.0.1:9898/api/input \
  -H 'Content-Type: application/json' \
  -d '{"action":"click"}'
curl http://127.0.0.1:9898/api/screenshot/glasses --output glasses.png
```

Simulator上の基本操作は次の通りです。

- Up / Down: メニュー移動、候補選択、結果スクロール
- Click: Analyze、サブメニューを開く、候補を確定する
- Double click: 候補選択をキャンセル、または結果を閉じて待機画面へ戻る

Simulatorでは、行を移動する入力と項目を実行するClickが別イベントになる場合があります。選択行へ移動後、もう一度Clickしてください。

Viteのページは公式SimulatorへG2アプリを供給する技術的なホストとしてのみ動作します。プレゼン用のWeb画面は持たず、操作はCYTOLONEと公式Simulatorだけで完結します。

## 検証

```bash
cd /Users/Kurita/Desktop/CYTOLONE
uv run python -m unittest discover -s tests -v

cd /Users/Kurita/Desktop/CYTOLONE/prototypes/even-g2-cytolone
npm run build
npm audit
```

現時点の`npm audit`には、Windows上の開発サーバーだけに該当するesbuildのlow severity 1件が残ります。このデモはmacOSかつlocalhost限定で動作します。

## 実機購入後に必要な検証

Simulatorで検証済みなのは表示レイアウト、R1相当イベント、Macとのlocalhost通信です。実機購入後は次を別途確認します。

1. Even Hubアプリをパッケージ化してG2へ導入する。
2. R1実機のClick / Up / Down / Double clickを確認する。
3. スマートフォンからMacへ接続するLAN通信、認証、再接続を実装する。
4. iPhoneの現在フレーム取得が実機G2/R1経由でも同じタイミングで動くことを確認する。
5. 顕微鏡接眼部との物理干渉、焦点、視認性、操作疲労を評価する。

Simulatorの表示と実機のフォント・光学的な見え方が一致するとは限らないため、購入後の実機検証は省略できません。

## 公式パッケージ

- [Even Hub SDK](https://www.npmjs.com/package/@evenrealities/even_hub_sdk)
- [Even Hub Simulator](https://www.npmjs.com/package/@evenrealities/evenhub-simulator)
