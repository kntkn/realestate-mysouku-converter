#!/usr/bin/env python3
"""
マイソク自動変換システム 起動スクリプト
"""

import os
import sys
from app import app

def check_dependencies():
    """必要なライブラリの確認"""
    try:
        import flask
        import PyPDF2
        import pdfplumber
        # import pytesseract
        from PIL import Image
        import reportlab
        print("✓ 必要なライブラリが正常に読み込まれました")
        return True
    except ImportError as e:
        print(f"✗ 必要なライブラリが不足しています: {e}")
        print("pip install -r requirements.txt を実行してください")
        return False

def check_directories():
    """必要なディレクトリの確認・作成"""
    directories = [
        'static/uploads',
        'static/generated',
        'static/css',
        'static/js',
        'templates'
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ ディレクトリを作成しました: {directory}")
        else:
            print(f"✓ ディレクトリが存在します: {directory}")
    
    return True

def main():
    """メイン実行関数"""
    print("=" * 50)
    print("不動産マイソク自動変換システム")
    print("=" * 50)
    
    # 依存関係チェック
    print("\n1. 依存関係チェック...")
    if not check_dependencies():
        sys.exit(1)
    
    # ディレクトリチェック
    print("\n2. ディレクトリチェック...")
    check_directories()
    
    # データベース初期化
    print("\n3. データベース初期化...")
    try:
        from models.company import CompanyModel
        company_model = CompanyModel()
        print("✓ データベースが正常に初期化されました")
    except Exception as e:
        print(f"✗ データベース初期化エラー: {e}")
        sys.exit(1)
    
    # サーバー起動
    print("\n4. Webサーバーを起動しています...")
    print(f"アクセス先: http://localhost:5001")
    print("停止するには Ctrl+C を押してください")
    print("=" * 50)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        print("\n\nサーバーを停止しました")
    except Exception as e:
        print(f"\nサーバーエラー: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()