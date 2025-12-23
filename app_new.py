# 新しいシンプルなPyMuPDF版
from flask import Flask, request, render_template, jsonify
import base64
import logging
import traceback
from io import BytesIO
from werkzeug.utils import secure_filename
import PyPDF2
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.colors import colors
from reportlab.lib.units import mm

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/test_pymupdf', methods=['POST'])
def test_pymupdf():
    """PyMuPDFテスト用エンドポイント"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        file = request.files['pdf_file']
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        file_data = file.read()
        
        # PyMuPDF精密検出テスト
        result = pymupdf_footer_detection(file_data)
        
        return jsonify({
            'status': 'success',
            'message': 'PyMuPDF検出テスト完了',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"テストエラー: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

def pymupdf_footer_detection(pdf_data):
    """PyMuPDFを使用してフッター領域を精密検出"""
    try:
        logger.info("🚀 PyMuPDF精密フッター検出開始")
        
        # PyMuPDFでPDFを開く
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        logger.info(f"✅ PDF開く成功: {len(pdf_document)}ページ")
        
        if len(pdf_document) == 0:
            return {'bottom_height': 40, 'confidence': 0, 'error': 'ページなし'}
        
        page = pdf_document[0]  # 最初のページ
        page_height = page.rect.height  # pt単位
        
        # 単語レベルでテキストと座標を取得
        words = page.get_text("words")
        logger.info(f"📄 単語検出: {len(words)}個")
        
        # フッター候補キーワード
        footer_keywords = [
            "株式会社", "有限会社", "宅建", "免許", "知事", "大臣",
            "TEL", "FAX", "仲介", "媒介", "代理", "売主", "AD"
        ]
        
        # フッターキーワードの位置を検索
        footer_positions = []
        found_keywords = []
        
        for word in words:
            if len(word) >= 5:  # PyMuPDFの単語タプルは通常8要素
                x0, y0, x1, y1, text = word[:5]
                
                if any(keyword in text for keyword in footer_keywords):
                    footer_positions.append(y0)
                    found_keywords.append(text)
                    logger.info(f"🎯 フッターキーワード発見: '{text}' at Y={y0:.1f}")
        
        if not footer_positions:
            logger.warning("⚠️ フッターキーワードが見つかりません")
            pdf_document.close()
            return {'bottom_height': 30, 'confidence': 40, 'keywords': []}
        
        # 最も上のフッター位置を特定
        min_footer_y = min(footer_positions)
        footer_height_pt = page_height - min_footer_y
        footer_height_mm = footer_height_pt * 25.4 / 72  # pt→mm変換
        
        # 安全マージン追加
        final_height_mm = footer_height_mm + 5
        final_height_mm = max(10, min(80, final_height_mm))
        
        confidence = min(95, 60 + len(found_keywords) * 10)
        
        result = {
            'bottom_height': round(final_height_mm, 1),
            'confidence': confidence,
            'keywords': found_keywords,
            'page_height': page_height,
            'footer_y': min_footer_y
        }
        
        logger.info(f"✅ 検出完了: {result}")
        pdf_document.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ PyMuPDF検出エラー: {str(e)}")
        logger.error(f"❌ 詳細: {traceback.format_exc()}")
        return {'bottom_height': 40, 'confidence': 0, 'error': str(e)}

if __name__ == '__main__':
    app.run(debug=True)