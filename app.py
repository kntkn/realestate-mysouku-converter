from flask import Flask, request, render_template, jsonify, send_file, session
import os
import uuid
import tempfile
import base64
import json
import re
from werkzeug.utils import secure_filename
from io import BytesIO
import PyPDF2
import pdfplumber
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import anthropic
from PIL import Image
import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'realestate_mysouku_converter_secret_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30日間セッション保持

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 会社情報のセッション管理関数
def get_company_info():
    """セッションから会社情報を取得"""
    return session.get('company_info', {})

def set_company_info(company_data):
    """セッションに会社情報を保存"""
    session['company_info'] = company_data
    session.permanent = True  # セッションを永続化

ALLOWED_EXTENSIONS = {'pdf'}

# Claude API設定
try:
    claude_client = anthropic.Anthropic(
        api_key=os.environ.get('CLAUDE_API_KEY', '')
    )
    CLAUDE_AVAILABLE = bool(os.environ.get('CLAUDE_API_KEY'))
except Exception as e:
    logger.warning(f"Claude API初期化エラー: {e}")
    claude_client = None
    CLAUDE_AVAILABLE = False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf_page(pdf_data, page_num):
    """PDFの特定ページからテキストを抽出"""
    try:
        with pdfplumber.open(BytesIO(pdf_data)) as pdf:
            if page_num < len(pdf.pages):
                page = pdf.pages[page_num]
                return page.extract_text() or ""
            else:
                logger.warning(f"ページ{page_num + 1}が存在しません")
                return ""
    except Exception as e:
        logger.error(f"ページ{page_num + 1}のテキスト抽出エラー: {str(e)}")
        return ""

def extract_text_from_pdf(file_data):
    """PDFからテキストを抽出（簡易版）"""
    try:
        text = ""
        pdf_file = BytesIO(file_data)
        
        # PyPDF2でテキスト抽出
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        
        if not text.strip():
            # pdfplumberで再試行
            pdf_file.seek(0)
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        
        return text
    except Exception as e:
        print(f"PDF抽出エラー: {e}")
        return ""

def parse_property_data(text):
    """物件データを解析（簡易版）"""
    data = {
        "property_type": "",
        "transaction_type": "",
        "price": "",
        "address": "",
        "access": "",
        "building_area": "",
        "land_area": "",
        "floor_plan": "",
        "building_age": "",
        "structure": "",
        "parking": "",
        "features": []
    }
    
    # 価格・賃料
    price_patterns = [
        r"賃料[：:]\s*([0-9,]+万円)",
        r"価格[：:]\s*([0-9,]+万円)",
        r"([0-9,]+万円)"
    ]
    for pattern in price_patterns:
        match = re.search(pattern, text)
        if match:
            data["price"] = match.group(1)
            break
    
    # 住所
    address_patterns = [
        r"所在地[：:]\s*(.+?)(?=\n|交通)",
        r"住所[：:]\s*(.+?)(?=\n)"
    ]
    for pattern in address_patterns:
        match = re.search(pattern, text)
        if match:
            data["address"] = match.group(1).strip()
            break
    
    # 間取り
    floor_plan_match = re.search(r"([0-9][LDK]+)", text)
    if floor_plan_match:
        data["floor_plan"] = floor_plan_match.group(1)
    
    # 築年数
    age_match = re.search(r"築[：:]?\s*([0-9]+年)", text)
    if age_match:
        data["building_age"] = age_match.group(1)
    
    # 物件種別判定
    if "マンション" in text:
        data["property_type"] = "マンション"
    elif "アパート" in text:
        data["property_type"] = "アパート"
    elif "戸建" in text:
        data["property_type"] = "戸建て"
    elif "土地" in text:
        data["property_type"] = "土地"
    
    # 取引種別判定
    if "賃料" in text or "家賃" in text:
        data["transaction_type"] = "賃貸"
    elif "価格" in text or "売買" in text:
        data["transaction_type"] = "売買"
    
    return data

def create_page_with_footer_overlay(original_page, overlay_page, page_width, page_height):
    """フォールバック: ページ全体を再構築してフッターをオーバーレイ"""
    try:
        # 現時点では元のページをそのまま返す（将来の拡張用）
        logger.warning("フォールバック処理: 現在は元のページを返します")
        return original_page
    except Exception as e:
        logger.error(f"フォールバック処理エラー: {str(e)}")
        return original_page

def detect_footer_region_with_claude_fallback(pdf_data, page_num=0):
    """Claude APIを使用してフッター領域を検出（フォールバック用）"""
    if not CLAUDE_AVAILABLE:
        logger.warning("Claude API利用不可、大きめのデフォルト領域を使用")
        return {'bottom_height': 60, 'confidence': 60}  # 60mm
    
    try:
        # PDFからテキストを抽出（ページ指定に対応）
        if page_num is not None:
            text_content = extract_text_from_pdf_page(pdf_data, page_num)
            logger.info(f"ページ{page_num + 1}のテキスト抽出完了: {len(text_content)}文字")
        else:
            text_content = extract_text_from_pdf(pdf_data)
            logger.info(f"全PDFのテキスト抽出完了: {len(text_content)}文字")
        
        # Claude APIでフッター領域を分析（視覚的レイアウト重視プロンプト）
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": f"""
不動産マイソクPDFの事業者フッター領域を精密に検出してください。物件情報を侵害せず、フッター部分のみを正確に特定する必要があります。

【最重要】検出精度の向上:
以下の事業者情報パターンを最下部から検索し、その直前で物件情報との境界を特定してください。

【事業者情報の必須要素】:
1. 会社名（株式会社○○、○○不動産、有限会社○○）
2. 宅建業免許番号（東京都知事（○）第○○号、国土交通大臣（○）第○○号）
3. 連絡先（TEL、FAX、住所）
4. 取引形態（仲介、媒介、代理、売主）
5. AD情報、手数料情報

【精密な境界検出手法】:
1. テキストを下から上に解析
2. 事業者情報の開始行を特定
3. 物件情報との間の視覚的区切りを確認
4. 必要最小限の高さを計算

【高さ算出基準（保守的）】:
- 1-2行の簡素なフッター: 10-15mm
- 3-4行の標準フッター: 15-25mm
- 5-6行の詳細フッター: 25-35mm
- 複雑なレイアウト/画像有: 35-50mm
- 特殊な装飾/大きなロゴ: 50-70mm（例外的）

【物件情報保護】:
以下は絶対に侵害してはいけません:
- 賃料、価格情報
- 間取り、専有面積
- 所在地、最寄り駅
- 物件写真、間取り図
- 設備情報、築年月

【入力テキスト】:
{text_content[-2000:]}

【必須出力】:
{{
    "footer_detected": true/false,
    "bottom_height": 数値（ミリメートル、保守的に算出）,
    "confidence": 数値（0-100、厳格評価）,
    "boundary_line": "事業者情報開始行の内容",
    "protected_content": "保護すべき物件情報の最下部行",
    "detected_elements": ["検出された事業者要素"],
    "safety_margin": "なぜこの高さが安全か",
    "reason": "境界判定の根拠"
}}
"""
                }
            ]
        )
        
        response_text = response.content[0].text
        
        # JSONレスポンスを解析
        import json
        try:
            result = json.loads(response_text)
            
            # 必須フィールドの検証
            if 'bottom_height' not in result or not isinstance(result['bottom_height'], (int, float)):
                logger.warning(f"Claude API応答に問題: bottom_heightが無効 - {result}")
                return {'bottom_height': 30, 'confidence': 40, 'reason': 'APIレスポンス検証失敗'}
            
            logger.info(f"Claude API 視覚的フッター検出結果: {result}")
            return result
        except json.JSONDecodeError as json_error:
            logger.error(f"Claude API JSON解析エラー: {str(json_error)}")
            logger.error(f"生レスポンス: {response_text[:500]}")
            return {'bottom_height': 30, 'confidence': 30, 'reason': 'JSON解析失敗'}
        
    except Exception as e:
        logger.error(f"Claude API エラー: {str(e)}")
        return None

def detect_footer_region_with_precise_detection(pdf_data, page_num=0):
    """PyMuPDFを使用してフッター領域を精密検出"""
    try:
        logger.info("🔍 PyMuPDFモジュール確認")
        logger.info(f"fitz module: {fitz}")
        logger.info(f"fitz version: {getattr(fitz, '__version__', 'unknown')}")
        
        # PyMuPDFでPDFを開く
        logger.info("📄 PDFファイルをPyMuPDFで開いています...")
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        logger.info(f"✅ PDF開く成功: {len(pdf_document)}ページ")
        
        if page_num >= len(pdf_document):
            logger.warning(f"指定ページ{page_num}が存在しません。ページ数: {len(pdf_document)}")
            page_num = 0
            
        page = pdf_document[page_num]
        page_height = page.rect.height  # pt単位
        
        # 単語レベルでテキストと座標を取得
        words = page.get_text("words")  # [(x0, y0, x1, y1, "text", block_no, line_no, word_no), ...]
        logger.info(f"ページ{page_num + 1}: {len(words)}個の単語を検出、ページ高さ{page_height:.1f}pt")
        
        # フッター候補キーワードの定義
        footer_keywords = [
            "株式会社", "有限会社", "合同会社", "宅建", "免許", "知事", "大臣",
            "TEL", "FAX", "電話", "仲介", "媒介", "代理", "売主", "AD", "手数料"
        ]
        
        # Y座標でグループ化してフッター候補を検索
        footer_candidates = []
        footer_y_positions = []
        
        for word in words:
            x0, y0, x1, y1, text, block_no, line_no, word_no = word
            
            # フッターキーワードが含まれているかチェック
            if any(keyword in text for keyword in footer_keywords):
                footer_candidates.append(word)
                footer_y_positions.append(y0)
                logger.info(f"フッターキーワード発見: '{text}' at Y={y0:.1f}")
        
        if not footer_candidates:
            logger.warning("フッターキーワードが見つかりません。デフォルト値を使用")
            pdf_document.close()
            return {'bottom_height': 30, 'confidence': 50}
        
        # 最も上（Y座標が最小）のフッター要素を特定
        min_footer_y = min(footer_y_positions)
        
        # フッター高さを計算（ページ下部からmin_footer_yまで）
        footer_height_pt = page_height - min_footer_y
        footer_height_mm = footer_height_pt * 25.4 / 72  # pt→mm変換
        
        # 安全マージンを追加（上方向に5mm拡張）
        safety_margin_mm = 5
        final_height_mm = footer_height_mm + safety_margin_mm
        
        # 最小・最大値の制限
        final_height_mm = max(10, min(80, final_height_mm))
        
        # 信頼度の計算
        confidence = min(95, 70 + len(footer_candidates) * 5)
        
        logger.info(f"フッター領域検出完了:")
        logger.info(f"  - 最上フッター位置: Y={min_footer_y:.1f}pt")
        logger.info(f"  - フッター高さ: {footer_height_pt:.1f}pt = {footer_height_mm:.1f}mm")
        logger.info(f"  - 安全マージン追加後: {final_height_mm:.1f}mm")
        logger.info(f"  - 検出キーワード数: {len(footer_candidates)}")
        logger.info(f"  - 信頼度: {confidence}%")
        
        pdf_document.close()
        
        return {
            'bottom_height': round(final_height_mm, 1),
            'confidence': confidence,
            'keywords_found': len(footer_candidates),
            'footer_y_position': min_footer_y
        }
        
    except Exception as e:
        logger.error(f"PyMuPDF フッター検出エラー: {str(e)}")
        return {'bottom_height': 40, 'confidence': 60}

def convert_pdf_footer(pdf_data, company_info):
    """PDFのフッター部分を白塗りし、新しい会社情報を配置"""
    try:
        # PDFを読み込み
        pdf_input = BytesIO(pdf_data)
        
        # PyPDF2の互換性チェック
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_input)
            logger.info(f"PyPDF2でPDF読み込み成功: {len(pdf_reader.pages)}ページ")
        except Exception as read_error:
            logger.error(f"PyPDF2 PDF読み込みエラー: {str(read_error)}")
            raise Exception(f"PDFファイルの読み込みに失敗しました: {str(read_error)}")
        
        pdf_writer = PyPDF2.PdfWriter()
        
        # 元のページサイズを取得
        if len(pdf_reader.pages) == 0:
            raise Exception("PDFにページがありません")
        
        first_page = pdf_reader.pages[0]
        if first_page.mediabox:
            page_width = float(first_page.mediabox.width)
            page_height = float(first_page.mediabox.height)
        else:
            page_width, page_height = A4  # デフォルト
        
        # 新しいPyMuPDF精密検出を使用（全ページ同じ設定で安全動作）
        # まず精密検出を試行、フォールバックでClaude API
        try:
            logger.info("🚀 新PyMuPDF精密フッター検出を開始!")
            global_footer_region = detect_footer_region_with_precise_detection(pdf_data, 0)
            logger.info(f"🎯 PyMuPDF検出結果: {global_footer_region}")
            
            # 信頼度が低い場合はClaude APIを併用
            if global_footer_region.get('confidence', 0) < 60:
                logger.info("信頼度が低いため、Claude APIも併用")
                claude_result = detect_footer_region_with_claude_fallback(pdf_data, 0)
                if claude_result and claude_result.get('confidence', 0) > global_footer_region.get('confidence', 0):
                    global_footer_region = claude_result
                    logger.info("Claude API結果を採用")
            
        except Exception as detection_error:
            logger.error(f"❌ PyMuPDF検出エラー: {str(detection_error)}")
            import traceback
            logger.error(f"❌ PyMuPDF詳細エラー: {traceback.format_exc()}")
            # フォールバック: Claude API
            try:
                logger.info("⚠️ フォールバック: Claude API検出を試行")
                global_footer_region = detect_footer_region_with_claude_fallback(pdf_data, 0)
                if not global_footer_region:
                    global_footer_region = {'bottom_height': 40, 'confidence': 70}
                logger.info(f"✅ Claude API検出完了: {global_footer_region}")
            except Exception as claude_error:
                logger.error(f"❌ Claude API検出エラー: {str(claude_error)}")
                global_footer_region = {'bottom_height': 40, 'confidence': 70}
        
        global_confidence = global_footer_region.get('confidence', 70)
        global_detected_height = global_footer_region.get('bottom_height', 40)
        logger.info(f"グローバル設定: 検出高さ{global_detected_height}mm、信頼度{global_confidence}%")
        
        # 各ページを処理（同じ設定で統一処理）
        for page_num, page in enumerate(pdf_reader.pages):
            logger.info(f"=== ページ {page_num + 1} の処理開始 ===")
            
            try:
                # オーバーレイページを作成
                overlay_buffer = BytesIO()
                overlay_canvas = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
                
                # フッター部分を白で塗りつぶし
                # グローバル設定を使用（全ページ統一）
                confidence = global_confidence
                detected_height = global_detected_height
                
                # 信頼度に応じた高さ調整
                if confidence < 60:
                    # 低信頼度の場合は安全マージンを追加
                    safe_height = max(detected_height + 10, 30)
                    logger.info(f"低信頼度({confidence}%)のため高さを{detected_height}mm→{safe_height}mmに調整")
                    bottom_height_pt = safe_height * mm
                else:
                    bottom_height_pt = detected_height * mm
                # 確実な白塗り処理（複数の矩形で確実にカバー）
                overlay_canvas.setFillColor(colors.white)
                overlay_canvas.setStrokeColor(colors.white)
                
                # シンプルな白塗り矩形（下部フッター領域のみ）
                # PDF座標系: 左下が原点(0,0)、Y軸は上向き
                # bottom_height_ptの高さで、ページ下部からその高さまでを白塗り
                overlay_canvas.rect(0, 0, page_width, bottom_height_pt, fill=1, stroke=0)
                
                logger.info(f"白塗り矩形: X=0, Y=0, Width={page_width/mm:.1f}mm, Height={bottom_height_pt/mm:.1f}mm")
                logger.info(f"座標詳細: 左下(0,0) → 右上({page_width/mm:.1f}mm, {bottom_height_pt/mm:.1f}mm)")
                
                # デバッグ用: 白塗り範囲を赤い枠で囲む（座標確認用）
                overlay_canvas.setStrokeColor(colors.red)
                overlay_canvas.setLineWidth(3)  # より見やすく
                overlay_canvas.rect(0, 0, page_width, bottom_height_pt, fill=0, stroke=1)
                logger.info(f"デバッグ: 赤い枠でマーキング - ページ下部から{bottom_height_pt/mm:.1f}mm高さ")
                
                # 新しい会社情報を配置
                add_company_footer(overlay_canvas, company_info, page_width, bottom_height_pt)
                
                overlay_canvas.save()
                
                # オーバーレイをPDFとして読み込み
                overlay_buffer.seek(0)
                overlay_reader = PyPDF2.PdfReader(overlay_buffer)
                
                if len(overlay_reader.pages) > 0:
                    overlay_page = overlay_reader.pages[0]
                    
                    # デバッグ: オーバーレイ処理の詳細ログ
                    logger.info(f"ページ{page_num + 1}: 白塗り高さ{bottom_height_pt/mm:.1f}mm、信頼度{confidence}%")
                    logger.info(f"ページサイズ: {page_width/mm:.1f}mm x {page_height/mm:.1f}mm")
                    logger.info(f"PDF座標系: 左下(0,0)が原点、白塗りは下部{bottom_height_pt/mm:.1f}mmを範囲指定")
                    
                    # 元のページとオーバーレイをマージ（オーバーレイを最前面に）
                    try:
                        page.merge_page(overlay_page)
                        logger.info(f"ページ{page_num + 1}: オーバーレイ合成完了")
                    except Exception as merge_error:
                        logger.error(f"ページ{page_num + 1}: merge_page失敗 - {str(merge_error)}")
                        # フォールバック: 代替方法でオーバーレイを試行
                        try:
                            # ReportLabでページ全体を再構築
                            page = create_page_with_footer_overlay(page, overlay_page, page_width, page_height)
                            logger.info(f"ページ{page_num + 1}: フォールバック処理で合成完了")
                        except Exception as fallback_error:
                            logger.error(f"ページ{page_num + 1}: フォールバック処理も失敗 - {str(fallback_error)}")
                            # 最後の手段: 元のページをそのまま使用
                            pass
                
                # 処理済みページを追加
                pdf_writer.add_page(page)
                
            except Exception as page_error:
                logger.error(f"ページ {page_num + 1} 処理エラー: {str(page_error)}")
                # エラーが発生したページも元のまま追加
                pdf_writer.add_page(page)
        
        # 最終PDFを出力
        output_buffer = BytesIO()
        pdf_writer.write(output_buffer)
        output_buffer.seek(0)
        
        result = output_buffer.getvalue()
        if len(result) == 0:
            raise Exception("生成されたPDFが空です")
        
        return result
        
    except Exception as e:
        logger.error(f"PDF変換エラー: {str(e)}")
        import traceback
        logger.error(f"詳細なトレースバック: {traceback.format_exc()}")
        return None

def add_company_footer(canvas, company_info, page_width, footer_height):
    """フッター領域に会社情報をバランス良く配置"""
    try:
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        
        # 配置エリアの設定（バランス改善）
        margin = 8 * mm  # 左右マージンを増加
        vertical_margin = 4 * mm  # 上下マージン
        text_start_x = margin
        # フッター領域を3つのゾーンに分割：上余白 + コンテンツ + 下余白
        content_height = footer_height - (2 * vertical_margin)
        text_start_y = footer_height - vertical_margin - 2 * mm  # 上から少し下げて開始
        
        # 日本語フォントの登録と設定（複数のフォールバック）
        font_name = "Helvetica"  # デフォルト
        try:
            # 1. HeiseiKakuGo-W5（標準的な日本語ゴシック）
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
            font_name = 'HeiseiKakuGo-W5'
            canvas.setFont(font_name, 10)
            logger.info(f"日本語フォント設定成功: {font_name}")
        except Exception:
            try:
                # 2. HeiseiMin-W3（明朝体）
                pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
                font_name = 'HeiseiMin-W3'
                canvas.setFont(font_name, 10)
                logger.info(f"日本語フォント設定成功（明朝）: {font_name}")
            except Exception:
                try:
                    # 3. 汎用日本語フォント
                    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
                    font_name = 'STSong-Light'
                    canvas.setFont(font_name, 10)
                    logger.info(f"汎用日本語フォント設定成功: {font_name}")
                except Exception as font_error:
                    logger.warning(f"すべての日本語フォント設定に失敗: {font_error}")
                    try:
                        canvas.setFont("Times-Roman", 10)
                        font_name = "Times-Roman"
                        logger.info("Times-Romanフォントに設定")
                    except:
                        canvas.setFont("Helvetica", 10)
                        font_name = "Helvetica"
                        logger.warning("Helveticaフォントにフォールバック")
        
        canvas.setFillColor(colors.black)
        
        # 水平レイアウト設計: 3カラム構成
        # 左カラム: 宅建番号 + 会社名
        # 中央カラム: 住所 + 電話番号  
        # 右カラム: メール + Web (必要に応じて)
        
        # カラム幅の設定
        left_column_width = page_width * 0.35  # 35%
        center_column_width = page_width * 0.45  # 45%
        right_column_width = page_width * 0.2   # 20%
        
        left_x = margin
        center_x = left_x + left_column_width
        right_x = center_x + center_column_width
        
        # Y位置の設定（2行レイアウト）
        top_line_y = text_start_y
        bottom_line_y = text_start_y - 8 * mm  # 8mm下
        
        logger.info(f"水平レイアウト: page_width={page_width/mm:.1f}mm, left_x={left_x/mm:.1f}mm, center_x={center_x/mm:.1f}mm")
        
        # 左カラム: 宅建番号（上）+ 会社名（下）
        license_number = company_info.get('license_number', '')
        company_name = company_info.get('company_name', '不動産会社')
        
        if license_number:
            canvas.setFont(font_name, 8)
            canvas.drawString(left_x, top_line_y, f"免許番号: {license_number}")
            
        if company_name:
            canvas.setFont(font_name, 20)  # 会社名を20ptに変更
            canvas.drawString(left_x, bottom_line_y, company_name)
        
        # 中央カラム: 住所（上）+ 電話番号（下）
        address = company_info.get('address', '')
        postal_code = company_info.get('postal_code', '')
        phone = company_info.get('phone', '')
        fax = company_info.get('fax', '')
        
        if address:
            address_text = f"〒{postal_code} {address}" if postal_code else address
            canvas.setFont(font_name, 9)
            canvas.drawString(center_x, top_line_y, address_text)
            
        if phone:
            contact_line = f"TEL: {phone}"
            if fax:
                contact_line += f" / FAX: {fax}"
            canvas.setFont(font_name, 9)
            canvas.drawString(center_x, bottom_line_y, contact_line)
        
        # 右カラム: メール（上）+ Web（下）※オプション
        email = company_info.get('email', '')
        website = company_info.get('website', '')
        
        if email or website:
            canvas.setFont(font_name, 8)
            try:
                if email:
                    canvas.drawString(right_x, top_line_y, f"E-mail: {email}")
                if website:
                    canvas.drawString(right_x, bottom_line_y, f"Web: {website}")
            except Exception as e:
                logger.warning(f"右カラム描画エラー: {e}")
        
    except Exception as e:
        logger.error(f"フッター情報描画エラー: {str(e)}")
        # 最低限の情報だけ描画（エラー時のフォールバック）
        try:
            # 最もシンプルなフォントで描画を試す
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.black)
            company_name = company_info.get('company_name', '不動産会社')
            # ASCIIのみの文字に変換（エラー時の最終手段）
            safe_company_name = company_name.encode('ascii', 'ignore').decode('ascii') if company_name else 'Real Estate Company'
            canvas.drawString(5 * mm, footer_height - 10 * mm, safe_company_name)
        except Exception as fallback_error:
            logger.error(f"フォールバック描画も失敗: {fallback_error}")
            pass

def generate_simple_mysouku(property_data, company_data):
    """簡易マイソクPDF生成"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                              topMargin=20*mm, bottomMargin=20*mm)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], 
                                   fontSize=16, textColor=colors.navy, 
                                   alignment=1, spaceAfter=20)
        
        elements = []
        
        # タイトル
        company_name = company_data.get('company_name', '不動産会社')
        elements.append(Paragraph(company_name, title_style))
        
        # 物件情報テーブル
        data = [
            ['物件種別', property_data.get('property_type', '')],
            ['取引種別', property_data.get('transaction_type', '')],
            ['価格・賃料', property_data.get('price', '')],
            ['所在地', property_data.get('address', '')],
            ['間取り', property_data.get('floor_plan', '')],
            ['築年数', property_data.get('building_age', '')]
        ]
        
        # 空の項目を除外
        data = [[k, v] for k, v in data if v]
        
        if data:
            table = Table(data, colWidths=[50*mm, 120*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                ('BACKGROUND', (1, 0), (1, -1), colors.white),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(table)
        
        # 連絡先
        contact_info = []
        if company_data.get('address'):
            contact_info.append(f"住所: {company_data['address']}")
        if company_data.get('phone'):
            contact_info.append(f"TEL: {company_data['phone']}")
        if company_data.get('license_number'):
            contact_info.append(f"免許番号: {company_data['license_number']}")
        
        if contact_info:
            from reportlab.platypus import Spacer
            elements.append(Spacer(1, 20*mm))
            
            contact_table = Table([[info] for info in contact_info], colWidths=[170*mm])
            contact_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(contact_table)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
        
    except Exception as e:
        print(f"PDF生成エラー: {e}")
        return None

@app.route('/test_basic', methods=['POST', 'GET'])
def test_basic():
    """最もシンプルなテスト"""
    return jsonify({
        'status': 'success',
        'message': 'Basic test OK',
        'python_version': '3.x',
        'flask_working': True
    })

@app.route('/test_pypdf2_only', methods=['POST'])
def test_pypdf2_only():
    """PyPDF2のみのテスト"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'ファイルなし'})
        
        file = request.files['pdf_file']
        file_data = file.read()
        
        # PyPDF2でPDF処理
        pdf_input = BytesIO(file_data)
        pdf_reader = PyPDF2.PdfReader(pdf_input)
        page_count = len(pdf_reader.pages)
        
        # 最初のページからテキスト抽出
        if page_count > 0:
            first_page = pdf_reader.pages[0]
            text = first_page.extract_text()
            text_length = len(text)
        else:
            text_length = 0
        
        return jsonify({
            'status': 'success',
            'message': 'PyPDF2テスト成功',
            'page_count': page_count,
            'text_length': text_length,
            'pypdf2_working': True
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'PyPDF2エラー: {str(e)}',
            'pypdf2_working': False
        })

@app.route('/test_pymupdf_only', methods=['POST'])
def test_pymupdf_only():
    """PyMuPDF単体テスト用エンドポイント"""
    try:
        logger.info("🧪 PyMuPDF単体テスト開始")
        
        # Step 1: リクエスト確認
        if 'pdf_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'ファイルなし'})
        
        file = request.files['pdf_file']
        file_data = file.read()
        logger.info(f"🧪 ファイル読み込み成功: {len(file_data)} bytes")
        
        # Step 2: PyMuPDFインポート確認
        try:
            import fitz
            logger.info(f"🧪 PyMuPDF import成功: {getattr(fitz, '__version__', 'unknown')}")
            fitz_status = True
        except ImportError as import_error:
            logger.error(f"🧪 PyMuPDF import失敗: {import_error}")
            return jsonify({
                'status': 'error',
                'message': f'PyMuPDF import失敗: {str(import_error)}',
                'fitz_available': False
            })
        
        # Step 3: シンプルなPDF開くテスト
        try:
            pdf_document = fitz.open(stream=file_data, filetype="pdf")
            page_count = len(pdf_document)
            pdf_document.close()
            logger.info(f"🧪 PDF開く成功: {page_count}ページ")
            pdf_open_status = True
        except Exception as pdf_error:
            logger.error(f"🧪 PDF開くエラー: {pdf_error}")
            return jsonify({
                'status': 'error',
                'message': f'PDF開くエラー: {str(pdf_error)}',
                'fitz_available': True,
                'pdf_open_failed': True
            })
        
        # Step 4: 実際の検出関数テスト
        try:
            result = detect_footer_region_with_precise_detection(file_data, 0)
            logger.info(f"🧪 検出関数成功: {result}")
        except Exception as detection_error:
            logger.error(f"🧪 検出関数エラー: {detection_error}")
            logger.error(f"🧪 検出関数詳細: {traceback.format_exc()}")
            return jsonify({
                'status': 'error',
                'message': f'検出関数エラー: {str(detection_error)}',
                'fitz_available': True,
                'pdf_open_success': True,
                'detection_failed': True
            })
        
        return jsonify({
            'status': 'success',
            'message': 'PyMuPDF完全テスト成功',
            'pymupdf_result': result,
            'fitz_available': True,
            'pdf_pages': page_count
        })
        
    except Exception as e:
        logger.error(f"🧪 予期しないエラー: {str(e)}")
        logger.error(f"🧪 予期しない詳細: {traceback.format_exc()}")
        return jsonify({
            'status': 'error', 
            'message': f'予期しないエラー: {str(e)}',
            'error_type': type(e).__name__
        })

@app.route('/')
def index():
    return render_template('index.html', company_info=get_company_info())

@app.route('/company_settings')
def company_settings():
    return render_template('company_settings.html', company_info=get_company_info())

@app.route('/save_company', methods=['POST'])
def save_company():
    try:
        company_data = {
            'company_name': request.form.get('company_name', ''),
            'company_name_kana': request.form.get('company_name_kana', ''),
            'postal_code': request.form.get('postal_code', ''),
            'address': request.form.get('address', ''),
            'phone': request.form.get('phone', ''),
            'fax': request.form.get('fax', ''),
            'email': request.form.get('email', ''),
            'website': request.form.get('website', ''),
            'license_number': request.form.get('license_number', ''),
            'representative_name': request.form.get('representative_name', ''),
        }
        
        set_company_info(company_data)
        logger.info(f"会社情報を保存: {company_data.get('company_name', '未設定')}")
        return jsonify({'status': 'success', 'message': '会社情報を保存しました'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        file = request.files['pdf_file']
        if not file or file.filename == '':
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        if not allowed_file(file.filename):
            return jsonify({'status': 'error', 'message': 'PDFファイルのみ許可されています'})
        
        # PDF解析
        file_data = file.read()
        text = extract_text_from_pdf(file_data)
        
        if not text.strip():
            return jsonify({'status': 'error', 'message': 'PDFからテキストを抽出できませんでした'})
        
        property_data = parse_property_data(text)
        file_id = uuid.uuid4().hex
        
        return jsonify({
            'status': 'success',
            'file_id': file_id,
            'filename': secure_filename(file.filename),
            'extracted_data': property_data,
            'raw_text': text[:500] + '...' if len(text) > 500 else text
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/process_pdf_simple', methods=['POST'])
def process_pdf_simple():
    """シンプルなPDF処理 - フッター検出と会社名変換"""
    try:
        logger.info("PDF処理開始")
        
        # ファイルチェック
        if 'pdf_file' not in request.files:
            logger.warning("ファイルが選択されていません")
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        file = request.files['pdf_file']
        if not file or file.filename == '':
            logger.warning("ファイルが空です")
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        if not allowed_file(file.filename):
            logger.warning(f"許可されていないファイル形式: {file.filename}")
            return jsonify({'status': 'error', 'message': 'PDFファイルのみ許可されています'})
        
        logger.info(f"ファイル受信: {file.filename}, サイズ: {file.content_length}")
        
        # 出力形式の確認
        output_format = request.form.get('output_format', 'separate')
        logger.info(f"出力形式: {output_format}")
        
        # 会社情報確認
        company_info = get_company_info()
        if not company_info:
            logger.warning("会社情報が設定されていません")
            return jsonify({
                'status': 'error',
                'message': '会社情報が設定されていません。先に会社情報を設定してください。'
            })
        
        logger.info(f"会社情報確認: {company_info.get('company_name', 'N/A')}")
        
        # PDF処理
        try:
            file_data = file.read()
            if len(file_data) == 0:
                return jsonify({'status': 'error', 'message': 'ファイルデータが空です'})
            
            logger.info(f"PDFデータ読込完了: {len(file_data)} bytes")
        except Exception as e:
            logger.error(f"ファイル読み込みエラー: {str(e)}")
            return jsonify({'status': 'error', 'message': 'ファイル読み込みに失敗しました'})
        
        # 内部でグローバルフッター検出を実行
        logger.info("PDF変換でフッター検出を実行")
        
        # PDFを変換
        try:
            logger.info("PDF変換開始")
            converted_pdf = convert_pdf_footer(file_data, company_info)
            
            if converted_pdf and len(converted_pdf) > 0:
                logger.info(f"PDF変換成功: {len(converted_pdf)} bytes")
                pdf_base64 = base64.b64encode(converted_pdf).decode('utf-8')
                filename = f"converted_{secure_filename(file.filename)}"
                
                return jsonify({
                    'status': 'success',
                    'message': 'PDF変換が完了しました',
                    'pdf_data': pdf_base64,
                    'filename': filename
                })
            else:
                logger.error("PDF変換結果が空またはNone")
                return jsonify({'status': 'error', 'message': 'PDF変換に失敗しました'})
                
        except Exception as e:
            logger.error(f"PDF変換処理エラー: {str(e)}")
            import traceback
            logger.error(f"変換エラートレースバック: {traceback.format_exc()}")
            return jsonify({'status': 'error', 'message': f'PDF変換エラー: {str(e)}'})
            
    except Exception as e:
        logger.error(f"予期しないエラー: {str(e)}")
        import traceback
        logger.error(f"全体エラートレースバック: {traceback.format_exc()}")
        return jsonify({'status': 'error', 'message': f'システムエラー: {str(e)}'})

@app.route('/generate_mysouku', methods=['POST'])
def generate_mysouku():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '無効なデータです'})
        
        property_data = data.get('property_data', {})
        file_id = data.get('file_id')
        
        company_info = get_company_info()
        if not company_info:
            return jsonify({
                'status': 'error',
                'message': '会社情報が設定されていません。先に会社情報を設定してください。'
            })
        
        # マイソク生成
        pdf_data = generate_simple_mysouku(property_data, company_info)
        
        if pdf_data:
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
            return jsonify({
                'status': 'success',
                'message': 'マイソクを生成しました',
                'pdf_data': pdf_base64,
                'filename': f'mysouku_{file_id}.pdf'
            })
        else:
            return jsonify({'status': 'error', 'message': 'マイソク生成に失敗しました'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.errorhandler(413)
def too_large(e):
    return jsonify({'status': 'error', 'message': 'ファイルサイズが大きすぎます（最大16MB）'}), 413

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'status': 'error', 'message': 'サーバーエラーが発生しました'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)