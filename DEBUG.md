# デバッグガイド

## エラー修正内容

### 1. PDF処理エラー修正
- ページ毎のエラーハンドリング強化
- PyPDF2の互換性問題対応
- メモリ効率の改善

### 2. フォント設定修正
- Helvetica-Bold エラー時のフォールバック
- right-align描画失敗時の左寄せフォールバック

### 3. ログ強化
- 詳細なステップ毎ログ出力
- トレースバック情報の追加
- エラー発生箇所の特定

### 4. JavaScript修正
- AbortController による適切なタイムアウト制御
- HTTPエラー状況の詳細処理
- エラーメッセージの改善

## テスト方法

### 1. 会社情報設定
1. https://realestate-mysouku-converter.vercel.app にアクセス
2. "会社情報を設定する" をクリック
3. 必要な情報を入力（最低限：会社名、電話番号）

### 2. PDF変換テスト
1. メインページでPDFファイルを選択
2. "自動変換実行" ボタンをクリック
3. 処理状況の確認
4. 変換済みPDFのダウンロード

## ログ確認方法

```bash
# Vercelログの確認
vercel logs https://realestate-mysouku-converter.vercel.app

# 特定のデプロイメントログ
vercel logs realestate-mysouku-converter-e4dx2v7p4.vercel.app
```

## 現在の状況
- ✅ デプロイ成功
- ✅ エラーハンドリング強化完了
- ✅ フォールバック機能実装
- ⏳ 実際のPDFでテスト待ち

## 既知の制限事項
- Claude API未設定（デフォルト25mmフッター使用）
- 複雑なPDFレイアウトでは調整が必要な場合あり