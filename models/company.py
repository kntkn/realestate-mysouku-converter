import sqlite3
import json
from typing import Dict, Optional

class CompanyModel:
    def __init__(self, db_path: str = "company.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """データベース初期化"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS company_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                company_name_kana TEXT,
                postal_code TEXT,
                address TEXT,
                phone TEXT,
                fax TEXT,
                email TEXT,
                website TEXT,
                license_number TEXT,
                representative_name TEXT,
                logo_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS template_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name TEXT NOT NULL,
                layout_settings TEXT,
                color_scheme TEXT,
                font_settings TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_company_info(self, company_data: Dict) -> bool:
        """会社情報を保存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 既存データがある場合は更新、なければ新規作成
            existing = self.get_company_info()
            
            if existing:
                cursor.execute('''
                    UPDATE company_info SET
                        company_name = ?,
                        company_name_kana = ?,
                        postal_code = ?,
                        address = ?,
                        phone = ?,
                        fax = ?,
                        email = ?,
                        website = ?,
                        license_number = ?,
                        representative_name = ?,
                        logo_path = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                ''', (
                    company_data.get('company_name', ''),
                    company_data.get('company_name_kana', ''),
                    company_data.get('postal_code', ''),
                    company_data.get('address', ''),
                    company_data.get('phone', ''),
                    company_data.get('fax', ''),
                    company_data.get('email', ''),
                    company_data.get('website', ''),
                    company_data.get('license_number', ''),
                    company_data.get('representative_name', ''),
                    company_data.get('logo_path', '')
                ))
            else:
                cursor.execute('''
                    INSERT INTO company_info (
                        company_name, company_name_kana, postal_code, address,
                        phone, fax, email, website, license_number,
                        representative_name, logo_path
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    company_data.get('company_name', ''),
                    company_data.get('company_name_kana', ''),
                    company_data.get('postal_code', ''),
                    company_data.get('address', ''),
                    company_data.get('phone', ''),
                    company_data.get('fax', ''),
                    company_data.get('email', ''),
                    company_data.get('website', ''),
                    company_data.get('license_number', ''),
                    company_data.get('representative_name', ''),
                    company_data.get('logo_path', '')
                ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"データベース保存エラー: {e}")
            return False
    
    def get_company_info(self) -> Optional[Dict]:
        """会社情報を取得"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM company_info LIMIT 1')
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return {
                    'id': row[0],
                    'company_name': row[1],
                    'company_name_kana': row[2],
                    'postal_code': row[3],
                    'address': row[4],
                    'phone': row[5],
                    'fax': row[6],
                    'email': row[7],
                    'website': row[8],
                    'license_number': row[9],
                    'representative_name': row[10],
                    'logo_path': row[11],
                    'created_at': row[12],
                    'updated_at': row[13]
                }
            
            return None
            
        except Exception as e:
            print(f"データベース読み取りエラー: {e}")
            return None
    
    def save_template_settings(self, template_name: str, settings: Dict) -> bool:
        """テンプレート設定を保存"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO template_settings (
                    template_name, layout_settings, color_scheme, font_settings
                ) VALUES (?, ?, ?, ?)
            ''', (
                template_name,
                json.dumps(settings.get('layout', {})),
                json.dumps(settings.get('colors', {})),
                json.dumps(settings.get('fonts', {}))
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            print(f"テンプレート設定保存エラー: {e}")
            return False
    
    def get_template_settings(self, template_name: str) -> Optional[Dict]:
        """テンプレート設定を取得"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT * FROM template_settings WHERE template_name = ?',
                (template_name,)
            )
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return {
                    'template_name': row[1],
                    'layout': json.loads(row[2]) if row[2] else {},
                    'colors': json.loads(row[3]) if row[3] else {},
                    'fonts': json.loads(row[4]) if row[4] else {}
                }
            
            return None
            
        except Exception as e:
            print(f"テンプレート設定読み取りエラー: {e}")
            return None