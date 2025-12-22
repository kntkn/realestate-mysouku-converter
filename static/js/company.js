// 会社情報設定機能

$(document).ready(function() {
    // フォーム送信イベント設定
    $('#companyForm').on('submit', handleSave);
    
    // フォームバリデーション
    setupValidation();
});

/**
 * 会社情報保存処理
 */
function handleSave(event) {
    event.preventDefault();
    
    if (!validateForm()) {
        return;
    }
    
    const formData = new FormData();
    const form = document.getElementById('companyForm');
    
    // フォームデータを収集
    const formElements = form.elements;
    for (let element of formElements) {
        if (element.type === 'file') {
            if (element.files.length > 0) {
                formData.append(element.name, element.files[0]);
            }
        } else if (element.name) {
            formData.append(element.name, element.value);
        }
    }
    
    // UI更新
    toggleButton('saveBtn', false);
    toggleSpinner('saveSpinner', true);
    
    // Ajax送信
    $.ajax({
        url: '/save_company',
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            if (response.status === 'success') {
                showAlert(response.message, 'success');
                
                // 少し待ってからメインページへリダイレクト
                setTimeout(() => {
                    window.location.href = '/';
                }, 2000);
                
            } else {
                showAlert(response.message || '保存に失敗しました。', 'danger');
            }
        },
        error: function(xhr, status, error) {
            let message = '保存エラーが発生しました。';
            
            if (xhr.responseJSON && xhr.responseJSON.message) {
                message = xhr.responseJSON.message;
            }
            
            showAlert(message, 'danger');
        },
        complete: function() {
            toggleButton('saveBtn', true);
            toggleSpinner('saveSpinner', false);
        }
    });
}

/**
 * フォームバリデーション設定
 */
function setupValidation() {
    // リアルタイムバリデーション
    const requiredFields = ['companyName', 'address', 'phone', 'licenseNumber'];
    
    requiredFields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('blur', function() {
                validateField(this);
            });
            
            field.addEventListener('input', function() {
                clearFieldError(this);
            });
        }
    });
    
    // 電話番号・FAX番号の入力フォーマット
    ['phone', 'fax'].forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.addEventListener('input', function() {
                formatPhoneNumber(this);
            });
        }
    });
    
    // 郵便番号の入力フォーマット
    const postalCodeField = document.getElementById('postalCode');
    if (postalCodeField) {
        postalCodeField.addEventListener('input', function() {
            formatPostalCode(this);
        });
    }
    
    // ロゴファイルのバリデーション
    const logoField = document.getElementById('logo');
    if (logoField) {
        logoField.addEventListener('change', function() {
            validateLogoFile(this);
        });
    }
}

/**
 * フォーム全体のバリデーション
 */
function validateForm() {
    const requiredFields = [
        { id: 'companyName', name: '会社名' },
        { id: 'address', name: '住所' },
        { id: 'phone', name: '電話番号' },
        { id: 'licenseNumber', name: '宅建業免許番号' }
    ];
    
    let isValid = true;
    
    requiredFields.forEach(field => {
        const element = document.getElementById(field.id);
        if (!validateField(element)) {
            isValid = false;
        }
    });
    
    // メールアドレスのバリデーション
    const emailField = document.getElementById('email');
    if (emailField && emailField.value) {
        if (!isValidEmail(emailField.value)) {
            setFieldError(emailField, '正しいメールアドレスを入力してください。');
            isValid = false;
        }
    }
    
    // ウェブサイトのバリデーション
    const websiteField = document.getElementById('website');
    if (websiteField && websiteField.value) {
        if (!isValidURL(websiteField.value)) {
            setFieldError(websiteField, '正しいURLを入力してください。');
            isValid = false;
        }
    }
    
    return isValid;
}

/**
 * 個別フィールドのバリデーション
 */
function validateField(field) {
    if (!field) return true;
    
    const value = field.value.trim();
    const isRequired = field.hasAttribute('required');
    
    if (isRequired && !value) {
        setFieldError(field, 'この項目は必須です。');
        return false;
    }
    
    clearFieldError(field);
    return true;
}

/**
 * ロゴファイルのバリデーション
 */
function validateLogoFile(fileInput) {
    const file = fileInput.files[0];
    
    if (!file) return true;
    
    // ファイルサイズチェック（2MB）
    if (file.size > 2 * 1024 * 1024) {
        setFieldError(fileInput, 'ファイルサイズは2MB以下にしてください。');
        fileInput.value = '';
        return false;
    }
    
    // ファイルタイプチェック
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg'];
    if (!allowedTypes.includes(file.type)) {
        setFieldError(fileInput, 'PNG、JPG形式のファイルを選択してください。');
        fileInput.value = '';
        return false;
    }
    
    clearFieldError(fileInput);
    showAlert(`ロゴファイル選択完了: ${file.name} (${formatFileSize(file.size)})`, 'success');
    return true;
}

/**
 * フィールドエラー表示
 */
function setFieldError(field, message) {
    clearFieldError(field);
    
    field.classList.add('is-invalid');
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'invalid-feedback';
    errorDiv.textContent = message;
    errorDiv.setAttribute('data-error-for', field.id);
    
    field.parentNode.appendChild(errorDiv);
}

/**
 * フィールドエラークリア
 */
function clearFieldError(field) {
    field.classList.remove('is-invalid');
    
    const existingError = field.parentNode.querySelector(`[data-error-for="${field.id}"]`);
    if (existingError) {
        existingError.remove();
    }
}

/**
 * 電話番号フォーマット
 */
function formatPhoneNumber(field) {
    let value = field.value.replace(/[^\d-]/g, '');
    
    // 基本的なフォーマットチェック
    if (value.length > 0 && !value.match(/^\d{2,4}-\d{1,4}-\d{4}$/)) {
        // 自動フォーマット（簡易版）
        value = value.replace(/-/g, '');
        if (value.length >= 7) {
            if (value.length <= 10) {
                value = value.replace(/(\d{2,3})(\d{3,4})(\d{4})/, '$1-$2-$3');
            } else {
                value = value.replace(/(\d{2,4})(\d{3,4})(\d{4})/, '$1-$2-$3');
            }
        }
    }
    
    field.value = value;
}

/**
 * 郵便番号フォーマット
 */
function formatPostalCode(field) {
    let value = field.value.replace(/[^\d-]/g, '');
    
    // 7桁の数字の場合、自動的にハイフンを挿入
    if (value.length === 7 && !value.includes('-')) {
        value = value.replace(/(\d{3})(\d{4})/, '$1-$2');
    }
    
    field.value = value;
}

/**
 * メールアドレスバリデーション
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * URLバリデーション
 */
function isValidURL(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}