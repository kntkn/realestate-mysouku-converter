// マイソク会社名自動変換 - シンプル版

let selectedFiles = [];

$(document).ready(function() {
    // ファイル選択イベント
    $('#pdfFile').on('change', handleFileSelection);
    
    // ドラッグ＆ドロップ
    setupDragAndDrop();
    
    // 変換実行
    $('#processForm').on('submit', handleProcessing);
    
    // リセット
    $('#resetBtn').on('click', handleReset);
});

/**
 * ファイル選択処理
 */
function handleFileSelection() {
    const files = Array.from(document.getElementById('pdfFile').files);
    const fileListContainer = document.getElementById('fileList');
    const selectedFilesContainer = document.getElementById('selectedFiles');
    const processBtn = document.getElementById('processBtn');
    
    // リセット
    selectedFiles = [];
    
    if (files.length === 0) {
        fileListContainer.classList.add('d-none');
        processBtn.disabled = true;
        return;
    }
    
    // ファイル検証
    let validFiles = [];
    let errors = [];
    
    files.forEach(file => {
        if (file.type !== 'application/pdf') {
            errors.push(`${file.name}: PDFファイルではありません`);
            return;
        }
        
        if (file.size > 16 * 1024 * 1024) {
            errors.push(`${file.name}: ファイルサイズが大きすぎます（16MB以下）`);
            return;
        }
        
        validFiles.push(file);
    });
    
    if (errors.length > 0) {
        showNotification('エラー: ' + errors.join(', '), 'error');
        processBtn.disabled = true;
        fileListContainer.classList.add('d-none');
        return;
    }
    
    // ファイル一覧表示
    selectedFiles = validFiles;
    displaySelectedFiles(validFiles, selectedFilesContainer);
    fileListContainer.classList.remove('d-none');
    
    // 出力オプションを常に表示（1ファイル内の複数物件も考慮）
    const outputOptions = document.getElementById('outputOptions');
    outputOptions.classList.remove('d-none');
    
    processBtn.disabled = false;
    
    showNotification(`${validFiles.length}個のファイルが選択されました`, 'success');
}

/**
 * 選択されたファイル一覧表示
 */
function displaySelectedFiles(files, container) {
    let html = '<div class="row">';
    
    files.forEach((file, index) => {
        html += `
            <div class="col-md-6 mb-2">
                <div class="d-flex align-items-center p-2 border rounded bg-white">
                    <i class="fas fa-file-pdf text-danger me-2"></i>
                    <div class="flex-grow-1">
                        <div class="fw-bold small">${escapeHtml(file.name)}</div>
                        <small class="text-muted">${formatFileSize(file.size)}</small>
                    </div>
                    <i class="fas fa-check-circle text-success"></i>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

/**
 * ドラッグ&ドロップ設定
 */
function setupDragAndDrop() {
    const uploadArea = document.querySelector('.file-upload-area');
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, unhighlight, false);
    });
    
    uploadArea.addEventListener('drop', handleDrop, false);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight(e) {
        uploadArea.classList.add('dragover');
    }
    
    function unhighlight(e) {
        uploadArea.classList.remove('dragover');
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        document.getElementById('pdfFile').files = files;
        handleFileSelection();
    }
}

/**
 * 変換処理実行
 */
async function handleProcessing(event) {
    event.preventDefault();
    
    if (selectedFiles.length === 0) {
        showNotification('PDFファイルを選択してください', 'error');
        return;
    }
    
    // UI更新
    const processBtn = document.getElementById('processBtn');
    const processingStatus = document.getElementById('processingStatus');
    const statusMessage = document.getElementById('statusMessage');
    
    processBtn.disabled = true;
    processingStatus.classList.remove('d-none');
    
    try {
        const results = [];
        
        // 各ファイルを順次処理
        for (let i = 0; i < selectedFiles.length; i++) {
            const file = selectedFiles[i];
            const current = i + 1;
            const total = selectedFiles.length;
            
            statusMessage.textContent = `${current}/${total}: ${file.name} を処理中...`;
            
            const result = await processIndividualFile(file, i);
            if (result.success) {
                results.push(result);
                statusMessage.textContent = `${current}/${total}: ${file.name} 完了`;
            } else {
                showNotification(`${file.name} の処理でエラー: ${result.error}`, 'warning');
            }
            
            // 短時間の遅延でUI更新を視覚化
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        if (results.length > 0) {
            statusMessage.textContent = '変換完了！';
            setTimeout(() => {
                processingStatus.classList.add('d-none');
                showDownloadResults(results);
            }, 1000);
        } else {
            throw new Error('すべてのファイルの処理に失敗しました');
        }
        
    } catch (error) {
        showNotification(`処理エラー: ${error.message}`, 'error');
        processingStatus.classList.add('d-none');
        processBtn.disabled = false;
    }
}

/**
 * 個別ファイル処理
 */
async function processIndividualFile(file, index) {
    const formData = new FormData();
    formData.append('pdf_file', file);
    
    // 出力形式の設定を追加
    const outputFormat = document.querySelector('input[name="outputFormat"]:checked')?.value || 'separate';
    formData.append('output_format', outputFormat);
    
    try {
        // タイムアウト付きfetch
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 2分タイムアウト
        
        const response = await fetch('/process_pdf_simple', {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            throw new Error(`HTTPエラー: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.status === 'success') {
            return {
                success: true,
                filename: result.filename,
                pdfData: result.pdf_data,
                originalName: file.name
            };
        } else {
            return {
                success: false,
                error: result.message || 'PDFの処理に失敗しました'
            };
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            return {
                success: false,
                error: 'タイムアウト: 処理に時間がかかりすぎています'
            };
        } else {
            return {
                success: false,
                error: error.message || 'ネットワークエラーが発生しました'
            };
        }
    }
}

/**
 * ダウンロード結果表示
 */
function showDownloadResults(results) {
    const downloadCard = document.getElementById('downloadCard');
    const downloadContent = document.getElementById('downloadContent');
    
    let html = `
        <div class="text-center">
            <i class="fas fa-check-circle fa-3x text-success mb-3"></i>
            <h4 class="text-success mb-3">変換完了！</h4>
            <p class="text-muted mb-4">${results.length}個のPDFファイルが正常に変換されました</p>
    `;
    
    if (results.length === 1) {
        // 単一ファイル
        const result = results[0];
        html += `
            <a href="#" class="btn btn-success btn-lg" onclick="downloadPDF('${result.pdfData}', '${result.filename}')">
                <i class="fas fa-download me-2"></i>
                PDFをダウンロード
            </a>
        `;
    } else {
        // 複数ファイル
        html += '<div class="row justify-content-center">';
        results.forEach((result, index) => {
            html += `
                <div class="col-md-6 mb-2">
                    <a href="#" class="btn btn-success btn-sm w-100" onclick="downloadPDF('${result.pdfData}', '${result.filename}')">
                        <i class="fas fa-download me-1"></i>
                        ${escapeHtml(result.filename)}
                    </a>
                </div>
            `;
        });
        html += '</div>';
    }
    
    html += '</div>';
    
    downloadContent.innerHTML = html;
    downloadCard.classList.remove('d-none');
    
    // スムーズスクロール
    downloadCard.scrollIntoView({ behavior: 'smooth' });
}

/**
 * リセット処理
 */
function handleReset() {
    selectedFiles = [];
    document.getElementById('processForm').reset();
    document.getElementById('fileList').classList.add('d-none');
    document.getElementById('outputOptions').classList.add('d-none');
    document.getElementById('downloadCard').classList.add('d-none');
    document.getElementById('processingStatus').classList.add('d-none');
    document.getElementById('processBtn').disabled = true;
    
    // スムーズスクロールで最上部に
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    showNotification('リセットしました', 'info');
}

/**
 * PDFダウンロード
 */
function downloadPDF(base64Data, filename) {
    try {
        const byteCharacters = atob(base64Data);
        const byteNumbers = new Array(byteCharacters.length);
        
        for (let i = 0; i < byteCharacters.length; i++) {
            byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: 'application/pdf' });
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        
        document.body.appendChild(a);
        a.click();
        
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('ダウンロードを開始しました', 'success');
    } catch (error) {
        showNotification(`ダウンロードエラー: ${error.message}`, 'error');
    }
}

/**
 * ユーティリティ関数
 */

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function showNotification(message, type = 'info') {
    const alertContainer = document.createElement('div');
    alertContainer.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show position-fixed`;
    alertContainer.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
    
    const iconMap = {
        success: 'check-circle',
        error: 'exclamation-circle',
        warning: 'exclamation-triangle',
        info: 'info-circle'
    };
    
    alertContainer.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${iconMap[type] || 'info-circle'} me-2"></i>
            <span>${escapeHtml(message)}</span>
            <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(alertContainer);
    
    setTimeout(() => {
        if (alertContainer.parentNode) {
            alertContainer.remove();
        }
    }, 5000);
}