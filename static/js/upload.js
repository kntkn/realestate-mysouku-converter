// PDFアップロード・変換機能

let extractedData = null;
let fileId = null;

$(document).ready(function() {
    // アップロードフォームのイベント設定
    $('#uploadForm').on('submit', handleUpload);
    
    // 生成ボタンのイベント設定
    $('#generateBtn').on('click', handleGenerate);
    
    // リセットボタンのイベント設定
    $('#resetBtn').on('click', handleReset);
    
    // ファイル選択時のバリデーション
    $('#pdfFile').on('change', function() {
        const file = this.files[0];
        if (file) {
            if (file.type !== 'application/pdf') {
                showAlert('PDFファイルを選択してください。', 'danger');
                this.value = '';
                return;
            }
            
            if (file.size > 16 * 1024 * 1024) { // 16MB
                showAlert('ファイルサイズが大きすぎます。16MB以下のファイルを選択してください。', 'danger');
                this.value = '';
                return;
            }
            
            showAlert(`ファイル選択完了: ${file.name} (${formatFileSize(file.size)})`, 'success');
        }
    });
});

/**
 * PDFアップロード処理
 */
function handleUpload(event) {
    event.preventDefault();
    
    const formData = new FormData();
    const fileInput = document.getElementById('pdfFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('PDFファイルを選択してください。', 'danger');
        return;
    }
    
    formData.append('pdf_file', file);
    
    // UI更新
    toggleButton('uploadBtn', false);
    toggleSpinner('uploadSpinner', true);
    
    // Ajax送信
    $.ajax({
        url: '/upload_pdf',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        timeout: 120000, // 2分タイムアウト
        success: function(response) {
            if (response.status === 'success') {
                extractedData = response.extracted_data;
                fileId = response.file_id;
                
                showAlert(`PDF解析完了: ${response.filename}`, 'success');
                displayExtractedData(extractedData);
                
                // Step 2を表示
                $('#dataCard').removeClass('d-none');
                
                // スクロール
                $('html, body').animate({
                    scrollTop: $('#dataCard').offset().top - 20
                }, 500);
                
            } else {
                showAlert(response.message || 'アップロードに失敗しました。', 'danger');
            }
        },
        error: function(xhr, status, error) {
            let message = 'アップロードエラーが発生しました。';
            
            if (status === 'timeout') {
                message = 'アップロード処理がタイムアウトしました。ファイルサイズを確認してください。';
            } else if (xhr.responseJSON && xhr.responseJSON.message) {
                message = xhr.responseJSON.message;
            }
            
            showAlert(message, 'danger');
        },
        complete: function() {
            toggleButton('uploadBtn', true);
            toggleSpinner('uploadSpinner', false);
        }
    });
}

/**
 * 抽出データを表示
 */
function displayExtractedData(data) {
    const container = document.getElementById('extractedData');
    
    const fields = [
        { key: 'property_type', label: '物件種別', icon: 'fas fa-home' },
        { key: 'transaction_type', label: '取引種別', icon: 'fas fa-handshake' },
        { key: 'price', label: '価格・賃料', icon: 'fas fa-yen-sign' },
        { key: 'address', label: '所在地', icon: 'fas fa-map-marker-alt' },
        { key: 'access', label: '交通', icon: 'fas fa-train' },
        { key: 'floor_plan', label: '間取り', icon: 'fas fa-th-large' },
        { key: 'building_area', label: '建物面積', icon: 'fas fa-ruler-combined' },
        { key: 'land_area', label: '土地面積', icon: 'fas fa-expand-arrows-alt' },
        { key: 'building_age', label: '築年数', icon: 'fas fa-calendar-alt' },
        { key: 'structure', label: '構造', icon: 'fas fa-building' },
        { key: 'parking', label: '駐車場', icon: 'fas fa-car' }
    ];
    
    let html = '<div class="row">';
    
    fields.forEach(field => {
        const value = data[field.key] || '';
        html += `
            <div class="col-md-6 mb-3">
                <label for="${field.key}" class="form-label">
                    <i class="${field.icon} me-1"></i>
                    ${field.label}
                </label>
                <input type="text" class="form-control" id="${field.key}" 
                       value="${escapeHtml(value)}" data-field="${field.key}">
            </div>
        `;
    });
    
    html += '</div>';
    
    // 設備・特徴
    if (data.features && data.features.length > 0) {
        html += `
            <div class="mb-3">
                <label for="features" class="form-label">
                    <i class="fas fa-list me-1"></i>
                    設備・特徴
                </label>
                <input type="text" class="form-control" id="features" 
                       value="${escapeHtml(data.features.join('、'))}" data-field="features">
                <div class="form-text">複数の項目は「、」で区切って入力してください</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // 入力フィールドの変更イベント設定
    container.querySelectorAll('input[data-field]').forEach(input => {
        input.addEventListener('input', function() {
            const field = this.dataset.field;
            let value = this.value;
            
            if (field === 'features') {
                extractedData[field] = value ? value.split('、').map(item => item.trim()) : [];
            } else {
                extractedData[field] = value;
            }
        });
    });
}

/**
 * マイソク生成処理
 */
function handleGenerate() {
    if (!extractedData || !fileId) {
        showAlert('先にPDFをアップロードしてください。', 'danger');
        return;
    }
    
    // UI更新
    toggleButton('generateBtn', false);
    toggleSpinner('generateSpinner', true);
    
    // Ajax送信
    $.ajax({
        url: '/generate_mysouku',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            property_data: extractedData,
            file_id: fileId
        }),
        timeout: 60000, // 1分タイムアウト
        success: function(response) {
            if (response.status === 'success') {
                showAlert(response.message, 'success');
                
                // ダウンロード機能設定
                const downloadLink = document.getElementById('downloadLink');
                downloadLink.onclick = function(e) {
                    e.preventDefault();
                    downloadPDF(response.pdf_data, response.filename || 'mysouku.pdf');
                };
                
                // Step 3を表示
                $('#downloadCard').removeClass('d-none');
                
                // スクロール
                $('html, body').animate({
                    scrollTop: $('#downloadCard').offset().top - 20
                }, 500);
                
            } else {
                showAlert(response.message || 'マイソク生成に失敗しました。', 'danger');
            }
        },
        error: function(xhr, status, error) {
            let message = 'マイソク生成エラーが発生しました。';
            
            if (status === 'timeout') {
                message = 'マイソク生成処理がタイムアウトしました。';
            } else if (xhr.responseJSON && xhr.responseJSON.message) {
                message = xhr.responseJSON.message;
            }
            
            showAlert(message, 'danger');
        },
        complete: function() {
            toggleButton('generateBtn', true);
            toggleSpinner('generateSpinner', false);
        }
    });
}

/**
 * リセット処理
 */
function handleReset() {
    // データクリア
    extractedData = null;
    fileId = null;
    
    // フォームリセット
    document.getElementById('uploadForm').reset();
    
    // カード非表示
    $('#dataCard').addClass('d-none');
    $('#downloadCard').addClass('d-none');
    
    // ページトップへスクロール
    $('html, body').animate({
        scrollTop: 0
    }, 500);
    
    showAlert('リセットしました。新しいPDFをアップロードしてください。', 'info');
}

/**
 * HTMLエスケープ
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Base64 PDFデータをダウンロード
 */
function downloadPDF(base64Data, filename) {
    try {
        // Base64をBlobに変換
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'application/pdf' });
        
        // ダウンロードリンクを作成
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        
        // ダウンロード実行
        document.body.appendChild(a);
        a.click();
        
        // クリーンアップ
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showAlert('PDFダウンロードを開始しました', 'success');
        
    } catch (error) {
        showAlert('ダウンロードエラーが発生しました: ' + error.message, 'danger');
    }
}