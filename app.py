from flask import Flask, request, render_template, jsonify, send_file
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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'realestate_mysouku_converter_secret_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 簡易会社情報ストレージ（セッション用）
company_storage = {}

ALLOWED_EXTENSIONS = {'pdf'}

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
    return render_template('index.html', company_info=company_storage.get('default'))

@app.route('/company_settings')
def company_settings():
    return render_template('company_settings.html', company_info=company_storage.get('default'))

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
        
        company_storage['default'] = company_data
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

@app.route('/generate_mysouku', methods=['POST'])
def generate_mysouku():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': '無効なデータです'})
        
        property_data = data.get('property_data', {})
        file_id = data.get('file_id')
        
        company_info = company_storage.get('default')
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