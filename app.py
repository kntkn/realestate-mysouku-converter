from flask import Flask, request, render_template, jsonify, send_file, redirect, url_for
import os
import uuid
from werkzeug.utils import secure_filename
from utils.pdf_analyzer import PDFAnalyzer
from utils.template_generator import MysoukuTemplateGenerator
from models.company import CompanyModel

app = Flask(__name__)
app.config['SECRET_KEY'] = 'realestate_mysouku_converter_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['GENERATED_FOLDER'] = 'static/generated'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 初期化
pdf_analyzer = PDFAnalyzer()
template_generator = MysoukuTemplateGenerator()
company_model = CompanyModel()

# アップロードフォルダ作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)

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
            'logo_path': ''
        }
        
        # ロゴファイルの処理
        if 'logo' in request.files:
            logo_file = request.files['logo']
            if logo_file and logo_file.filename:
                filename = secure_filename(logo_file.filename)
                logo_path = os.path.join(app.config['UPLOAD_FOLDER'], f"logo_{filename}")
                logo_file.save(logo_path)
                company_data['logo_path'] = logo_path
        
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
        
        # ファイル保存
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # PDF解析
        analysis_result = pdf_analyzer.analyze_pdf(file_path)
        
        if not analysis_result['success']:
            return jsonify({
                'status': 'error',
                'message': f'PDF解析に失敗しました: {analysis_result.get("error", "不明なエラー")}'
            })
        
        # 解析結果を返す
        return jsonify({
            'status': 'success',
            'file_id': unique_filename.split('_')[0],  # UUIDの部分のみ
            'filename': filename,
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
        
        # 出力ファイル名生成
        output_filename = f"mysouku_{file_id}_{uuid.uuid4().hex}.pdf"
        output_path = os.path.join(app.config['GENERATED_FOLDER'], output_filename)
        
        # マイソク生成
        success = template_generator.generate_mysouku(
            property_data,
            company_info,
            output_path
        )
        
        if success:
            return jsonify({
                'status': 'success',
                'message': 'マイソクを生成しました',
                'download_url': f'/download/{output_filename}'
            })
        else:
            return jsonify({'status': 'error', 'message': 'マイソク生成に失敗しました'})
            
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'エラーが発生しました: {str(e)}'})

@app.route('/download/<filename>')
def download_file(filename):
    """ファイルダウンロード"""
    try:
        file_path = os.path.join(app.config['GENERATED_FOLDER'], filename)
        
        if not os.path.exists(file_path):
            return jsonify({'status': 'error', 'message': 'ファイルが見つかりません'})
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=f"マイソク_{filename}",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'ダウンロードエラー: {str(e)}'})

@app.route('/edit_data')
def edit_data():
    """データ編集ページ"""
    return render_template('edit_data.html')

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
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)