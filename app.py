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

def detect_footer_region_with_claude(pdf_data):
    """Claude APIを使用してPDFのフッター領域を視覚的レイアウトで検出"""
    if not CLAUDE_AVAILABLE:
        logger.warning("Claude API利用不可、デフォルト領域を使用")
        return None
    
    try:
        # PDFからテキストを抽出
        text_content = extract_text_from_pdf(pdf_data)
        
        # Claude APIでフッター領域を分析（視覚的レイアウト重視プロンプト）
        response = claude_client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=1500,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": f"""
以下は不動産マイソクPDFから抽出したテキストです。物件情報エリアと事業者フッターエリアを分ける視覚的区切りを検出してください。

【重要】視覚的フッター区切りの特徴（テスト素材で確認済み）:
1. カラー帯・背景色（緑色帯、青色帯、水色帯など）
2. 枠線・フレーム（点線囲み、実線囲み、角丸フレーム）
3. 区切り線・罫線（実線、点線、二重線）
4. 空白スペース（物件情報との間の明確な余白）
5. レイアウト変化（文字配置の変化、段組み変更）

【フッター検出優先順位】:
1. 視覚的区切り（線、帯、枠）がある → 高精度
2. レイアウト変化 + 事業者情報 → 中精度
3. 事業者情報のみ → 低精度

【事業者情報キーワード（参考）】:
- 会社名、不動産、株式会社、有限会社、コーポレーション
- 免許番号、国土交通大臣、知事、宅建
- 住所、TEL、FAX、電話、連絡先
- 代理、媒介、売主、仲介

【白塗り高さ判定基準（テスト素材ベース）】:
- 単色帯のみ: 15-20mm
- 帯 + 文字情報: 20-25mm  
- 枠線 + 複数行: 25-30mm
- フレーム囲み + 複雑レイアウト: 30-40mm
- 点線枠 + 装飾的要素: 35-45mm

【入力テキスト（レイアウト構造を重視）】:
{text_content[-2000:]}

【出力形式】:
{{
    "footer_detected": true/false,
    "bottom_height": 数値（ミリメートル）,
    "confidence": 数値（0-100の信頼度）,
    "visual_separator": "検出された区切り要素（帯/線/枠など）",
    "layout_pattern": "レイアウトパターンの説明",
    "detected_elements": ["事業者要素1", "事業者要素2", ...],
    "reason": "視覚的判定の詳細理由"
}}
"""
                }
            ]
        )
        
        response_text = response.content[0].text
        
        # JSONレスポンスを解析
        import json
        result = json.loads(response_text)
        
        logger.info(f"Claude API 視覚的フッター検出結果: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Claude API エラー: {str(e)}")
        return None

def convert_pdf_footer(pdf_data, footer_region, company_info):
    """PDFのフッター部分を白塗りし、新しい会社情報を配置"""
    try:
        # PDFを読み込み
        pdf_input = BytesIO(pdf_data)
        pdf_reader = PyPDF2.PdfReader(pdf_input)
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
        
        # 各ページを処理
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                # オーバーレイページを作成
                overlay_buffer = BytesIO()
                overlay_canvas = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
                
                # フッター部分を白で塗りつぶし
                # 信頼度が低い場合は安全な高さを使用
                confidence = footer_region.get('confidence', 50)
                detected_height = footer_region.get('bottom_height', 25)
                
                # 信頼度に応じた高さ調整
                if confidence < 60:
                    # 低信頼度の場合は安全マージンを追加
                    safe_height = max(detected_height + 10, 30)
                    logger.info(f"低信頼度({confidence}%)のため高さを{detected_height}mm→{safe_height}mmに調整")
                    bottom_height_pt = safe_height * mm
                else:
                    bottom_height_pt = detected_height * mm
                overlay_canvas.setFillColor(colors.white)
                overlay_canvas.rect(0, 0, page_width, bottom_height_pt, fill=1, stroke=0)
                
                # 新しい会社情報を配置
                add_company_footer(overlay_canvas, company_info, page_width, bottom_height_pt)
                
                overlay_canvas.save()
                
                # オーバーレイをPDFとして読み込み
                overlay_buffer.seek(0)
                overlay_reader = PyPDF2.PdfReader(overlay_buffer)
                
                if len(overlay_reader.pages) > 0:
                    overlay_page = overlay_reader.pages[0]
                    
                    # 元のページとオーバーレイをマージ
                    page.merge_page(overlay_page)
                
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
        
        # Claude APIでフッター領域を検出
        try:
            footer_region = detect_footer_region_with_claude(file_data)
            if not footer_region:
                # フォールバック: デフォルト領域
                footer_region = {'bottom_height': 25}  # 25mm
                logger.info("Claude API利用不可、デフォルト領域を使用")
            else:
                confidence = footer_region.get('confidence', 50)
                detected_elements = footer_region.get('detected_elements', [])
                visual_separator = footer_region.get('visual_separator', '不明')
                layout_pattern = footer_region.get('layout_pattern', '不明')
                logger.info(f"Claude API検出結果: {footer_region}")
                logger.info(f"信頼度: {confidence}%, 視覚的区切り: {visual_separator}")
                logger.info(f"レイアウトパターン: {layout_pattern}")
                logger.info(f"検出要素: {detected_elements}")
        except Exception as e:
            logger.error(f"フッター検出エラー: {str(e)}")
            footer_region = {'bottom_height': 25}
        
        # PDFを変換
        try:
            logger.info("PDF変換開始")
            converted_pdf = convert_pdf_footer(file_data, footer_region, company_info)
            
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

@app.errorhandler(404)
def not_found(e):
    return render_template('index.html'), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'status': 'error', 'message': 'サーバーエラーが発生しました'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)