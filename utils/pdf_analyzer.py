import PyPDF2
import pdfplumber
import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional

class PDFAnalyzer:
    def __init__(self):
        self.extracted_data = {}
    
    def analyze_pdf(self, pdf_path: str) -> Dict:
        """メインのPDF解析メソッド"""
        try:
            # テキスト抽出を試行
            text_data = self._extract_text_with_pdfplumber(pdf_path)
            
            if not text_data or len(text_data.strip()) < 100:
                # テキストが少ない場合はOCRも併用
                ocr_data = self._extract_with_ocr(pdf_path)
                text_data += "\n" + ocr_data
            
            # 構造化データ抽出
            structured_data = self._parse_mysouku_data(text_data)
            
            return {
                "success": True,
                "raw_text": text_data,
                "structured_data": structured_data
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_text_with_pdfplumber(self, pdf_path: str) -> str:
        """pdfplumberを使用したテキスト抽出"""
        text = ""
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text
    
    def _extract_with_ocr(self, pdf_path: str) -> str:
        """OCRを使用したテキスト抽出"""
        try:
            # PDFを画像に変換してOCR
            doc = fitz.open(pdf_path)
            text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap()
                img_data = pix.tobytes("ppm")
                
                # OpenCVで画像処理
                nparr = np.frombuffer(img_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                # OCR実行
                ocr_text = pytesseract.image_to_string(image, lang='jpn')
                text += ocr_text + "\n"
            
            doc.close()
            return text
            
        except Exception as e:
            print(f"OCR処理エラー: {e}")
            return ""
    
    def _parse_mysouku_data(self, text: str) -> Dict:
        """マイソクテキストから構造化データを抽出"""
        data = {
            "property_type": "",      # 物件種別
            "transaction_type": "",   # 賃貸/売買
            "price": "",             # 価格・賃料
            "address": "",           # 所在地
            "access": "",            # 交通
            "building_area": "",     # 建物面積
            "land_area": "",         # 土地面積
            "floor_plan": "",        # 間取り
            "building_age": "",      # 築年数
            "structure": "",         # 構造
            "parking": "",           # 駐車場
            "other_fees": "",        # その他費用
            "contact": "",           # 連絡先
            "features": [],          # 設備・特徴
        }
        
        # 各項目のパターンマッチング
        patterns = {
            "price": [
                r"賃料[：:]\s*([0-9,]+万円)",
                r"価格[：:]\s*([0-9,]+万円)",
                r"([0-9,]+万円)",
            ],
            "address": [
                r"所在地[：:]\s*(.+?)(?=\n|交通)",
                r"住所[：:]\s*(.+?)(?=\n)",
            ],
            "access": [
                r"交通[：:]\s*(.+?)(?=\n|建物)",
                r"最寄り駅[：:]\s*(.+?)(?=\n)",
            ],
            "building_area": [
                r"建物面積[：:]\s*([0-9.]+㎡)",
                r"専有面積[：:]\s*([0-9.]+㎡)",
            ],
            "land_area": [
                r"土地面積[：:]\s*([0-9.]+㎡)",
            ],
            "floor_plan": [
                r"間取り[：:]\s*([0-9][LDK]+)",
                r"([0-9][LDK]+)",
            ],
            "building_age": [
                r"築年数[：:]\s*([0-9]+年)",
                r"築[：:]\s*([0-9]+年)",
            ],
            "structure": [
                r"構造[：:]\s*(.+?)(?=\n)",
            ],
            "parking": [
                r"駐車場[：:]\s*(.+?)(?=\n)",
            ]
        }
        
        # パターンマッチングでデータ抽出
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data[key] = match.group(1).strip()
                    break
        
        # 物件種別の判定
        if "マンション" in text:
            data["property_type"] = "マンション"
        elif "アパート" in text:
            data["property_type"] = "アパート"
        elif "一戸建て" in text or "戸建" in text:
            data["property_type"] = "戸建て"
        elif "土地" in text:
            data["property_type"] = "土地"
        
        # 取引種別の判定
        if "賃料" in text or "家賃" in text:
            data["transaction_type"] = "賃貸"
        elif "価格" in text or "売買" in text:
            data["transaction_type"] = "売買"
        
        # 設備・特徴を抽出
        features_keywords = [
            "エアコン", "バス・トイレ別", "オートロック", "宅配ボックス",
            "ペット可", "駐輪場", "エレベーター", "バルコニー", "フローリング",
            "都市ガス", "プロパンガス", "IHクッキングヒーター", "システムキッチン"
        ]
        
        for keyword in features_keywords:
            if keyword in text:
                data["features"].append(keyword)
        
        return data