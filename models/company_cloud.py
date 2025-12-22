import os
import json
import base64
from typing import Dict, Optional

class CompanyCloudModel:
    """
    Vercelサーバーレス環境対応の会社情報管理モデル
    環境変数を使用してデータを保存
    """
    
    def __init__(self):
        self.storage_key = 'COMPANY_DATA'
    
    def save_company_info(self, company_data: Dict) -> bool:
        """会社情報を環境変数として保存（開発用）"""
        try:
            # 本番環境では外部データベース（PostgreSQL、MongoDB等）を使用
            # 開発・デモ用として環境変数を使用
            data_json = json.dumps(company_data, ensure_ascii=False)
            
            # Base64エンコードして保存
            encoded_data = base64.b64encode(data_json.encode('utf-8')).decode('utf-8')
            
            # 実際の実装では外部ストレージ（Vercel KV、Supabase等）を使用
            self._save_to_storage(encoded_data)
            
            return True
            
        except Exception as e:
            print(f"データ保存エラー: {e}")
            return False
    
    def get_company_info(self) -> Optional[Dict]:
        """会社情報を取得"""
        try:
            encoded_data = self._load_from_storage()
            
            if not encoded_data:
                return None
            
            # Base64デコード
            data_json = base64.b64decode(encoded_data.encode('utf-8')).decode('utf-8')
            company_data = json.loads(data_json)
            
            return company_data
            
        except Exception as e:
            print(f"データ読み取りエラー: {e}")
            return None
    
    def _save_to_storage(self, data: str):
        """ストレージにデータ保存"""
        # 本番環境では以下のような外部ストレージを使用:
        # - Vercel KV (Redis互換)
        # - Supabase (PostgreSQL)
        # - MongoDB Atlas
        # - AWS DynamoDB
        
        # 開発・デモ用実装（実際には永続化されません）
        self._demo_storage = data
    
    def _load_from_storage(self) -> Optional[str]:
        """ストレージからデータ読み込み"""
        # デモ用のデフォルトデータを返す
        default_company = {
            'company_name': 'サンプル不動産株式会社',
            'company_name_kana': 'サンプルフドウサンカブシキガイシャ',
            'postal_code': '100-0001',
            'address': '東京都千代田区千代田1-1-1',
            'phone': '03-1234-5678',
            'fax': '03-1234-5679',
            'email': 'info@sample-realestate.co.jp',
            'website': 'https://sample-realestate.co.jp',
            'license_number': '東京都知事(1)第12345号',
            'representative_name': '山田太郎',
            'logo_data': '',
            'logo_filename': ''
        }
        
        # 本番環境用のストレージ読み込み処理
        if hasattr(self, '_demo_storage'):
            return self._demo_storage
        
        # デフォルトデータを返す
        data_json = json.dumps(default_company, ensure_ascii=False)
        return base64.b64encode(data_json.encode('utf-8')).decode('utf-8')

class VercelKVModel(CompanyCloudModel):
    """Vercel KV使用版（本番環境用）"""
    
    def __init__(self):
        super().__init__()
        # Vercel KVの設定
        self.kv_url = os.environ.get('KV_REST_API_URL')
        self.kv_token = os.environ.get('KV_REST_API_TOKEN')
    
    def _save_to_storage(self, data: str):
        """Vercel KVにデータ保存"""
        if not self.kv_url or not self.kv_token:
            print("Vercel KV設定が不足しています")
            return
        
        try:
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.kv_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.kv_url}/set/{self.storage_key}",
                headers=headers,
                json={"value": data}
            )
            
            response.raise_for_status()
            print("Vercel KVに保存完了")
            
        except Exception as e:
            print(f"Vercel KV保存エラー: {e}")
    
    def _load_from_storage(self) -> Optional[str]:
        """Vercel KVからデータ読み込み"""
        if not self.kv_url or not self.kv_token:
            return super()._load_from_storage()
        
        try:
            import requests
            
            headers = {
                'Authorization': f'Bearer {self.kv_token}'
            }
            
            response = requests.get(
                f"{self.kv_url}/get/{self.storage_key}",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('result')
            else:
                return super()._load_from_storage()
            
        except Exception as e:
            print(f"Vercel KV読み込みエラー: {e}")
            return super()._load_from_storage()

class SupabaseModel(CompanyCloudModel):
    """Supabase使用版（本番環境用）"""
    
    def __init__(self):
        super().__init__()
        self.supabase_url = os.environ.get('SUPABASE_URL')
        self.supabase_key = os.environ.get('SUPABASE_ANON_KEY')
    
    def _save_to_storage(self, data: str):
        """Supabaseにデータ保存"""
        if not self.supabase_url or not self.supabase_key:
            print("Supabase設定が不足しています")
            return
        
        try:
            import requests
            
            headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}',
                'Content-Type': 'application/json'
            }
            
            data_payload = {
                'id': 1,
                'company_data': data,
                'updated_at': 'now()'
            }
            
            response = requests.post(
                f"{self.supabase_url}/rest/v1/company_info",
                headers=headers,
                json=data_payload
            )
            
            response.raise_for_status()
            print("Supabaseに保存完了")
            
        except Exception as e:
            print(f"Supabase保存エラー: {e}")
    
    def _load_from_storage(self) -> Optional[str]:
        """Supabaseからデータ読み込み"""
        if not self.supabase_url or not self.supabase_key:
            return super()._load_from_storage()
        
        try:
            import requests
            
            headers = {
                'apikey': self.supabase_key,
                'Authorization': f'Bearer {self.supabase_key}'
            }
            
            response = requests.get(
                f"{self.supabase_url}/rest/v1/company_info?id=eq.1",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result and len(result) > 0:
                    return result[0].get('company_data')
            
            return super()._load_from_storage()
            
        except Exception as e:
            print(f"Supabase読み込みエラー: {e}")
            return super()._load_from_storage()

# 環境に応じてモデルを選択
def get_company_model():
    """環境変数に応じて適切なモデルを返す"""
    if os.environ.get('KV_REST_API_URL'):
        return VercelKVModel()
    elif os.environ.get('SUPABASE_URL'):
        return SupabaseModel()
    else:
        return CompanyCloudModel()