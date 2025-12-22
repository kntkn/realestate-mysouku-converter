# Vercel デプロイガイド

## 🚀 Vercelでのデプロイ手順

### 1. Vercelアカウント準備
1. [Vercel](https://vercel.com)にサインアップ/ログイン
2. GitHubアカウントと連携

### 2. プロジェクトのインポート
1. Vercel ダッシュボードで「New Project」をクリック
2. GitHubリポジトリ `realestate-mysouku-converter` を選択
3. 「Import」をクリック

### 3. プロジェクト設定
**Framework Preset**: `Other`を選択

**Build Settings**:
- Build Command: (空のまま)
- Output Directory: (空のまま)
- Install Command: `pip install -r requirements_vercel.txt`

**Root Directory**: `.` (そのまま)

### 4. 環境変数設定（オプション）
**Settings** > **Environment Variables** で以下を設定:

```bash
# セキュリティキー（必須）
SECRET_KEY=your_secret_key_here

# Vercel KV使用時（オプション）
KV_REST_API_URL=https://your-kv-endpoint
KV_REST_API_TOKEN=your_kv_token

# Supabase使用時（オプション）
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
```

### 5. デプロイ実行
1. 「Deploy」ボタンをクリック
2. ビルド完了まで約2-3分待機
3. デプロイ完了後、URLが発行される

## 📋 デプロイ後の設定

### 1. 会社情報の設定
1. デプロイされたURLにアクセス
2. 「会社情報設定」から基本情報を入力
3. 会社ロゴをアップロード（オプション）

### 2. 動作確認
1. サンプルPDFで変換テスト
2. 生成されたマイソクPDFをダウンロード確認

## 🛠️ Vercel特有の制限と対応

### ファイル制限
- **Lambda関数サイズ**: 最大50MB
- **実行時間**: 最大30秒（Hobby Plan）
- **一時ファイル**: `/tmp`ディレクトリのみ利用可能

### データ永続化オプション

#### Option 1: Vercel KV（推奨）
- Redis互換のキーバリューストア
- 月1万リクエスト無料
- 設定: Environment Variablesで`KV_REST_API_URL`と`KV_REST_API_TOKEN`

#### Option 2: Supabase
- PostgreSQL互換データベース
- 月50MB無料
- 設定: Environment Variablesで`SUPABASE_URL`と`SUPABASE_ANON_KEY`

#### Option 3: セッションベース（デフォルト）
- 会社情報は各セッションで入力
- データは永続化されない
- 最も簡単な構成

## 🔧 トラブルシューティング

### ビルドエラー
```bash
# requirements.txtの依存関係エラーの場合
pip install -r requirements_vercel.txt
```

### OCR機能エラー
- TesseractはVercel環境で動作しません
- OCR機能が必要な場合は外部API（Google Vision API等）を使用

### メモリ不足エラー
- 大きなPDFファイル処理時に発生する可能性
- ファイルサイズ制限を5MB以下に調整

### タイムアウトエラー
- 複雑なPDF処理で30秒を超える場合
- Pro Planで実行時間を延長（最大5分）

## 📱 カスタムドメイン設定

### 独自ドメインの設定
1. Vercel プロジェクト > Settings > Domains
2. 「Add Domain」で独自ドメインを追加
3. DNSレコードを設定
4. SSL証明書は自動発行

## 📊 デプロイ状況の監視

### Analytics
- Vercel Analytics で訪問者数を確認
- Core Web Vitals でパフォーマンス監視

### Logs
- Functions タブでLambda実行ログを確認
- エラー発生時のデバッグ情報

## 🔄 継続的デプロイ

### 自動デプロイ
- GitHubにプッシュすると自動デプロイ
- プレビューデプロイで本番前確認
- main ブランチは本番環境に自動反映

### Preview Deployments
- Pull Request作成時に自動でプレビュー環境生成
- レビュー後にマージで本番反映

## 💡 パフォーマンス最適化

### 画像最適化
- Vercel Image Optimization を活用
- 自動的にWebP/AVIF変換

### CDN活用
- 静的ファイルは自動的にCDN配信
- 世界中で高速アクセス可能

## 🎯 本番運用のベストプラクティス

1. **環境変数**: 機密情報は必ず環境変数で管理
2. **エラーハンドリング**: 適切なエラーメッセージとログ出力
3. **セキュリティ**: ファイルアップロード時のバリデーション強化
4. **監視**: Vercel Analytics とログ監視の設定
5. **バックアップ**: 重要なデータは外部ストレージにバックアップ

## 📞 サポート

### Vercelサポート
- [Vercel Documentation](https://vercel.com/docs)
- [Community Discord](https://vercel.com/discord)

### プロジェクト固有
- GitHub Issues: [realestate-mysouku-converter/issues](https://github.com/kntkn/realestate-mysouku-converter/issues)

---

**Deploy Now**: [![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/kntkn/realestate-mysouku-converter)