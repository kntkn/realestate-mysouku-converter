# 不動産マイソク自動変換システム

レインズでダウンロードしたマイソクPDFを、弊社仕様のマイソクPDFに自動変換するWebアプリケーションです。

## 機能概要

- **PDFアップロード**: レインズのマイソクPDFをドラッグ&ドロップで簡単アップロード
- **自動データ抽出**: PDF内のテキストを自動解析、物件情報を構造化データとして抽出
- **OCR対応**: 画像化されたPDFでもOCR技術で文字認識
- **データ編集**: 抽出されたデータの確認・修正が可能
- **会社情報設定**: 自社の会社情報（ロゴ、連絡先等）を事前設定
- **マイソク生成**: 弊社仕様のレイアウトでPDF自動生成
- **即時ダウンロード**: 生成されたマイソクをその場でダウンロード

## システム構成

```
realestate-mysouku-converter/
├── app.py                   # Flaskメインアプリケーション
├── run.py                   # 起動スクリプト
├── requirements.txt         # 依存ライブラリ
├── models/
│   └── company.py          # 会社情報データベースモデル
├── utils/
│   ├── pdf_analyzer.py     # PDF解析・OCR機能
│   └── template_generator.py # マイソクテンプレート生成
├── templates/              # HTMLテンプレート
│   ├── base.html
│   ├── index.html
│   └── company_settings.html
├── static/
│   ├── css/
│   │   └── style.css       # カスタムCSS
│   ├── js/
│   │   ├── main.js         # 共通JavaScript
│   │   ├── upload.js       # PDF処理用JS
│   │   └── company.js      # 会社設定用JS
│   ├── uploads/            # アップロードファイル保存
│   └── generated/          # 生成PDFファイル保存
└── company.db              # SQLiteデータベース（自動作成）
```

## 技術スタック

- **バックエンド**: Flask (Python)
- **PDF処理**: PyPDF2, pdfplumber
- **OCR**: Tesseract + pytesseract
- **PDF生成**: ReportLab
- **フロントエンド**: HTML5, CSS3, JavaScript, Bootstrap 5
- **データベース**: SQLite
- **画像処理**: Pillow, OpenCV

## インストール・セットアップ

### 1. 必要なソフトウェア

```bash
# Python 3.8以上が必要
python3 --version

# Tesseract OCRエンジンのインストール（macOS）
brew install tesseract
brew install tesseract-lang  # 日本語サポート

# Tesseract OCRエンジンのインストール（Ubuntu）
sudo apt-get install tesseract-ocr tesseract-ocr-jpn

# Tesseract OCRエンジンのインストール（Windows）
# https://github.com/UB-Mannheim/tesseract/wiki からダウンロード
```

### 2. ライブラリのインストール

```bash
cd realestate-mysouku-converter
pip install -r requirements.txt
```

### 3. アプリケーション起動

```bash
python3 run.py
```

または

```bash
./run.py
```

### 4. アクセス

ブラウザで以下にアクセス：
```
http://localhost:5000
```

## 使用方法

### 1. 初回設定

1. アプリケーション起動後、「会社情報設定」にアクセス
2. 必須項目を入力：
   - 会社名
   - 住所  
   - 電話番号
   - 宅建業免許番号
3. オプション項目：
   - 会社ロゴ（PNG/JPG、2MB以下）
   - FAX、メール、ウェブサイト等
4. 「保存」ボタンで設定完了

### 2. マイソク変換

1. メインページでレインズのマイソクPDFをアップロード
2. 自動解析結果の確認・必要に応じて修正
3. 「マイソクPDF生成」ボタンをクリック
4. 生成完了後、PDFをダウンロード

## 対応データ項目

以下の物件情報を自動抽出・変換します：

- 物件種別（マンション、アパート、戸建て、土地等）
- 取引種別（賃貸・売買）
- 価格・賃料
- 所在地
- 交通アクセス
- 間取り
- 建物面積・土地面積
- 築年数
- 構造
- 駐車場情報
- 設備・特徴

## トラブルシューティング

### PDFが読み込めない場合

1. ファイルサイズが16MB以下か確認
2. PDF形式が正しいか確認  
3. パスワード保護されていないか確認

### OCRが正しく動作しない場合

```bash
# Tesseractの確認
tesseract --version

# 日本語パックの確認
tesseract --list-langs
```

### データベースエラーの場合

```bash
# データベースファイルを削除（設定がリセットされます）
rm company.db
```

## カスタマイズ

### マイソクレイアウトの変更

`utils/template_generator.py` の `MysoukuTemplateGenerator` クラスを編集してください。

### 抽出項目の追加

`utils/pdf_analyzer.py` の `_parse_mysouku_data` メソッドに新しいパターンマッチングを追加してください。

### デザインの変更

- CSS: `static/css/style.css`
- HTML: `templates/` フォルダ内のファイル

## セキュリティ

- アップロードファイルは一時的にサーバーに保存（処理後自動削除推奨）
- 機密情報は暗号化してデータベースに保存
- 本番環境では適切なアクセス制御を設定してください

## ライセンス

このソフトウェアは不動産業務効率化を目的として開発されました。
商用利用時は適切なライセンス確認を行ってください。

## サポート

問題が発生した場合は、以下の情報と共にお問い合わせください：

1. エラーメッセージ
2. ブラウザの種類・バージョン
3. アップロードしようとしたPDFの種類
4. 実行環境（OS、Pythonバージョン）