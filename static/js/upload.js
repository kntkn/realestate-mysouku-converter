// PDFアップロード・変換機能

// 複数ファイル対応
let extractedDataArray = [];
let fileIdArray = [];
let currentFileIndex = 0;
let totalFiles = 0;

// 単一ファイル（後方互換性）
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
        const files = Array.from(this.files);
        const fileList = document.getElementById('fileList');
        const selectedFilesDiv = document.getElementById('selectedFiles');
        
        if (files.length === 0) {
            fileList.classList.add('d-none');
            return;
        }
        
        // バリデーション
        let validFiles = [];
        let errors = [];
        
        files.forEach((file, index) => {
            if (file.type !== 'application/pdf') {
                errors.push(`${file.name}: PDFファイルではありません`);
                return;
            }
            
            if (file.size > 16 * 1024 * 1024) { // 16MB
                errors.push(`${file.name}: ファイルサイズが大きすぎます（16MB以下）`);
                return;
            }
            
            validFiles.push(file);
        });
        
        if (errors.length > 0) {
            showAlert('エラー:\n' + errors.join('\n'), 'danger');
            this.value = '';
            fileList.classList.add('d-none');
            return;
        }
        
        // 選択されたファイル一覧を表示
        let html = '<div class="row">';
        validFiles.forEach((file, index) => {
            html += `
                <div class="col-md-6 mb-2">
                    <div class="d-flex align-items-center">
                        <i class="fas fa-file-pdf text-danger me-2"></i>
                        <div class="flex-grow-1">
                            <div class="fw-bold">${escapeHtml(file.name)}</div>
                            <small class="text-muted">${formatFileSize(file.size)}</small>
                        </div>
                        <i class="fas fa-check-circle text-success"></i>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        selectedFilesDiv.innerHTML = html;
        fileList.classList.remove('d-none');
        
        showAlert(`${validFiles.length}個のPDFファイルが選択されました`, 'success');
    });
});

/**
 * PDFアップロード処理（複数ファイル対応）
 */
async function handleUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('pdfFile');
    const files = Array.from(fileInput.files);
    
    if (files.length === 0) {
        showAlert('PDFファイルを選択してください。', 'danger');
        return;
    }
    
    // データリセット
    extractedDataArray = [];
    fileIdArray = [];
    currentFileIndex = 0;
    totalFiles = files.length;
    
    // UI更新
    toggleButton('uploadBtn', false);
    toggleSpinner('uploadSpinner', true);
    
    // プログレスバー表示
    showProgressBar(0, totalFiles);
    
    try {
        // 順次アップロード処理
        for (let i = 0; i < files.length; i++) {
            currentFileIndex = i;
            const file = files[i];
            
            showProgressMessage(`ファイル ${i + 1}/${totalFiles} を処理中: ${file.name}`);
            updateProgressBar(i, totalFiles);
            
            const result = await uploadSingleFile(file, i);
            
            if (result.success) {
                extractedDataArray.push(result.data.extracted_data);
                fileIdArray.push(result.data.file_id);
            } else {
                showAlert(`${file.name} の処理でエラー: ${result.message}`, 'warning');
            }
        }
        
        updateProgressBar(totalFiles, totalFiles);
        showProgressMessage(`全${totalFiles}ファイルの処理が完了しました`);
        
        if (extractedDataArray.length > 0) {
            showAlert(`${extractedDataArray.length}個のPDFを正常に解析しました`, 'success');
            displayExtractedDataMultiple(extractedDataArray);
            
            // Step 2を表示
            $('#dataCard').removeClass('d-none');
            
            // スクロール
            $('html, body').animate({
                scrollTop: $('#dataCard').offset().top - 20
            }, 500);
        } else {
            showAlert('すべてのファイルの処理に失敗しました。', 'danger');
        }
        
    } catch (error) {
        showAlert('アップロード処理中にエラーが発生しました: ' + error.message, 'danger');
    } finally {
        toggleButton('uploadBtn', true);
        toggleSpinner('uploadSpinner', false);
        hideProgressBar();
    }
}

/**
 * 単一ファイルのアップロード処理
 */
function uploadSingleFile(file, index) {
    return new Promise((resolve) => {
        const formData = new FormData();
        formData.append('pdf_file', file);
        
        $.ajax({
            url: '/upload_pdf',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            timeout: 120000, // 2分タイムアウト
            success: function(response) {
                if (response.status === 'success') {
                    resolve({ success: true, data: response });
                } else {
                    resolve({ success: false, message: response.message || 'アップロードに失敗しました' });
                }
            },
            error: function(xhr, status, error) {
                let message = 'アップロードエラーが発生しました';
                
                if (status === 'timeout') {
                    message = 'アップロード処理がタイムアウトしました';
                } else if (xhr.responseJSON && xhr.responseJSON.message) {
                    message = xhr.responseJSON.message;
                }
                
                resolve({ success: false, message: message });
            }
        });
    });
}

/**
 * 複数物件の抽出データを表示
 */
function displayExtractedDataMultiple(dataArray) {
    const container = document.getElementById('extractedData');
    
    if (dataArray.length === 1) {
        // 単一ファイルの場合は従来の表示方法
        // 後方互換性のため単一変数も設定
        extractedData = dataArray[0];
        fileId = fileIdArray[0];
        displayExtractedData(dataArray[0], container);
        return;
    }
    
    // 複数ファイルの場合はタブ形式で表示
    let html = `
        <div class="mb-3">
            <h6><i class="fas fa-list me-2"></i>解析結果（${dataArray.length}件の物件）</h6>
        </div>
        
        <!-- ナビゲーションタブ -->
        <ul class="nav nav-tabs" id="propertyTabs" role="tablist">
    `;
    
    dataArray.forEach((data, index) => {
        const isActive = index === 0 ? 'active' : '';
        const propertyName = data.address || data.property_type || `物件${index + 1}`;
        html += `
            <li class="nav-item" role="presentation">
                <button class="nav-link ${isActive}" id="property-${index}-tab" data-bs-toggle="tab" 
                        data-bs-target="#property-${index}" type="button" role="tab">
                    <i class="fas fa-home me-1"></i>
                    ${escapeHtml(propertyName.substring(0, 20))}${propertyName.length > 20 ? '...' : ''}
                </button>
            </li>
        `;
    });
    
    html += `
        </ul>
        
        <!-- タブコンテンツ -->
        <div class="tab-content mt-3" id="propertyTabContent">
    `;
    
    dataArray.forEach((data, index) => {
        const isActive = index === 0 ? 'show active' : '';
        html += `
            <div class="tab-pane fade ${isActive}" id="property-${index}" role="tabpanel">
                <div id="extractedData-${index}"></div>
            </div>
        `;
    });
    
    html += '</div>';
    
    container.innerHTML = html;
    
    // 各タブのデータを表示
    dataArray.forEach((data, index) => {
        const tabContainer = document.getElementById(`extractedData-${index}`);
        displayExtractedData(data, tabContainer, index);
    });
}

/**
 * 単一物件の抽出データを表示
 */
function displayExtractedData(data, container = null, index = 0) {
    if (!container) {
        container = document.getElementById('extractedData');
    }
    
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
        const fieldId = index > 0 ? `${field.key}-${index}` : field.key;
        html += `
            <div class="col-md-6 mb-3">
                <label for="${fieldId}" class="form-label">
                    <i class="${field.icon} me-1"></i>
                    ${field.label}
                </label>
                <input type="text" class="form-control" id="${fieldId}" 
                       value="${escapeHtml(value)}" data-field="${field.key}" data-index="${index}">
            </div>
        `;
    });
    
    html += '</div>';
    
    // 設備・特徴
    if (data.features && data.features.length > 0) {
        const featuresId = index > 0 ? `features-${index}` : 'features';
        html += `
            <div class="mb-3">
                <label for="${featuresId}" class="form-label">
                    <i class="fas fa-list me-1"></i>
                    設備・特徴
                </label>
                <input type="text" class="form-control" id="${featuresId}" 
                       value="${escapeHtml(data.features.join('、'))}" data-field="features" data-index="${index}">
                <div class="form-text">複数の項目は「、」で区切って入力してください</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
    
    // 入力フィールドの変更イベント設定
    container.querySelectorAll('input[data-field]').forEach(input => {
        input.addEventListener('input', function() {
            const field = this.dataset.field;
            const dataIndex = parseInt(this.dataset.index) || 0;
            let value = this.value;
            
            // 複数ファイルの場合は配列の該当インデックスを更新
            const targetData = extractedDataArray.length > 0 ? extractedDataArray[dataIndex] : extractedData;
            
            if (field === 'features') {
                targetData[field] = value ? value.split('、').map(item => item.trim()) : [];
            } else {
                targetData[field] = value;
            }
        });
    });
}

/**
 * マイソク生成処理（複数ファイル対応）
 */
async function handleGenerate() {
    const hasMultipleFiles = extractedDataArray.length > 0;
    const dataToProcess = hasMultipleFiles ? extractedDataArray : [extractedData];
    const fileIdsToProcess = hasMultipleFiles ? fileIdArray : [fileId];
    
    if (!dataToProcess[0] || !fileIdsToProcess[0]) {
        showAlert('先にPDFをアップロードしてください。', 'danger');
        return;
    }
    
    // UI更新
    toggleButton('generateBtn', false);
    toggleSpinner('generateSpinner', true);
    
    // プログレスバー表示
    showProgressBar(0, dataToProcess.length);
    showProgressMessage('マイソクPDFを生成中...');
    
    try {
        const generatedPdfs = [];
        
        // 各物件データを順次処理
        for (let i = 0; i < dataToProcess.length; i++) {
            const propertyData = dataToProcess[i];
            const currentFileId = fileIdsToProcess[i];
            
            showProgressMessage(`${i + 1}/${dataToProcess.length} 件目のマイソクを生成中...`);
            updateProgressBar(i, dataToProcess.length);
            
            const result = await generateSingleMysouku(propertyData, currentFileId, i);
            
            if (result.success) {
                generatedPdfs.push(result.data);
            } else {
                showAlert(`${i + 1}件目の生成でエラー: ${result.message}`, 'warning');
            }
        }
        
        updateProgressBar(dataToProcess.length, dataToProcess.length);
        showProgressMessage('マイソク生成が完了しました');
        
        if (generatedPdfs.length > 0) {
            showAlert(`${generatedPdfs.length}件のマイソクを生成しました`, 'success');
            
            // ダウンロード機能設定
            setupDownloadLinks(generatedPdfs, hasMultipleFiles);
            
            // Step 3を表示
            $('#downloadCard').removeClass('d-none');
            
            // スクロール
            $('html, body').animate({
                scrollTop: $('#downloadCard').offset().top - 20
            }, 500);
            
        } else {
            showAlert('すべての生成に失敗しました。', 'danger');
        }
        
    } catch (error) {
        showAlert('マイソク生成中にエラーが発生しました: ' + error.message, 'danger');
    } finally {
        toggleButton('generateBtn', true);
        toggleSpinner('generateSpinner', false);
        hideProgressBar();
    }
}

/**
 * 単一マイソクの生成処理
 */
function generateSingleMysouku(propertyData, fileId, index) {
    return new Promise((resolve) => {
        $.ajax({
            url: '/generate_mysouku',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                property_data: propertyData,
                file_id: fileId
            }),
            timeout: 60000, // 1分タイムアウト
            success: function(response) {
                if (response.status === 'success') {
                    resolve({ 
                        success: true, 
                        data: {
                            pdf_data: response.pdf_data,
                            filename: response.filename || `mysouku_${index + 1}.pdf`,
                            index: index
                        }
                    });
                } else {
                    resolve({ success: false, message: response.message || 'マイソク生成に失敗しました' });
                }
            },
            error: function(xhr, status, error) {
                let message = 'マイソク生成エラーが発生しました';
                
                if (status === 'timeout') {
                    message = 'マイソク生成処理がタイムアウトしました';
                } else if (xhr.responseJSON && xhr.responseJSON.message) {
                    message = xhr.responseJSON.message;
                }
                
                resolve({ success: false, message: message });
            }
        });
    });
}

/**
 * ダウンロードリンクの設定
 */
function setupDownloadLinks(generatedPdfs, hasMultiple) {
    const downloadCard = document.querySelector('#downloadCard .card-body');
    
    if (hasMultiple && generatedPdfs.length > 1) {
        // 複数ファイルの場合は個別ダウンロードリンクを表示
        let html = `
            <div class="alert alert-success" role="alert">
                <h5 class="alert-heading">
                    <i class="fas fa-check-circle me-2"></i>
                    ${generatedPdfs.length}件のマイソク生成が完了しました！
                </h5>
                <p class="mb-3">弊社仕様のマイソクPDFが生成されました。</p>
                
                <div class="row">
        `;
        
        generatedPdfs.forEach((pdf, index) => {
            html += `
                <div class="col-md-6 mb-2">
                    <a href="#" class="btn btn-info btn-sm w-100 download-link" 
                       data-pdf="${pdf.pdf_data}" data-filename="${pdf.filename}">
                        <i class="fas fa-download me-1"></i>
                        ${pdf.filename}
                    </a>
                </div>
            `;
        });
        
        html += `
                </div>
                
                <button type="button" class="btn btn-outline-secondary mt-3" id="resetBtn">
                    <i class="fas fa-redo me-1"></i>
                    新しいPDFを変換
                </button>
            </div>
        `;
        
        downloadCard.innerHTML = html;
        
        // ダウンロードリンクのイベント設定
        downloadCard.querySelectorAll('.download-link').forEach(link => {
            link.onclick = function(e) {
                e.preventDefault();
                const pdfData = this.dataset.pdf;
                const filename = this.dataset.filename;
                downloadPDF(pdfData, filename);
            };
        });
        
    } else {
        // 単一ファイルの場合は従来通り
        const pdf = generatedPdfs[0];
        const downloadLink = document.getElementById('downloadLink');
        downloadLink.onclick = function(e) {
            e.preventDefault();
            downloadPDF(pdf.pdf_data, pdf.filename);
        };
    }
}

/**
 * リセット処理
 */
function handleReset() {
    // データクリア
    extractedData = null;
    fileId = null;
    extractedDataArray = [];
    fileIdArray = [];
    currentFileIndex = 0;
    totalFiles = 0;
    
    // フォームリセット
    document.getElementById('uploadForm').reset();
    
    // ファイル一覧も非表示
    document.getElementById('fileList').classList.add('d-none');
    
    // カード非表示
    $('#dataCard').addClass('d-none');
    $('#downloadCard').addClass('d-none');
    
    // プログレスバー非表示
    hideProgressBar();
    
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
 * プログレスバー表示
 */
function showProgressBar(current, total) {
    const progressHtml = `
        <div id="progressContainer" class="mt-3">
            <div class="d-flex justify-content-between mb-1">
                <span id="progressLabel">処理中...</span>
                <span id="progressPercent">0%</span>
            </div>
            <div class="progress">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     id="progressBar" role="progressbar" style="width: 0%" 
                     aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                </div>
            </div>
        </div>
    `;
    
    // プログレスバーを適切な位置に挿入
    let targetElement = document.querySelector('#uploadSpinner').parentElement;
    if (!document.getElementById('progressContainer')) {
        targetElement.insertAdjacentHTML('afterend', progressHtml);
    }
    
    updateProgressBar(current, total);
}

/**
 * プログレスバー更新
 */
function updateProgressBar(current, total) {
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    
    if (progressBar && progressPercent) {
        const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
        
        progressBar.style.width = percentage + '%';
        progressBar.setAttribute('aria-valuenow', percentage);
        progressPercent.textContent = percentage + '%';
    }
}

/**
 * プログレスメッセージ更新
 */
function showProgressMessage(message) {
    const progressLabel = document.getElementById('progressLabel');
    if (progressLabel) {
        progressLabel.textContent = message;
    }
}

/**
 * プログレスバー非表示
 */
function hideProgressBar() {
    const progressContainer = document.getElementById('progressContainer');
    if (progressContainer) {
        progressContainer.remove();
    }
}

/**
 * ファイルサイズをフォーマット
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * ボタンの有効/無効切り替え
 */
function toggleButton(buttonId, enabled) {
    const button = document.getElementById(buttonId);
    if (button) {
        if (enabled) {
            button.disabled = false;
            button.classList.remove('disabled');
        } else {
            button.disabled = true;
            button.classList.add('disabled');
        }
    }
}

/**
 * スピナーの表示/非表示切り替え
 */
function toggleSpinner(spinnerId, visible) {
    const spinner = document.getElementById(spinnerId);
    if (spinner) {
        if (visible) {
            spinner.classList.remove('d-none');
        } else {
            spinner.classList.add('d-none');
        }
    }
}

/**
 * アラート表示
 */
function showAlert(message, type = 'info') {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertContainer.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    
    alertContainer.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${getAlertIcon(type)} me-2"></i>
            <span style="white-space: pre-line;">${escapeHtml(message)}</span>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(alertContainer);
    
    // 5秒後に自動削除
    setTimeout(() => {
        if (alertContainer.parentNode) {
            alertContainer.remove();
        }
    }, 5000);
}

/**
 * アラートタイプに応じたアイコンを取得
 */
function getAlertIcon(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
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