from flask import Flask, request, render_template, jsonify, send_file, redirect, url_for
import os
import uuid
import tempfile
import base64
import json
from werkzeug.utils import secure_filename
from io import BytesIO

# 相対インポート用のパス設定
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pdf_analyzer import PDFAnalyzer
from utils.template_generator import MysoukuTemplateGenerator
from models.company_cloud import CompanyCloudModel  # Cloud対応版

app = Flask(__name__, 
           template_folder='../templates',
           static_folder='../static')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'realestate_mysouku_converter_secret_key')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# 初期化
pdf_analyzer = PDFAnalyzer()
template_generator = MysoukuTemplateGenerator()
company_model = CompanyCloudModel()

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """許可されたファイル形式かチェック"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """メインページ"""
    company_info = company_model.get_company_info()
    return render_template('index.html', company_info=company_info)

@app.route('/company_settings')
def company_settings():
    """会社情報設定ページ"""
    company_info = company_model.get_company_info()
    return render_template('company_settings.html', company_info=company_info)

@app.route('/save_company', methods=['POST'])
def save_company():
    """会社情報保存"""
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
            'logo_data': ''
        }
        
        # ロゴファイルの処理（Base64エンコード）
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                logo_data = base64.b64encode(logo_file.read()).decode('utf-8')
                company_data['logo_data'] = logo_data
                company_data['logo_filename'] = secure_filename(logo_file.filename)
        
        success = company_model.save_company_info(company_data)
        
        if success:
            return jsonify({'status': 'success', 'message': '会社情報を保存しました'})
        else:
            return jsonify({'status': 'error', 'message': '保存に失敗しました'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    """PDFアップロード・解析"""
    try:
        if 'pdf_file' not in request.files:
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        file = request.files['pdf_file']
        
        if file.filename == '':
            return jsonify({'status': 'error', 'message': 'ファイルが選択されていません'})
        
        if not allowed_file(file.filename):
            return jsonify({'status': 'error', 'message': 'PDFファイルのみ許可されています'})
        
        # 一時ファイルとして処理
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            file.save(temp_file.name)
            
            # PDF解析
            analysis_result = pdf_analyzer.analyze_pdf(temp_file.name)
            
            # 一時ファイル削除
            os.unlink(temp_file.name)
        
        if not analysis_result['success']:
            return jsonify({
                'status': 'error',
                'message': f'PDF解析に失敗しました: {analysis_result.get("error", "不明なエラー")}'
            })
        
        # 解析結果を返す
        file_id = uuid.uuid4().hex
        return jsonify({
            'status': 'success',
            'file_id': file_id,
            'filename': secure_filename(file.filename),
            'extracted_data': analysis_result['structured_data'],
            'raw_text': analysis_result['raw_text'][:500] + '...' if len(analysis_result['raw_text']) > 500 else analysis_result['raw_text']
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/generate_mysouku', methods=['POST'])
def generate_mysouku():
    """マイソク生成"""
    try:
        # リクエストデータ取得
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': '無効なデータです'})
        
        property_data = data.get('property_data', {})
        file_id = data.get('file_id')
        
        # 会社情報取得
        company_info = company_model.get_company_info()
        
        if not company_info:
            return jsonify({
                'status': 'error',
                'message': '会社情報が設定されていません。先に会社情報を設定してください。'
            })
        
        # 一時ファイルでマイソク生成
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            success = template_generator.generate_mysouku(
                property_data,
                company_info,
                temp_file.name
            )
            
            if success:
                # ファイルをBase64エンコードして返す
                temp_file.seek(0)
                pdf_data = temp_file.read()
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                
                # 一時ファイル削除
                os.unlink(temp_file.name)
                
                return jsonify({
                    'status': 'success',
                    'message': 'マイソクを生成しました',
                    'pdf_data': pdf_base64,
                    'filename': f'mysouku_{file_id}.pdf'
                })
            else:
                os.unlink(temp_file.name)
                return jsonify({'status': 'error', 'message': 'マイソク生成に失敗しました'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    """PDFダウンロード"""
    try:
        data = request.get_json()
        pdf_base64 = data.get('pdf_data')
        filename = data.get('filename', 'mysouku.pdf')
        
        if not pdf_base64:
            return jsonify({'status': 'error', 'message': 'PDFデータが見つかりません'})
        
        # Base64デコード
        pdf_data = base64.b64decode(pdf_base64)
        
        # BytesIOでファイル送信
        pdf_io = BytesIO(pdf_data)
        pdf_io.seek(0)
        
        return send_file(
            pdf_io,
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'ダウンロードエラー: {str(e)}'})

@app.errorhandler(413)
def too_large(e):
    """ファイルサイズエラー"""
    return jsonify({'status': 'error', 'message': 'ファイルサイズが大きすぎます（最大16MB）'}), 413

@app.errorhandler(404)
def not_found(e):
    """404エラー"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    """500エラー"""
    return jsonify({'status': 'error', 'message': 'サーバーエラーが発生しました'}), 500

# Vercel用のハンドラ
def handler(request):
    """Vercel Lambda用ハンドラ"""
    return app(request.environ, request.start_response)

if __name__ == '__main__':
    app.run(debug=True)