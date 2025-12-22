from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from typing import Dict, List, Optional
import os

class MysoukuTemplateGenerator:
    def __init__(self):
        self.page_width, self.page_height = A4
        self.margin = 20 * mm
        self.setup_fonts()
    
    def setup_fonts(self):
        """日本語フォント設定"""
        try:
            # システムフォントを登録（macOSの場合）
            font_paths = [
                '/System/Library/Fonts/ヒラギノ角ゴシック W3.otf',
                '/System/Library/Fonts/Helvetica.ttc',
                '/Library/Fonts/Arial.ttf'
            ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    if 'ヒラギノ' in font_path:
                        pdfmetrics.registerFont(TTFont('JapaneseFont', font_path))
                    break
        except:
            pass
    
    def generate_mysouku(self, property_data: Dict, company_data: Dict, output_path: str) -> bool:
        """マイソクPDF生成"""
        try:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                leftMargin=self.margin,
                rightMargin=self.margin,
                topMargin=self.margin,
                bottomMargin=self.margin
            )
            
            # スタイル設定
            styles = self._create_styles()
            
            # 要素リスト
            elements = []
            
            # ヘッダー部分
            elements.extend(self._create_header(company_data, styles))
            
            # 物件情報部分
            elements.extend(self._create_property_section(property_data, styles))
            
            # フッター部分
            elements.extend(self._create_footer(company_data, styles))
            
            # PDF生成
            doc.build(elements)
            return True
            
        except Exception as e:
            print(f"PDF生成エラー: {e}")
            return False
    
    def _create_styles(self) -> Dict:
        """スタイル作成"""
        styles = getSampleStyleSheet()
        
        # カスタムスタイル
        custom_styles = {
            'CompanyName': ParagraphStyle(
                'CompanyName',
                parent=styles['Heading1'],
                fontSize=16,
                textColor=colors.navy,
                alignment=1,  # 中央揃え
                spaceAfter=10
            ),
            'PropertyTitle': ParagraphStyle(
                'PropertyTitle',
                parent=styles['Heading2'],
                fontSize=14,
                textColor=colors.darkblue,
                spaceBefore=10,
                spaceAfter=8
            ),
            'PropertyInfo': ParagraphStyle(
                'PropertyInfo',
                parent=styles['Normal'],
                fontSize=10,
                spaceBefore=2,
                spaceAfter=2
            ),
            'ContactInfo': ParagraphStyle(
                'ContactInfo',
                parent=styles['Normal'],
                fontSize=9,
                textColor=colors.grey,
                alignment=1  # 中央揃え
            )
        }
        
        return custom_styles
    
    def _create_header(self, company_data: Dict, styles: Dict) -> List:
        """ヘッダー部分作成"""
        elements = []
        
        # 会社名
        company_name = company_data.get('company_name', '不動産会社')
        elements.append(Paragraph(company_name, styles['CompanyName']))
        
        # ロゴがある場合
        logo_path = company_data.get('logo_path')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image(logo_path, width=50*mm, height=20*mm)
                elements.append(logo)
            except:
                pass
        
        elements.append(Spacer(1, 10*mm))
        
        return elements
    
    def _create_property_section(self, property_data: Dict, styles: Dict) -> List:
        """物件情報セクション作成"""
        elements = []
        
        # 物件タイトル
        title = f"{property_data.get('property_type', '物件')} - {property_data.get('transaction_type', '')}"
        elements.append(Paragraph(title, styles['PropertyTitle']))
        
        # 基本情報テーブル
        basic_info_data = [
            ['価格・賃料', property_data.get('price', '要相談')],
            ['所在地', property_data.get('address', '')],
            ['交通', property_data.get('access', '')],
            ['間取り', property_data.get('floor_plan', '')],
            ['建物面積', property_data.get('building_area', '')],
            ['土地面積', property_data.get('land_area', '')],
            ['築年数', property_data.get('building_age', '')],
            ['構造', property_data.get('structure', '')],
            ['駐車場', property_data.get('parking', '')]
        ]
        
        # 空の項目を除外
        basic_info_data = [[k, v] for k, v in basic_info_data if v]
        
        if basic_info_data:
            basic_table = Table(basic_info_data, colWidths=[40*mm, 120*mm])
            basic_table.setStyle(TableStyle([
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
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3)
            ]))
            
            elements.append(basic_table)
            elements.append(Spacer(1, 5*mm))
        
        # 設備・特徴
        if property_data.get('features'):
            elements.append(Paragraph('設備・特徴', styles['PropertyTitle']))
            features_text = '、'.join(property_data['features'])
            elements.append(Paragraph(features_text, styles['PropertyInfo']))
            elements.append(Spacer(1, 5*mm))
        
        # その他費用
        if property_data.get('other_fees'):
            elements.append(Paragraph('その他費用', styles['PropertyTitle']))
            elements.append(Paragraph(property_data['other_fees'], styles['PropertyInfo']))
            elements.append(Spacer(1, 5*mm))
        
        return elements
    
    def _create_footer(self, company_data: Dict, styles: Dict) -> List:
        """フッター部分作成"""
        elements = []
        
        elements.append(Spacer(1, 10*mm))
        
        # 連絡先情報
        contact_info = []
        
        if company_data.get('address'):
            contact_info.append(f"住所: {company_data['address']}")
        
        if company_data.get('phone'):
            contact_info.append(f"TEL: {company_data['phone']}")
        
        if company_data.get('fax'):
            contact_info.append(f"FAX: {company_data['fax']}")
        
        if company_data.get('email'):
            contact_info.append(f"Email: {company_data['email']}")
        
        if company_data.get('license_number'):
            contact_info.append(f"免許番号: {company_data['license_number']}")
        
        # 連絡先テーブル
        if contact_info:
            contact_data = [[info] for info in contact_info]
            contact_table = Table(contact_data, colWidths=[160*mm])
            contact_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2)
            ]))
            
            elements.append(contact_table)
        
        return elements