#!/usr/bin/env python3
"""PyMuPDFのテストスクリプト"""

import fitz
import logging

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pymupdf():
    """PyMuPDFの基本動作テスト"""
    try:
        logger.info(f"PyMuPDF version: {fitz.__version__ if hasattr(fitz, '__version__') else 'unknown'}")
        logger.info("PyMuPDFテスト完了")
        return True
    except Exception as e:
        logger.error(f"PyMuPDFテストエラー: {e}")
        return False

if __name__ == "__main__":
    result = test_pymupdf()
    print(f"テスト結果: {'成功' if result else '失敗'}")