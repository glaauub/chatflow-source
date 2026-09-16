# -*- coding: utf-8 -*-
"""站点生成器（板块化 + 京东式详情页 + SEO/GEO + 自定义页面 + 版本快照）
生成结构：
  output_site/
  ├── index.html            # 首页（按 sections 顺序渲染板块）
  ├── contact.html          # Contact Us 页
  ├── page_<slug>.html      # 自定义页面（About/FAQ 等）
  ├── product_<id>.html     # 产品详情页（京东式排版）
  ├── style.css             # 所选模板样式
  ├── sitemap.xml           # SEO
  ├── robots.txt            # SEO
  └── static/uploads/       # 图片资源

page 参数：'index' 生成静态站（相对文件链接）；'preview' 后台预览（Flask 路由链接）
"""
import html
import json
import os
import re
import shutil
from datetime import datetime
from urllib.parse import quote, urljoin, urlsplit
from visibility import plain_text, valid_site_url, audit_output, write_manifest

from models import get_db, get_config, set_config, get_all_config
from site_themes import build_css, get_template

from runtime_paths import BUNDLE_DIR as BASE_DIR, DATA_DIR
# 上传图片/生成站点 → 可写数据目录；内置支付图标 → 程序只读资源
UPLOAD_DIR = os.path.join(DATA_DIR, 'static', 'uploads')
OUTPUT_DIR = os.path.join(DATA_DIR, 'output_site')

CONTACT_ICONS = {
    'WhatsApp': '📱', '微信': '💬', '电话': '📞', 'QQ': '🐧',
    'Email': '✉️', 'Telegram': '✈️', 'Skype': '💠', 'LINE': '💬',
    'Facebook': '📘', 'Instagram': '📷', 'YouTube': '▶️', 'TikTok': '🎵',
    'LinkedIn': '💼', 'Website': '🌐', 'Address': '📍', 'AliTrade': '🛒',
    'Trademanager': '🤝',
}

# ---------------- 联系方式统一渠道定义（前台美观直达渲染） ----------------
# 作用：把后台各种写法（中文/英文/别名）规范成统一品牌标识 + 官方品牌色 + 直达动作，
# 输出为统一的「图标徽章 + 品牌名 + 直达按钮」结构，杜绝同一号码文本在多处重复堆叠。
CONTACT_STD = {
    'whatsapp': {'label': 'WhatsApp',  'color': '#25D366', 'verb': 'Chat',   'short': 'WA'},
    'phone':    {'label': 'Phone',     'color': '#1a73e8', 'verb': 'Call',   'short': 'PH'},
    'tel':      {'label': 'Phone',     'color': '#1a73e8', 'verb': 'Call',   'short': 'PH'},
    '电话':      {'label': 'Phone',     'color': '#1a73e8', 'verb': 'Call',   'short': 'PH'},
    'email':    {'label': 'Email',     'color': '#ea4335', 'verb': 'Email',  'short': '@'},
    'wechat':   {'label': 'WeChat',    'color': '#07C160', 'verb': '',       'short': 'WX'},
    '微信':      {'label': 'WeChat',    'color': '#07C160', 'verb': '',       'short': 'WX'},
    'telegram': {'label': 'Telegram',  'color': '#2AABEE', 'verb': 'Chat',   'short': 'TG'},
    'skype':    {'label': 'Skype',     'color': '#00AFF0', 'verb': 'Chat',   'short': 'SK'},
    'line':     {'label': 'LINE',      'color': '#06C755', 'verb': 'Chat',   'short': 'LI'},
    'facebook': {'label': 'Facebook',  'color': '#1877F2', 'verb': 'Follow', 'short': 'f'},
    'instagram': {'label': 'Instagram', 'color': '#E1306C', 'verb': 'Follow', 'short': 'IG'},
    'youtube':  {'label': 'YouTube',   'color': '#FF0000', 'verb': 'Watch',  'short': 'YT'},
    'tiktok':   {'label': 'TikTok',    'color': '#111111', 'verb': 'Follow', 'short': 'TT'},
    'linkedin': {'label': 'LinkedIn',  'color': '#0A66C2', 'verb': 'Follow', 'short': 'in'},
    'twitter':  {'label': 'X / Twitter', 'color': '#000000', 'verb': 'Follow', 'short': 'X'},
    'x':        {'label': 'X / Twitter', 'color': '#000000', 'verb': 'Follow', 'short': 'X'},
    'website':  {'label': 'Website',   'color': '#0f766e', 'verb': 'Visit',  'short': 'WWW'},
    'address':  {'label': 'Address',   'color': '#64748b', 'verb': '',       'short': 'ADD'},
    'qq':       {'label': 'QQ',        'color': '#12B7F5', 'verb': '',       'short': 'QQ'},
    'alitrade': {'label': 'AliTrade',  'color': '#ff6a00', 'verb': 'Visit',  'short': 'AT'},
    'trademanager': {'label': 'TradeManager', 'color': '#ff6a00', 'verb': 'Chat', 'short': 'TM'},
}
CONTACT_STD_KEYS = list(CONTACT_STD.keys())
_CONTACT_STD_LOW = {k.lower(): v for k, v in CONTACT_STD.items()}


def _contact_std_key(ct):
    """把后台填写的类型名归一化为 CONTACT_STD 中的小写键；未知返回 ''"""
    c = str(ct or '').strip().lower()
    if not c:
        return ''
    if c in _CONTACT_STD_LOW:
        return c
    # 兼容带空格/常见变体
    c2 = c.replace(' ', '').replace('-', '').replace('_', '')
    for k, v in _CONTACT_STD_LOW.items():
        if k.replace(' ', '').replace('-', '').replace('_', '') == c2:
            return k
    # WhatsApp 号码 / whatsapp number 等
    if c2 in ('whatsappnumber', 'whatsapp号码', 'wa'):
        return 'whatsapp'
    if c2 in ('phonenumber', '电话号码', 'mobile', 'cellphone', 'cell'):
        return 'phone'
    if c2 in ('emailaddress', '邮箱', 'e-mail', 'e-mailaddress', 'mail'):
        return 'email'
    if c2 in ('wechatid', 'wechatid', '微信号'):
        return 'wechat'
    if c2 in ('lineid',):
        return 'line'
    if c2 in ('skypeid',):
        return 'skype'
    if c2 == 'qq':
        return 'qq'
    return ''


def _contact_std_lookup(ct, value):
    """返回 (std_key, std_def)；未知类型按值智能识别类型"""
    k = _contact_std_key(ct)
    if k:
        return k, CONTACT_STD[k]
    v = str(value or '').strip()
    if v.startswith(('http://', 'https://')):
        return 'website', CONTACT_STD['website']
    if '@' in v and '.' in v.split('@')[-1]:
        return 'email', CONTACT_STD['email']
    if re.fullmatch(r'\+?[\d][\d\s\-()]{4,}', v):
        return 'phone', CONTACT_STD['phone']
    return '', None

# ---------------- 多平台详情页风格库 ----------------
# id: 风格标识；name: 中文名；en: 英文名；desc: 说明；default: 主色
DETAIL_LAYOUTS = [
    {'id': 'amazon',    'name': 'Amazon 亚马逊',      'en': 'Amazon',        'color': '#f0c14b', 'desc': '左图右信息 · 星级评分 · 黄色 Add to Cart 按钮 · bullet 卖点'},
    {'id': 'taobao',    'name': '淘宝 Taobao',       'en': 'Taobao',        'color': '#ff5000', 'desc': '左图右信息 · 红色价格 · 橙色购买按钮 · 店铺模块'},
    {'id': 'jd',        'name': '京东 JD',           'en': 'JD.com',        'color': '#e1251b', 'desc': '顶部服务条 · 京东红 · 参数 Tab · 价格红'},
    {'id': 'pdd',       'name': '拼多多 Pinduoduo',   'en': 'Pinduoduo',     'color': '#e02e24', 'desc': '拼团氛围 · 红色价格 · 橙红按钮 · 销量进度'},
    {'id': 'alibaba',   'name': 'Alibaba / 1688',    'en': 'Alibaba',       'color': '#ff6a00', 'desc': 'B2B 询盘 · 贸易保障 · MOQ · 橙蓝配色'},
    {'id': 'shopee',    'name': 'Shopee 虾皮',        'en': 'Shopee',        'color': '#ee4d2d', 'desc': '橙色系 · 免运标签 · 直购按钮 · 热卖感'},
    {'id': 'rakuten',   'name': 'Rakuten 乐天',       'en': 'Rakuten',       'color': '#bf0000', 'desc': '日系红白 · 商品编号 · 加购按钮 · 配送说明'},
    {'id': 'ebay',      'name': 'eBay',              'en': 'eBay',          'color': '#e53238', 'desc': '蓝黄配色 · Buy It Now · 卖家信息 · 多色价格'},
    {'id': 'walmart',   'name': 'Walmart',           'en': 'Walmart',       'color': '#0071dc', 'desc': '蓝色系 · Rollback 价格 · 蓝色按钮 · 简单直购'},
    {'id': 'etsy',      'name': 'Etsy',              'en': 'Etsy',          'color': '#f1641e', 'desc': '手作风 · 橙色按钮 · 复古卡片 · 评价展示'},
    {'id': 'minimal',   'name': '极简自建站 Minimal', 'en': 'Minimal',       'color': '#111111', 'desc': '黑白极简 · 大留白 · 无边框 · 高级感'},
    {'id': 'classic',   'name': '经典商务 Classic',   'en': 'Classic',       'color': '#2563eb', 'desc': '稳重蓝 · 通用商务 · 左图右信息 · 保守排版'},
]

# ---------------- 多语言包（>=10 种） ----------------
# 键位说明：nav_home/nav_products/nav_contact 导航；btn_* 按钮；sec_* 板块标题；inq_* 询盘；ck_* Cookie；seo_* SEO 文案
I18N = {
    'en': {
        'lang_name': 'English', 'html_lang': 'en',
        'nav_home': 'Home', 'nav_products': 'Products', 'nav_contact': 'Contact Us', 'nav_about': 'About',
        'btn_inquire': 'Inquire Now', 'btn_buy': 'Buy Now', 'btn_add_cart': 'Add to Cart', 'btn_send': 'Send',
        'sec_products': 'Our Products', 'sec_about': 'About Us', 'sec_contact': 'Contact Us',
        'related_products': 'Related Products', 'detail_specs': 'Product Details', 'detail_desc': 'Description',
        'detail_shipping': 'Shipping & Payment', 'detail_video': 'Product Video',
        'attr_sku': 'SKU', 'attr_model': 'Model', 'attr_spec': 'Specification', 'attr_category': 'Category',
        'attr_stock': 'Availability', 'in_stock': 'In Stock', 'out_stock': 'Out of Stock',
        'inq_title': 'Send Inquiry', 'inq_sub': 'Fill in the form and we will reply within 24 hours.',
        'inq_name': 'Your Name', 'inq_email': 'Your Email', 'inq_country': 'Country',
        'inq_message': 'Message', 'inq_placeholder': 'Tell us your requirements (quantity, customization, etc.)',
        'inq_success': 'Your inquiry has been sent successfully. We will contact you soon!',
        'inq_required': 'Please fill in name, email and message.',
        'ck_text': 'We use cookies to improve your experience and analyze site traffic. By continuing, you agree to our Cookie Policy.',
        'ck_accept': 'Accept', 'ck_decline': 'Decline',
        'btn_view': 'View Details', 'in_stock_short': 'In Stock', 'out_stock_short': 'Out of Stock',
        'seo_desc_default': 'Professional factory & supplier - high quality products with OEM/ODM service worldwide.',
        'seo_default_title': 'Professional Manufacturer & Supplier - Quality Products at Factory Price',
        'seo_default_desc': 'We are a professional factory and supplier, offering high quality products with OEM/ODM service worldwide.',
        'copyright': 'All Rights Reserved.',
    },
    'zh': {
        'lang_name': '简体中文', 'html_lang': 'zh-CN',
        'nav_home': '首页', 'nav_products': '产品中心', 'nav_contact': '联系我们', 'nav_about': '关于我们',
        'btn_inquire': '立即询盘', 'btn_buy': '立即购买', 'btn_add_cart': '加入购物车', 'btn_send': '发送',
        'sec_products': '我们的产品', 'sec_about': '关于我们', 'sec_contact': '联系我们',
        'related_products': '相关产品', 'detail_specs': '产品参数', 'detail_desc': '产品详情',
        'detail_shipping': '配送与支付', 'detail_video': '产品视频',
        'attr_sku': '库存编码', 'attr_model': '型号', 'attr_spec': '规格', 'attr_category': '分类',
        'attr_stock': '库存状态', 'in_stock': '有货', 'out_stock': '缺货',
        'inq_title': '在线询盘', 'inq_sub': '填写表单，我们将在 24 小时内回复您。',
        'inq_name': '您的姓名', 'inq_email': '您的邮箱', 'inq_country': '国家/地区',
        'inq_message': '留言内容', 'inq_placeholder': '请描述您的需求（数量、定制要求等）',
        'inq_success': '询盘提交成功，我们会尽快与您联系！',
        'inq_required': '请填写姓名、邮箱和留言内容。',
        'ck_text': '我们使用 Cookie 来改善您的访问体验并分析流量。继续浏览即表示您同意我们的 Cookie 政策。',
        'ck_accept': '同意', 'ck_decline': '拒绝',
        'btn_view': '查看详情', 'in_stock_short': '有货', 'out_stock_short': '缺货',
        'seo_desc_default': '专业制造商与供应商 - 工厂价优质产品',
        'seo_default_title': '专业制造商与供应商 - 工厂价优质产品',
        'seo_default_desc': '我们是一家专业工厂与供应商，面向全球提供高品质产品与 OEM/ODM 服务。',
        'copyright': '版权所有。',
    },
    'zh-Hant': {
        'lang_name': '繁體中文（香港/澳門）', 'html_lang': 'zh-Hant',
        'nav_home': '首頁', 'nav_products': '產品中心', 'nav_contact': '聯絡我們', 'nav_about': '關於我們',
        'btn_inquire': '立即詢盤', 'btn_buy': '立即購買', 'btn_add_cart': '加入購物車', 'btn_send': '發送',
        'sec_products': '我們的產品', 'sec_about': '關於我們', 'sec_contact': '聯絡我們',
        'related_products': '相關產品', 'detail_specs': '產品參數', 'detail_desc': '產品詳情',
        'detail_shipping': '配送與支付', 'detail_video': '產品影片',
        'attr_sku': '庫存編碼', 'attr_model': '型號', 'attr_spec': '規格', 'attr_category': '分類',
        'attr_stock': '庫存狀態', 'in_stock': '有貨', 'out_stock': '缺貨',
        'inq_title': '線上詢盤', 'inq_sub': '填寫表單，我們將於 24 小時內回覆您。',
        'inq_name': '您的姓名', 'inq_email': '您的郵箱', 'inq_country': '國家/地區',
        'inq_message': '留言內容', 'inq_placeholder': '請描述您的需求（數量、訂製要求等）',
        'inq_success': '詢盤提交成功，我們會盡快與您聯絡！',
        'inq_required': '請填寫姓名、郵箱和留言內容。',
        'ck_text': '我們使用 Cookie 來改善您的瀏覽體驗並分析流量。繼續瀏覽即表示您同意我們的 Cookie 政策。',
        'ck_accept': '同意', 'ck_decline': '拒絕',
        'btn_view': '查看詳情', 'in_stock_short': '有貨', 'out_stock_short': '缺貨',
        'seo_desc_default': '專業製造商與供應商 - 工廠價優質產品',
        'seo_default_title': '專業製造商與供應商 - 工廠價優質產品',
        'seo_default_desc': '我們是一家專業工廠與供應商，面向全球提供高品質產品與 OEM/ODM 服務。',
        'copyright': '版權所有。',
    },
    'ja': {
        'inq_direct': 'または直接お問い合わせ：',
        'inq_direct_title': '直接お問い合わせ',
        'inq_direct_sub': 'すぐにご連絡をご希望ですか？下記までどうぞ：',
        'lang_name': '日本語', 'html_lang': 'ja',
        'nav_home': 'ホーム', 'nav_products': '製品', 'nav_contact': 'お問い合わせ', 'nav_about': '会社概要',
        'btn_inquire': 'お問い合わせ', 'btn_buy': '今すぐ購入', 'btn_add_cart': 'カートに入れる', 'btn_send': '送信',
        'sec_products': '製品紹介', 'sec_about': '会社概要', 'sec_contact': 'お問い合わせ',
        'related_products': '関連製品', 'detail_specs': '製品仕様', 'detail_desc': '製品詳細',
        'detail_shipping': '配送と支払い', 'detail_video': '製品動画',
        'attr_sku': 'SKU', 'attr_model': '型番', 'attr_spec': '仕様', 'attr_category': 'カテゴリ',
        'attr_stock': '在庫状況', 'in_stock': '在庫あり', 'out_stock': '在庫なし',
        'inq_title': 'お問い合わせ', 'inq_sub': 'フォームにご記入ください。24時間以内に返信いたします。',
        'inq_name': 'お名前', 'inq_email': 'メールアドレス', 'inq_country': '国・地域',
        'inq_message': 'メッセージ', 'inq_placeholder': 'ご要望（数量・カスタマイズ等）をご記入ください',
        'inq_success': 'お問い合わせを送信しました。まもなくご連絡いたします。',
        'inq_required': 'お名前・メール・メッセージを入力してください。',
        'ck_text': '当サイトではアクセス解析と利便性向上のためCookieを使用しています。継続して閲覧することでCookieの使用に同意したものとみなされます。',
        'ck_accept': '同意する', 'ck_decline': '拒否',
        'btn_view': '詳細を見る', 'in_stock_short': '在庫あり', 'out_stock_short': '在庫切れ',
        'seo_desc_default': 'プロフェッショナルメーカー・サプライヤー - 工場価格の高品質製品',
        'seo_default_title': 'プロフェッショナルメーカー・サプライヤー - 工場価格の高品質製品',
        'seo_default_desc': '当社はプロフェッショナルな工場・サプライヤーとして、世界中に高品質製品とOEM/ODMサービスを提供しています。',
        'copyright': 'All Rights Reserved.',
    },
    'ko': {
        'inq_direct': '또는 직접 문의하세요:',
        'inq_direct_title': '직접 문의하기',
        'inq_direct_sub': '빠른 연락을 원하시나요? 아래 방법으로 연락주세요:',
        'lang_name': '한국어', 'html_lang': 'ko',
        'nav_home': '홈', 'nav_products': '제품', 'nav_contact': '문의하기', 'nav_about': '회사소개',
        'btn_inquire': '문의하기', 'btn_buy': '바로구매', 'btn_add_cart': '장바구니 담기', 'btn_send': '보내기',
        'sec_products': '우리 제품', 'sec_about': '회사소개', 'sec_contact': '문의하기',
        'related_products': '관련 제품', 'detail_specs': '제품 사양', 'detail_desc': '제품 상세',
        'detail_shipping': '배송 및 결제', 'detail_video': '제품 비디오',
        'attr_sku': 'SKU', 'attr_model': '모델', 'attr_spec': '규격', 'attr_category': '카테고리',
        'attr_stock': '재고', 'in_stock': '재고 있음', 'out_stock': '재고 없음',
        'inq_title': '문의하기', 'inq_sub': '양식을 작성하시면 24시간 내에 답변드리겠습니다.',
        'inq_name': '이름', 'inq_email': '이메일', 'inq_country': '국가',
        'inq_message': '메시지', 'inq_placeholder': '요구사항(수량, 커스텀 등)을 적어주세요',
        'inq_success': '문의가 성공적으로 전송되었습니다. 곧 연락드리겠습니다!',
        'inq_required': '이름, 이메일, 메시지를 입력해주세요.',
        'ck_text': '당사는 이용자 경험 개선과 트래픽 분석을 위해 쿠키를 사용합니다. 계속 탐색하면 쿠키 정책에 동의한 것으로 간주됩니다.',
        'ck_accept': '동의', 'ck_decline': '거부',
        'btn_view': '상세보기', 'in_stock_short': '재고 있음', 'out_stock_short': '품절',
        'seo_desc_default': '전문 제조업체 및 공급업체 - 공장가 고품질 제품',
        'seo_default_title': '전문 제조업체 및 공급업체 - 공장가 고품질 제품',
        'seo_default_desc': '저희는 고품질 제품과 OEM/ODM 서비스를 전 세계에 제공하는 전문 공장 및 공급업체입니다.',
        'copyright': 'All Rights Reserved.',
    },
    'de': {
        'inq_direct': 'Oder kontaktieren Sie uns direkt:',
        'inq_direct_title': 'Kontaktieren Sie uns direkt',
        'inq_direct_sub': 'Schneller Kontakt? Erreichen Sie uns über:',
        'lang_name': 'Deutsch', 'html_lang': 'de',
        'nav_home': 'Startseite', 'nav_products': 'Produkte', 'nav_contact': 'Kontakt', 'nav_about': 'Über uns',
        'btn_inquire': 'Anfragen', 'btn_buy': 'Jetzt kaufen', 'btn_add_cart': 'In den Warenkorb', 'btn_send': 'Senden',
        'sec_products': 'Unsere Produkte', 'sec_about': 'Über uns', 'sec_contact': 'Kontakt',
        'related_products': 'Ähnliche Produkte', 'detail_specs': 'Produktdetails', 'detail_desc': 'Beschreibung',
        'detail_shipping': 'Versand & Zahlung', 'detail_video': 'Produktvideo',
        'attr_sku': 'SKU', 'attr_model': 'Modell', 'attr_spec': 'Spezifikation', 'attr_category': 'Kategorie',
        'attr_stock': 'Verfügbarkeit', 'in_stock': 'Auf Lager', 'out_stock': 'Nicht auf Lager',
        'inq_title': 'Anfrage senden', 'inq_sub': 'Füllen Sie das Formular aus, wir antworten innerhalb von 24 Stunden.',
        'inq_name': 'Ihr Name', 'inq_email': 'Ihre E-Mail', 'inq_country': 'Land',
        'inq_message': 'Nachricht', 'inq_placeholder': 'Teilen Sie uns Ihre Anforderungen mit (Menge, Anpassung usw.)',
        'inq_success': 'Ihre Anfrage wurde erfolgreich gesendet. Wir melden uns bald!',
        'inq_required': 'Bitte Name, E-Mail und Nachricht ausfüllen.',
        'ck_text': 'Wir verwenden Cookies, um Ihr Erlebnis zu verbessern und den Verkehr zu analysieren. Durch Fortfahren stimmen Sie unserer Cookie-Richtlinie zu.',
        'ck_accept': 'Akzeptieren', 'ck_decline': 'Ablehnen',
        'btn_view': 'Details ansehen', 'in_stock_short': 'Auf Lager', 'out_stock_short': 'Ausverkauft',
        'seo_desc_default': 'Professioneller Hersteller & Lieferant - Qualitätsprodukte zum Fabrikpreis',
        'seo_default_title': 'Professioneller Hersteller & Lieferant - Qualitätsprodukte zum Fabrikpreis',
        'seo_default_desc': 'Wir sind eine professionelle Fabrik und Lieferant, bieten weltweit Qualitätsprodukte und OEM/ODM-Service.',
        'copyright': 'Alle Rechte vorbehalten.',
    },
    'es': {
        'inq_direct': 'O contáctenos directamente:',
        'inq_direct_title': 'Contáctenos directamente',
        'inq_direct_sub': '¿Prefiere contacto inmediato? Escríbanos por:',
        'lang_name': 'Español', 'html_lang': 'es',
        'nav_home': 'Inicio', 'nav_products': 'Productos', 'nav_contact': 'Contacto', 'nav_about': 'Nosotros',
        'btn_inquire': 'Consultar', 'btn_buy': 'Comprar ahora', 'btn_add_cart': 'Añadir al carrito', 'btn_send': 'Enviar',
        'sec_products': 'Nuestros Productos', 'sec_about': 'Sobre Nosotros', 'sec_contact': 'Contacto',
        'related_products': 'Productos Relacionados', 'detail_specs': 'Detalles del Producto', 'detail_desc': 'Descripción',
        'detail_shipping': 'Envío y Pago', 'detail_video': 'Video del Producto',
        'attr_sku': 'SKU', 'attr_model': 'Modelo', 'attr_spec': 'Especificación', 'attr_category': 'Categoría',
        'attr_stock': 'Disponibilidad', 'in_stock': 'En stock', 'out_stock': 'Sin stock',
        'inq_title': 'Enviar Consulta', 'inq_sub': 'Complete el formulario, le responderemos en 24 horas.',
        'inq_name': 'Su Nombre', 'inq_email': 'Su Email', 'inq_country': 'País',
        'inq_message': 'Mensaje', 'inq_placeholder': 'Cuéntenos sus requisitos (cantidad, personalización, etc.)',
        'inq_success': 'Su consulta fue enviada con éxito. ¡Nos pondremos en contacto pronto!',
        'inq_required': 'Por favor complete nombre, email y mensaje.',
        'ck_text': 'Usamos cookies para mejorar su experiencia y analizar el tráfico. Al continuar, acepta nuestra Política de Cookies.',
        'ck_accept': 'Aceptar', 'ck_decline': 'Rechazar',
        'btn_view': 'Ver detalles', 'in_stock_short': 'En stock', 'out_stock_short': 'Agotado',
        'seo_desc_default': 'Fabricante y Proveedor Profesional - Productos de Calidad a Precio de Fábrica',
        'seo_default_title': 'Fabricante y Proveedor Profesional - Productos de Calidad a Precio de Fábrica',
        'seo_default_desc': 'Somos una fábrica y proveedor profesional que ofrece productos de alta calidad con servicio OEM/ODM en todo el mundo.',
        'copyright': 'Todos los derechos reservados.',
    },
    'ru': {
        'inq_direct': 'Или свяжитесь с нами напрямую:',
        'inq_direct_title': 'Свяжитесь с нами напрямую',
        'inq_direct_sub': 'Хотите быстрой связи? Напишите нам через:',
        'lang_name': 'Русский', 'html_lang': 'ru',
        'nav_home': 'Главная', 'nav_products': 'Товары', 'nav_contact': 'Контакты', 'nav_about': 'О нас',
        'btn_inquire': 'Запросить', 'btn_buy': 'Купить сейчас', 'btn_add_cart': 'В корзину', 'btn_send': 'Отправить',
        'sec_products': 'Наши товары', 'sec_about': 'О нас', 'sec_contact': 'Контакты',
        'related_products': 'Похожие товары', 'detail_specs': 'Характеристики', 'detail_desc': 'Описание',
        'detail_shipping': 'Доставка и оплата', 'detail_video': 'Видео товара',
        'attr_sku': 'Артикул', 'attr_model': 'Модель', 'attr_spec': 'Спецификация', 'attr_category': 'Категория',
        'attr_stock': 'Наличие', 'in_stock': 'В наличии', 'out_stock': 'Нет в наличии',
        'inq_title': 'Отправить запрос', 'inq_sub': 'Заполните форму, мы ответим в течение 24 часов.',
        'inq_name': 'Ваше имя', 'inq_email': 'Ваш email', 'inq_country': 'Страна',
        'inq_message': 'Сообщение', 'inq_placeholder': 'Расскажите о ваших требованиях (количество, кастомизация и т.д.)',
        'inq_success': 'Ваш запрос успешно отправлен. Мы скоро свяжемся с вами!',
        'inq_required': 'Пожалуйста, заполните имя, email и сообщение.',
        'ck_text': 'Мы используем файлы cookie для улучшения работы сайта и анализа трафика. Продолжая, вы соглашаетесь с нашей Политикой cookie.',
        'ck_accept': 'Принять', 'ck_decline': 'Отклонить',
        'btn_view': 'Подробнее', 'in_stock_short': 'В наличии', 'out_stock_short': 'Нет в наличии',
        'seo_desc_default': 'Профессиональный производитель и поставщик - качественная продукция по заводской цене',
        'seo_default_title': 'Профессиональный производитель и поставщик - качественная продукция по заводской цене',
        'seo_default_desc': 'Мы профессиональная фабрика и поставщик, предлагаем высококачественную продукцию и OEM/ODM услуги по всему миру.',
        'copyright': 'Все права защищены.',
    },
    'fr': {
        'inq_direct': 'Ou contactez-nous directement :',
        'inq_direct_title': 'Contactez-nous directement',
        'inq_direct_sub': 'Contact immédiat ? Écrivez-nous via :',
        'lang_name': 'Français', 'html_lang': 'fr',
        'nav_home': 'Accueil', 'nav_products': 'Produits', 'nav_contact': 'Contact', 'nav_about': 'À propos',
        'btn_inquire': 'Demander', 'btn_buy': 'Acheter', 'btn_add_cart': 'Ajouter au panier', 'btn_send': 'Envoyer',
        'sec_products': 'Nos Produits', 'sec_about': 'À propos', 'sec_contact': 'Contact',
        'related_products': 'Produits liés', 'detail_specs': 'Détails du produit', 'detail_desc': 'Description',
        'detail_shipping': 'Livraison & Paiement', 'detail_video': 'Vidéo du produit',
        'attr_sku': 'SKU', 'attr_model': 'Modèle', 'attr_spec': 'Spécification', 'attr_category': 'Catégorie',
        'attr_stock': 'Disponibilité', 'in_stock': 'En stock', 'out_stock': 'Rupture de stock',
        'inq_title': 'Envoyer une demande', 'inq_sub': 'Remplissez le formulaire, nous répondrons sous 24 heures.',
        'inq_name': 'Votre nom', 'inq_email': 'Votre email', 'inq_country': 'Pays',
        'inq_message': 'Message', 'inq_placeholder': 'Décrivez vos besoins (quantité, personnalisation, etc.)',
        'inq_success': 'Votre demande a été envoyée avec succès. Nous vous contacterons bientôt !',
        'inq_required': 'Veuillez remplir nom, email et message.',
        'ck_text': 'Nous utilisons des cookies pour améliorer votre expérience et analyser le trafic. En continuant, vous acceptez notre Politique de cookies.',
        'ck_accept': 'Accepter', 'ck_decline': 'Refuser',
        'btn_view': 'Voir les détails', 'in_stock_short': 'En stock', 'out_stock_short': 'Rupture de stock',
        'seo_desc_default': 'Fabricant et fournisseur professionnel - Produits de qualité au prix d\'usine',
        'seo_default_title': 'Fabricant et fournisseur professionnel - Produits de qualité au prix d\'usine',
        'seo_default_desc': 'Nous sommes une usine et un fournisseur professionnels, offrant des produits de haute qualité avec service OEM/ODM dans le monde entier.',
        'copyright': 'Tous droits réservés.',
    },
    'pt': {
        'inq_direct': 'Ou fale conosco diretamente:',
        'inq_direct_title': 'Fale conosco diretamente',
        'inq_direct_sub': 'Prefere contato imediato? Fale conosco via:',
        'lang_name': 'Português', 'html_lang': 'pt',
        'nav_home': 'Início', 'nav_products': 'Produtos', 'nav_contact': 'Contato', 'nav_about': 'Sobre',
        'btn_inquire': 'Consultar', 'btn_buy': 'Comprar agora', 'btn_add_cart': 'Adicionar ao carrinho', 'btn_send': 'Enviar',
        'sec_products': 'Nossos Produtos', 'sec_about': 'Sobre nós', 'sec_contact': 'Contato',
        'related_products': 'Produtos relacionados', 'detail_specs': 'Detalhes do produto', 'detail_desc': 'Descrição',
        'detail_shipping': 'Envio e Pagamento', 'detail_video': 'Vídeo do produto',
        'attr_sku': 'SKU', 'attr_model': 'Modelo', 'attr_spec': 'Especificação', 'attr_category': 'Categoria',
        'attr_stock': 'Disponibilidade', 'in_stock': 'Em estoque', 'out_stock': 'Fora de estoque',
        'inq_title': 'Enviar consulta', 'inq_sub': 'Preencha o formulário, responderemos em 24 horas.',
        'inq_name': 'Seu nome', 'inq_email': 'Seu email', 'inq_country': 'País',
        'inq_message': 'Mensagem', 'inq_placeholder': 'Conte-nos seus requisitos (quantidade, personalização, etc.)',
        'inq_success': 'Sua consulta foi enviada com sucesso. Entraremos em contato em breve!',
        'inq_required': 'Por favor, preencha nome, email e mensagem.',
        'ck_text': 'Usamos cookies para melhorar sua experiência e analisar o tráfego. Ao continuar, você concorda com nossa Política de Cookies.',
        'ck_accept': 'Aceitar', 'ck_decline': 'Recusar',
        'btn_view': 'Ver detalhes', 'in_stock_short': 'Em estoque', 'out_stock_short': 'Esgotado',
        'seo_desc_default': 'Fabricante e Fornecedor Profissional - Produtos de Qualidade a Preço de Fábrica',
        'seo_default_title': 'Fabricante e Fornecedor Profissional - Produtos de Qualidade a Preço de Fábrica',
        'seo_default_desc': 'Somos uma fábrica e fornecedor profissional, oferecendo produtos de alta qualidade com serviço OEM/ODM em todo o mundo.',
        'copyright': 'Todos os direitos reservados.',
    },
    'ar': {
        'inq_direct': 'أو تواصل معنا مباشرة:',
        'inq_direct_title': 'تواصل معنا مباشرة',
        'inq_direct_sub': 'تفضل التواصل الفوري؟ تواصل معنا عبر:',
        'lang_name': 'العربية', 'html_lang': 'ar',
        'nav_home': 'الرئيسية', 'nav_products': 'المنتجات', 'nav_contact': 'اتصل بنا', 'nav_about': 'من نحن',
        'btn_inquire': 'استفسر الآن', 'btn_buy': 'اشتر الآن', 'btn_add_cart': 'أضف إلى السلة', 'btn_send': 'إرسال',
        'sec_products': 'منتجاتنا', 'sec_about': 'من نحن', 'sec_contact': 'اتصل بنا',
        'related_products': 'منتجات ذات صلة', 'detail_specs': 'تفاصيل المنتج', 'detail_desc': 'الوصف',
        'detail_shipping': 'الشحن والدفع', 'detail_video': 'فيديو المنتج',
        'attr_sku': 'رمز التخزين', 'attr_model': 'الطراز', 'attr_spec': 'المواصفات', 'attr_category': 'الفئة',
        'attr_stock': 'التوفر', 'in_stock': 'متوفر', 'out_stock': 'غير متوفر',
        'inq_title': 'أرسل استفسارًا', 'inq_sub': 'املأ النموذج وسنرد خلال 24 ساعة.',
        'inq_name': 'اسمك', 'inq_email': 'بريدك الإلكتروني', 'inq_country': 'الدولة',
        'inq_message': 'الرسالة', 'inq_placeholder': 'أخبرنا بمتطلباتك (الكمية، التخصيص، إلخ)',
        'inq_success': 'تم إرسال استفسارك بنجاح. سنتواصل معك قريبًا!',
        'inq_required': 'يرجى ملء الاسم والبريد الإلكتروني والرسالة.',
        'ck_text': 'نستخدم ملفات تعريف الارتباط لتحسين تجربتك وتحليل حركة المرور. بالمتابعة، فإنك توافق على سياسة ملفات تعريف الارتباط الخاصة بنا.',
        'ck_accept': 'موافق', 'ck_decline': 'رفض',
        'btn_view': 'عرض التفاصيل', 'in_stock_short': 'متوفر', 'out_stock_short': 'نفد المخزون',
        'seo_desc_default': 'مصنع ومورد محترف - منتجات عالية الجودة بأسعار المصنع',
        'seo_default_title': 'مصنع ومورد محترف - منتجات عالية الجودة بأسعار المصنع',
        'seo_default_desc': 'نحن مصنع ومورد محترف، نقدم منتجات عالية الجودة مع خدمة OEM/ODM في جميع أنحاء العالم.',
        'copyright': 'جميع الحقوق محفوظة.',
    },
}

# 补充键：所有框架自带文案全量翻译（不覆盖已存在键）
I18N_EXTRA = {
    'en': {
        'site_suffix': 'Professional Manufacturer & Supplier', 'products_suffix': 'Collection',
        'products_sub_default': 'High-quality products with competitive prices. Welcome to inquire.',
        'hero_empty': 'Upload banner images to display the carousel',
        'no_products': 'No products yet. Please add products in the admin panel.',
        'no_contact': 'No contact info yet. Please add it in the admin panel.',
        'contact_sub': 'Feel free to contact us for any questions or quotations.',
        'why_us': 'Why Choose Us',
        'why_factory': 'Factory Direct', 'why_factory_d': 'Competitive prices with no middlemen.',
        'why_fast': 'Fast Response', 'why_fast_d': 'Reply within 24 hours on business days.',
        'why_global': 'Global Shipping', 'why_global_d': 'Sea, air and express shipping worldwide.',
        'why_quality': 'Quality Assurance', 'why_quality_d': 'Strict QC before shipment.',
        'co_company': 'Company', 'co_address': 'Address', 'co_phone': 'Phone', 'co_email': 'Email',
        'no_specs': 'No specs.', 'no_product_image': 'No product image',
        'shipping_packing': 'Shipping & Packing', 'after_sales_service': 'After-sales Service',
        'ship_pack': 'Standard export packing: carton / wooden case / pallet, moisture-proof.',
        'ship_methods': 'Shipping: Express (DHL/UPS/FedEx), Air, Sea.',
        'ship_lead': 'Lead time: sample 3-7 days, bulk 15-30 days.',
        'after_free': 'Free replacement or reshipment for quality issues.',
        'after_warranty': '12-month warranty on most products.',
        'after_support': 'Technical support & guidance anytime.',
        'trust_factory': 'Factory Direct', 'trust_fast': 'Fast Shipping',
        'trust_quality': 'Quality Guarantee', 'trust_24h': '24h Service',
        'no_faq': 'No FAQ yet.',
        'sec_why_us': 'Why Choose Us', 'sec_team': 'Our Team', 'sec_cases': 'Customer Cases',
        'sec_gallery': 'Gallery', 'no_gallery_images': 'No gallery images yet.',
        'sec_news': 'News & Blog', 'sec_faq': 'FAQ', 'sec_testimonials': 'Testimonials',
        'sec_stats': 'Company In Numbers', 'sec_partners': 'Our Partners',
        'wa_help': 'Need help? Chat on WhatsApp', 'search_placeholder': 'Search products and pages...', 'search_no_result': 'No results found.', 'cat_all': 'All', 'sec_certificates': 'Certificates & Qualifications', 'no_certificates': 'No certificates yet.', 'cta_title': 'Ready to Start Your Project?', 'cta_subtitle': 'Get a free quote within 24 hours. Our sales team is here to help.', 'cta_btn': 'Get a Free Quote',
        'sec_payments': 'Payment Methods', 'sec_contacts': 'Contact Us',
        'contacts_now_suffix': 'Now', 'sec_video': 'Video', 'sec_map': 'Find Us',
        'sec_trust': 'Our Promise', 'sec_friend_links': 'Friend Links',
        'about_founded': 'Founded', 'about_scale': 'Scale',
        'payments_desc': 'We support multiple secure payment methods for your convenience.',
        'no_payment': 'Configure payment methods in the admin panel.',
        'no_video': 'Set a video URL in the admin panel.',
        'browser_no_video': 'Your browser does not support the video tag.',
        'no_map': 'Set an address or embed URL in the admin panel.',
        'inq_whatsapp': 'WhatsApp (optional)', 'inq_wechat': 'WeChat (optional)',
        'inq_direct': 'Or contact us directly:',
        'inq_direct_title': 'Contact Us Directly',
        'inq_direct_sub': 'Prefer instant contact? Reach us via:',
        'inq_required_hint': 'Name and at least one contact (Email / WhatsApp / WeChat) are required.',
        'js_sending': 'Sending...', 'js_required': 'Please fill in all required fields.',
        'js_success': 'Thank you! Your inquiry has been sent. We will reply within 24 hours.',
        'js_mailto_sent': 'Sent via email client. We will reply soon.',
        'js_copied': 'Copied: ', 'js_copy_manual': 'Please copy manually:',
        'dl_amazon_sold': '1,200+ sold', 'dl_pdd_group': '2-person group', 'dl_pdd_sold': '8,653 items joined',
        'dl_alibaba_moq': 'MOQ: 100 pieces', 'dl_alibaba_trade': 'Trade Assurance', 'dl_alibaba_returns': '15-day returns',
        'dl_rakuten_code': 'Item No.', 'dl_rakuten_ship': 'Shipping: Free nationwide',
        'dl_ebay_seller': 'Seller', 'dl_ebay_brand': 'Brand New',
        'dl_walmart_rollback': 'Rollback', 'dl_walmart_was': 'Was', 'dl_walmart_save': 'You save 20%',
        'dl_etsy_handmade': 'Handmade item · Ready to ship',
        'dl_shopee_sold': '5.2k sold',
        'dl_taobao_shop': 'Official Flagship Store', 'dl_taobao_rating': 'Rating 4.9 · Service 4.8 · Logistics 4.9',
        'jd_authentic': 'Authenticity Guaranteed', 'jd_fast': 'Fast Delivery',
        'jd_service': 'Worry-free After-sales', 'jd_7day': '7-day Return',
        'in_stock_units': ' (%d units)',
    },
    'zh': {
        'site_suffix': '专业制造商与供应商', 'products_suffix': '系列',
        'products_sub_default': '高品质产品，价格有竞争力，欢迎询盘。',
        'hero_empty': '请在后台横幅管理中上传图片以显示轮播',
        'no_products': '暂无产品，请在后台产品管理中添加。',
        'no_contact': '暂无联系方式，请在后台添加。',
        'contact_sub': '如有任何问题或需要报价，欢迎随时联系我们。',
        'why_us': '为什么选择我们',
        'why_factory': '工厂直供', 'why_factory_d': '价格有竞争力，无中间商。',
        'why_fast': '快速响应', 'why_fast_d': '工作日 24 小时内回复。',
        'why_global': '全球发货', 'why_global_d': '海运、空运、快递全球配送。',
        'why_quality': '品质保障', 'why_quality_d': '发货前严格质检。',
        'co_company': '公司名称', 'co_address': '公司地址', 'co_phone': '联系电话', 'co_email': '联系邮箱',
        'no_specs': '暂无规格参数。', 'no_product_image': '暂无产品图片',
        'shipping_packing': '运输与包装', 'after_sales_service': '售后服务',
        'ship_pack': '标准出口包装：纸箱/木箱/托盘，防潮处理。',
        'ship_methods': '运输方式：快递（DHL/UPS/FedEx）、空运、海运。',
        'ship_lead': '交期：样品 3-7 天，大货 15-30 天。',
        'after_free': '质量问题免费换货或补发。',
        'after_warranty': '大部分产品提供 12 个月质保。',
        'after_support': '随时提供技术支持与指导。',
        'trust_factory': '工厂直供', 'trust_fast': '快速发货', 'trust_quality': '品质保证', 'trust_24h': '24小时服务',
        'no_faq': '暂无常见问题。',
        'sec_why_us': '为什么选择我们', 'sec_team': '我们的团队', 'sec_cases': '客户案例',
        'sec_gallery': '作品画廊', 'no_gallery_images': '画廊暂未上传图片。',
        'sec_news': '新闻动态', 'sec_faq': '常见问题', 'sec_testimonials': '客户评价',
        'sec_stats': '公司数据', 'sec_partners': '合作伙伴', 'sec_payments': '支付方式',
        'wa_help': '需要帮助？WhatsApp 在线咨询', 'search_placeholder': '搜索产品与页面…', 'search_no_result': '未找到相关内容。', 'cat_all': '全部', 'sec_certificates': '资质证书', 'no_certificates': '暂未上传证书。', 'cta_title': '准备好开始您的项目了吗？', 'cta_subtitle': '24 小时内免费报价，销售团队随时为您服务。', 'cta_btn': '免费获取报价',
        'sec_contacts': '联系我们', 'contacts_now_suffix': '我们',
        'sec_video': '视频介绍', 'sec_map': '找到我们', 'sec_trust': '我们的承诺', 'sec_friend_links': '友情链接',
        'about_founded': '成立时间', 'about_scale': '公司规模',
        'payments_desc': '我们支持多种安全支付方式，方便您下单。',
        'no_payment': '请在后台支付配置中添加支付方式。',
        'no_video': '请在后台板块配置中填写视频地址。',
        'browser_no_video': '您的浏览器不支持视频播放。',
        'no_map': '请在后台板块配置中填写地址或地图嵌入链接。',
        'inq_whatsapp': 'WhatsApp（选填）', 'inq_wechat': '微信（选填）',
        'inq_direct': '或直接联系我们：',
        'inq_direct_title': '直接联系我们',
        'inq_direct_sub': '想即时沟通？通过以下方式直接联系我们：',
        'inq_required_hint': '姓名和至少一种联系方式（邮箱/WhatsApp/微信）为必填',
        'js_sending': '发送中...', 'js_required': '请填写所有必填项。',
        'js_success': '感谢您的询盘！我们将在 24 小时内回复。',
        'js_mailto_sent': '已通过邮件客户端发送，我们将尽快回复。',
        'js_copied': '已复制：', 'js_copy_manual': '请手动复制：',
        'dl_amazon_sold': '已售 1,200+ 件', 'dl_pdd_group': '2人团', 'dl_pdd_sold': '已拼 8,653 件',
        'dl_alibaba_moq': '起订量：100 件', 'dl_alibaba_trade': '贸易保障', 'dl_alibaba_returns': '15 天退货',
        'dl_rakuten_code': '商品编号', 'dl_rakuten_ship': '配送：全国免运费',
        'dl_ebay_seller': '卖家', 'dl_ebay_brand': '全新',
        'dl_walmart_rollback': '特价', 'dl_walmart_was': '原价', 'dl_walmart_save': '立省 20%',
        'dl_etsy_handmade': '手工制作 · 现货可发',
        'dl_shopee_sold': '已售 5.2k',
        'dl_taobao_shop': '官方旗舰店', 'dl_taobao_rating': '描述 4.9 · 服务 4.8 · 物流 4.9',
        'jd_authentic': '正品保障', 'jd_fast': '极速发货', 'jd_service': '售后无忧', 'jd_7day': '7天退换',
        'in_stock_units': '（%d 件）',
    },
    'zh-Hant': {
        'site_suffix': '專業製造商與供應商', 'products_suffix': '系列',
        'products_sub_default': '高品質產品，價格具競爭力，歡迎詢盤。',
        'hero_empty': '請在後台橫幅管理中上傳圖片以顯示輪播',
        'no_products': '暫無產品，請在後台產品管理中新增。',
        'no_contact': '暫無聯絡方式，請在後台新增。',
        'contact_sub': '如有任何問題或需要報價，歡迎隨時聯絡我們。',
        'why_us': '為什麼選擇我們',
        'why_factory': '工廠直供', 'why_factory_d': '價格具競爭力，無中間商。',
        'why_fast': '快速回應', 'why_fast_d': '工作日 24 小時內回覆。',
        'why_global': '全球出貨', 'why_global_d': '海運、空運、快遞全球配送。',
        'why_quality': '品質保障', 'why_quality_d': '出貨前嚴格品檢。',
        'co_company': '公司名稱', 'co_address': '公司地址', 'co_phone': '聯絡電話', 'co_email': '聯絡郵箱',
        'no_specs': '暫無規格參數。', 'no_product_image': '暫無產品圖片',
        'shipping_packing': '運輸與包裝', 'after_sales_service': '售後服務',
        'ship_pack': '標準出口包裝：紙箱/木箱/托盤，防潮處理。',
        'ship_methods': '運輸方式：快遞（DHL/UPS/FedEx）、空運、海運。',
        'ship_lead': '交期：樣品 3-7 天，大貨 15-30 天。',
        'after_free': '品質問題免費換貨或補發。',
        'after_warranty': '大部分產品提供 12 個月保固。',
        'after_support': '隨時提供技術支援與指導。',
        'trust_factory': '工廠直供', 'trust_fast': '快速出貨', 'trust_quality': '品質保證', 'trust_24h': '24小時服務',
        'no_faq': '暫無常見問題。',
        'sec_why_us': '為什麼選擇我們', 'sec_team': '我們的團隊', 'sec_cases': '客戶案例',
        'sec_gallery': '作品畫廊', 'no_gallery_images': '畫廊暫未上傳圖片。',
        'sec_news': '新聞動態', 'sec_faq': '常見問題', 'sec_testimonials': '客戶評價',
        'sec_stats': '公司數據', 'sec_partners': '合作夥伴', 'sec_payments': '付款方式',
        'wa_help': '需要協助？WhatsApp 線上諮詢', 'search_placeholder': '搜尋產品與頁面…', 'search_no_result': '未找到相關內容。', 'cat_all': '全部', 'sec_certificates': '資質證書', 'no_certificates': '暫未上傳證書。', 'cta_title': '準備好開始您的專案了嗎？', 'cta_subtitle': '24 小時內免費報價，銷售團隊隨時為您服務。', 'cta_btn': '免費取得報價',
        'sec_contacts': '聯絡我們', 'contacts_now_suffix': '我們',
        'sec_video': '影片介紹', 'sec_map': '找到我們', 'sec_trust': '我們的承諾', 'sec_friend_links': '友情連結',
        'about_founded': '成立時間', 'about_scale': '公司規模',
        'payments_desc': '我們支援多種安全付款方式，方便您下單。',
        'no_payment': '請在後台付款設定中新增付款方式。',
        'no_video': '請在後台區塊設定中填寫影片網址。',
        'browser_no_video': '您的瀏覽器不支援影片播放。',
        'no_map': '請在後台區塊設定中填寫地址或地圖嵌入連結。',
        'inq_whatsapp': 'WhatsApp（選填）', 'inq_wechat': '微信（選填）',
        'inq_direct': '或直接聯絡我們：',
        'inq_direct_title': '直接聯絡我們',
        'inq_direct_sub': '想即時溝通？透過以下方式直接聯絡我們：',
        'inq_required_hint': '姓名和至少一種聯絡方式（郵箱/WhatsApp/微信）為必填',
        'js_sending': '傳送中...', 'js_required': '請填寫所有必填項目。',
        'js_success': '感謝您的詢盤！我們將於 24 小時內回覆。',
        'js_mailto_sent': '已透過郵件用戶端傳送，我們將盡快回覆。',
        'js_copied': '已複製：', 'js_copy_manual': '請手動複製：',
        'dl_amazon_sold': '已售 1,200+ 件', 'dl_pdd_group': '2人團', 'dl_pdd_sold': '已拼 8,653 件',
        'dl_alibaba_moq': '起訂量：100 件', 'dl_alibaba_trade': '貿易保障', 'dl_alibaba_returns': '15 天退貨',
        'dl_rakuten_code': '商品編號', 'dl_rakuten_ship': '配送：全國免運費',
        'dl_ebay_seller': '賣家', 'dl_ebay_brand': '全新',
        'dl_walmart_rollback': '特價', 'dl_walmart_was': '原價', 'dl_walmart_save': '立省 20%',
        'dl_etsy_handmade': '手工製作 · 現貨可發',
        'dl_shopee_sold': '已售 5.2k',
        'dl_taobao_shop': '官方旗艦店', 'dl_taobao_rating': '描述 4.9 · 服務 4.8 · 物流 4.9',
        'jd_authentic': '正品保障', 'jd_fast': '極速出貨', 'jd_service': '售後無憂', 'jd_7day': '7天退換',
        'in_stock_units': '（%d 件）',
    },
    'ja': {
        'site_suffix': 'プロフェッショナルメーカー＆サプライヤー', 'products_suffix': 'コレクション',
        'products_sub_default': '高品質な製品を競争力のある価格で提供しています。お気軽にお問い合わせください。',
        'hero_empty': '管理画面でバナー画像をアップロードしてください',
        'no_products': 'まだ製品がありません。管理画面で製品を追加してください。',
        'no_contact': '連絡先情報はまだありません。',
        'contact_sub': 'ご質問や見積もりはいつでもお気軽にご連絡ください。',
        'why_us': '選ばれる理由', 'why_factory': '工場直販', 'why_factory_d': '中間業者なしの競争力ある価格。',
        'why_fast': '迅速な対応', 'why_fast_d': '営業日24時間以内に返信します。',
        'why_global': '世界配送', 'why_global_d': '海運・航空・国際宅配で世界中へ。',
        'why_quality': '品質保証', 'why_quality_d': '出荷前に厳格な品質検査。',
        'co_company': '会社名', 'co_address': '住所', 'co_phone': '電話', 'co_email': 'メール',
        'no_specs': '仕様はまだありません。', 'no_product_image': '製品画像がありません',
        'shipping_packing': '配送と梱包', 'after_sales_service': 'アフターサービス',
        'ship_pack': '標準輸出梱包：段ボール/木箱/パレット、防湿処理。',
        'ship_methods': '配送：宅配便（DHL/UPS/FedEx）、航空便、海上便。',
        'ship_lead': '納期：サンプル3〜7日、大量注文15〜30日。',
        'after_free': '品質問題は無償交換または再送。',
        'after_warranty': 'ほとんどの製品は12ヶ月保証。',
        'after_support': 'いつでも技術サポートを提供。',
        'trust_factory': '工場直販', 'trust_fast': '迅速発送', 'trust_quality': '品質保証', 'trust_24h': '24時間サポート',
        'no_faq': 'よくある質問はまだありません。',
        'sec_why_us': '選ばれる理由', 'sec_team': '私たちのチーム', 'sec_cases': '導入事例',
        'sec_news': 'ニュース', 'sec_faq': 'よくある質問', 'sec_testimonials': 'お客様の声',
        'sec_stats': '会社概要データ', 'sec_partners': 'パートナー', 'sec_payments': '支払い方法',
        'wa_help': 'ご不明点はWhatsAppでどうぞ', 'search_placeholder': '製品・ページを検索…', 'search_no_result': '該当する結果が見つかりません。', 'cat_all': 'すべて', 'sec_certificates': '資格・認証', 'no_certificates': '証明書はまだありません。', 'cta_title': 'プロジェクトを始めませんか？', 'cta_subtitle': '24時間以内に無料見積もりをご提供します。', 'cta_btn': '無料見積もりを取得',
        'sec_contacts': 'お問い合わせ', 'contacts_now_suffix': '今すぐ',
        'sec_video': 'ビデオ', 'sec_map': 'アクセス', 'sec_trust': '私たちの約束', 'sec_friend_links': 'リンク',
        'about_founded': '設立', 'about_scale': '規模',
        'payments_desc': '複数の安全な支払い方法に対応しています。',
        'no_payment': '管理画面で支払い方法を設定してください。',
        'no_video': '管理画面でビデオURLを設定してください。',
        'browser_no_video': 'お使いのブラウザは動画に対応していません。',
        'no_map': '管理画面で住所または地図URLを設定してください。',
        'inq_whatsapp': 'WhatsApp（任意）', 'inq_wechat': 'WeChat（任意）',
        'inq_required_hint': 'お名前と連絡先（メール/WhatsApp/WeChat）のいずれか1つが必要です。',
        'js_sending': '送信中...', 'js_required': '必須項目をすべて入力してください。',
        'js_success': 'お問い合わせありがとうございます！24時間以内に返信します。',
        'js_mailto_sent': 'メールクライアントで送信しました。すぐに返信します。',
        'js_copied': 'コピーしました：', 'js_copy_manual': '手動でコピーしてください：',
        'dl_amazon_sold': '1,200+ 販売', 'dl_pdd_group': '2人グループ', 'dl_pdd_sold': '8,653 件参加',
        'dl_alibaba_moq': '最小注文数：100個', 'dl_alibaba_trade': '貿易保証', 'dl_alibaba_returns': '15日返品可',
        'dl_rakuten_code': '商品番号', 'dl_rakuten_ship': '配送：全国送料無料',
        'dl_ebay_seller': '出品者', 'dl_ebay_brand': '新品',
        'dl_walmart_rollback': '特価', 'dl_walmart_was': '元の価格', 'dl_walmart_save': '20%お得',
        'dl_etsy_handmade': 'ハンドメイド · すぐ発送',
        'dl_shopee_sold': '5.2k 販売',
        'dl_taobao_shop': '公式旗艦店', 'dl_taobao_rating': '説明 4.9 · サービス 4.8 · 物流 4.9',
        'jd_authentic': '正規品保証', 'jd_fast': 'スピード発送', 'jd_service': 'アフター安心', 'jd_7day': '7日返品交換',
        'in_stock_units': '（%d 個）',
    },
    'ko': {
        'site_suffix': '전문 제조업체 및 공급업체', 'products_suffix': '컬렉션',
        'products_sub_default': '경쟁력 있는 가격의 고품질 제품을 제공합니다. 문의를 환영합니다.',
        'hero_empty': '관리자 페이지에서 배너 이미지를 업로드하세요',
        'no_products': '아직 제품이 없습니다. 관리자 페이지에서 제품을 추가하세요.',
        'no_contact': '아직 연락처 정보가 없습니다.',
        'contact_sub': '궁금한 점이나 견적 문의는 언제든지 연락 주세요.',
        'why_us': '왜 우리를 선택해야 하나요',
        'why_factory': '공장 직송', 'why_factory_d': '중간상 없이 경쟁력 있는 가격.',
        'why_fast': '빠른 응답', 'why_fast_d': '영업일 기준 24시간 이내 답변.',
        'why_global': '전 세계 배송', 'why_global_d': '해운, 항공, 특송으로 전 세계 배송.',
        'why_quality': '품질 보증', 'why_quality_d': '출하 전 엄격한 품질 검사.',
        'co_company': '회사명', 'co_address': '주소', 'co_phone': '전화', 'co_email': '이메일',
        'no_specs': '아직 사양이 없습니다.', 'no_product_image': '제품 이미지 없음',
        'shipping_packing': '배송 및 포장', 'after_sales_service': '애프터 서비스',
        'ship_pack': '표준 수출 포장: 판지/목재 상자/팔레트, 방습 처리.',
        'ship_methods': '배송: 특송(DHL/UPS/FedEx), 항공, 해운.',
        'ship_lead': '납기: 샘플 3-7일, 대량 15-30일.',
        'after_free': '품질 문제 시 무료 교체 또는 재발송.',
        'after_warranty': '대부분 제품 12개월 보증.',
        'after_support': '언제든 기술 지원 및 안내.',
        'trust_factory': '공장 직송', 'trust_fast': '빠른 배송', 'trust_quality': '품질 보증', 'trust_24h': '24시간 서비스',
        'no_faq': '아직 FAQ가 없습니다.',
        'sec_why_us': '왜 우리를 선택해야 하나요', 'sec_team': '우리 팀', 'sec_cases': '고객 사례',
        'sec_news': '뉴스', 'sec_faq': '자주 묻는 질문', 'sec_testimonials': '고객 평가',
        'sec_stats': '회사 현황', 'sec_partners': '파트너', 'sec_payments': '결제 방법',
        'wa_help': '도움이 필요하세요? WhatsApp 상담', 'search_placeholder': '제품·페이지 검색…', 'search_no_result': '검색 결과가 없습니다.', 'cat_all': '전체', 'sec_certificates': '자격 및 인증', 'no_certificates': '아직 인증서가 없습니다.', 'cta_title': '프로젝트를 시작할 준비가 되셨나요?', 'cta_subtitle': '24시간 내 무료 견적을 받아보세요.', 'cta_btn': '무료 견적 받기',
        'sec_contacts': '문의하기', 'contacts_now_suffix': '지금',
        'sec_video': '비디오', 'sec_map': '오시는 길', 'sec_trust': '우리의 약속', 'sec_friend_links': '링크',
        'about_founded': '설립', 'about_scale': '규모',
        'payments_desc': '편리한 결제를 위해 다양한 안전한 결제 방법을 지원합니다.',
        'no_payment': '관리자 페이지에서 결제 방법을 설정하세요.',
        'no_video': '관리자 페이지에서 비디오 URL을 설정하세요.',
        'browser_no_video': '브라우저가 동영상을 지원하지 않습니다.',
        'no_map': '관리자 페이지에서 주소 또는 지도 URL을 설정하세요.',
        'inq_whatsapp': 'WhatsApp(선택)', 'inq_wechat': 'WeChat(선택)',
        'inq_required_hint': '이름과 연락처(이메일/WhatsApp/WeChat) 중 하나는 필수입니다.',
        'js_sending': '보내는 중...', 'js_required': '필수 항목을 모두 입력하세요.',
        'js_success': '문의해 주셔서 감사합니다! 24시간 이내에 답변드리겠습니다.',
        'js_mailto_sent': '이메일 클라이언트로 전송되었습니다. 곧 답변드리겠습니다.',
        'js_copied': '복사됨: ', 'js_copy_manual': '수동으로 복사하세요: ',
        'dl_amazon_sold': '1,200+ 판매', 'dl_pdd_group': '2인 그룹', 'dl_pdd_sold': '8,653개 참여',
        'dl_alibaba_moq': '최소주문: 100개', 'dl_alibaba_trade': '무역 보장', 'dl_alibaba_returns': '15일 반품',
        'dl_rakuten_code': '상품번호', 'dl_rakuten_ship': '배송: 전국 무료',
        'dl_ebay_seller': '판매자', 'dl_ebay_brand': '새 상품',
        'dl_walmart_rollback': '특가', 'dl_walmart_was': '기존 가격', 'dl_walmart_save': '20% 할인',
        'dl_etsy_handmade': '수공예 · 즉시 발송',
        'dl_shopee_sold': '5.2k 판매',
        'dl_taobao_shop': '공식 플래그십 스토어', 'dl_taobao_rating': '설명 4.9 · 서비스 4.8 · 배송 4.9',
        'jd_authentic': '정품 보장', 'jd_fast': '빠른 배송', 'jd_service': 'A/S 걱정 없음', 'jd_7day': '7일 반품',
        'in_stock_units': '(%d개)',
    },
    'de': {
        'site_suffix': 'Professioneller Hersteller & Lieferant', 'products_suffix': 'Kollektion',
        'products_sub_default': 'Qualitativ hochwertige Produkte zu wettbewerbsfähigen Preisen. Anfragen willkommen.',
        'hero_empty': 'Laden Sie Bannerbilder im Admin-Bereich hoch',
        'no_products': 'Noch keine Produkte. Bitte fügen Sie Produkte im Admin-Bereich hinzu.',
        'no_contact': 'Noch keine Kontaktinformationen vorhanden.',
        'contact_sub': 'Kontaktieren Sie uns gerne bei Fragen oder Angebotsanfragen.',
        'why_us': 'Warum uns wählen',
        'why_factory': 'Fabrikdirekt', 'why_factory_d': 'Wettbewerbsfähige Preise ohne Zwischenhändler.',
        'why_fast': 'Schnelle Antwort', 'why_fast_d': 'Antwort innerhalb von 24 Stunden an Werktagen.',
        'why_global': 'Weltweiter Versand', 'why_global_d': 'See-, Luft- und Expressversand weltweit.',
        'why_quality': 'Qualitätssicherung', 'why_quality_d': 'Strenge Qualitätskontrolle vor Versand.',
        'co_company': 'Firma', 'co_address': 'Adresse', 'co_phone': 'Telefon', 'co_email': 'E-Mail',
        'no_specs': 'Keine Spezifikationen.', 'no_product_image': 'Kein Produktbild',
        'shipping_packing': 'Versand & Verpackung', 'after_sales_service': 'Kundendienst',
        'ship_pack': 'Standard-Exportverpackung: Karton/Holzkiste/Palette, feuchtigkeitsgeschützt.',
        'ship_methods': 'Versand: Express (DHL/UPS/FedEx), Luft, See.',
        'ship_lead': 'Lieferzeit: Muster 3-7 Tage, Großbestellung 15-30 Tage.',
        'after_free': 'Kostenloser Ersatz oder Nachversand bei Qualitätsproblemen.',
        'after_warranty': '12 Monate Garantie auf die meisten Produkte.',
        'after_support': 'Technischer Support und Beratung jederzeit.',
        'trust_factory': 'Fabrikdirekt', 'trust_fast': 'Schneller Versand', 'trust_quality': 'Qualitätsgarantie', 'trust_24h': '24h-Service',
        'no_faq': 'Noch keine FAQ.',
        'sec_why_us': 'Warum uns wählen', 'sec_team': 'Unser Team', 'sec_cases': 'Kundenreferenzen',
        'sec_news': 'Neuigkeiten', 'sec_faq': 'FAQ', 'sec_testimonials': 'Kundenstimmen',
        'sec_stats': 'Zahlen & Fakten', 'sec_partners': 'Unsere Partner', 'sec_payments': 'Zahlungsmethoden',
        'wa_help': 'Hilfe? Chatten Sie auf WhatsApp', 'search_placeholder': 'Produkte und Seiten durchsuchen...', 'search_no_result': 'Keine Ergebnisse gefunden.', 'cat_all': 'Alle', 'sec_certificates': 'Zertifikate & Qualifikationen', 'no_certificates': 'Noch keine Zertifikate.', 'cta_title': 'Bereit, Ihr Projekt zu starten?', 'cta_subtitle': 'Erhalten Sie innerhalb von 24 Stunden ein kostenloses Angebot.', 'cta_btn': 'Kostenloses Angebot',
        'sec_contacts': 'Kontakt', 'contacts_now_suffix': 'Jetzt',
        'sec_video': 'Video', 'sec_map': 'Finden Sie uns', 'sec_trust': 'Unser Versprechen', 'sec_friend_links': 'Links',
        'about_founded': 'Gegründet', 'about_scale': 'Größe',
        'payments_desc': 'Wir unterstützen mehrere sichere Zahlungsmethoden.',
        'no_payment': 'Konfigurieren Sie Zahlungsmethoden im Admin-Bereich.',
        'no_video': 'Legen Sie eine Video-URL im Admin-Bereich fest.',
        'browser_no_video': 'Ihr Browser unterstützt das Video-Tag nicht.',
        'no_map': 'Legen Sie eine Adresse oder Karten-URL im Admin-Bereich fest.',
        'inq_whatsapp': 'WhatsApp (optional)', 'inq_wechat': 'WeChat (optional)',
        'inq_required_hint': 'Name und mindestens eine Kontaktmöglichkeit (E-Mail/WhatsApp/WeChat) sind erforderlich.',
        'js_sending': 'Wird gesendet...', 'js_required': 'Bitte füllen Sie alle Pflichtfelder aus.',
        'js_success': 'Vielen Dank! Wir antworten innerhalb von 24 Stunden.',
        'js_mailto_sent': 'Über den E-Mail-Client gesendet. Wir antworten bald.',
        'js_copied': 'Kopiert: ', 'js_copy_manual': 'Bitte manuell kopieren: ',
        'dl_amazon_sold': '1.200+ verkauft', 'dl_pdd_group': '2-Personen-Gruppe', 'dl_pdd_sold': '8.653 Artikel beigetreten',
        'dl_alibaba_moq': 'MOQ: 100 Stück', 'dl_alibaba_trade': 'Handelssicherung', 'dl_alibaba_returns': '15 Tage Rückgabe',
        'dl_rakuten_code': 'Artikelnummer', 'dl_rakuten_ship': 'Versand: Kostenlos bundesweit',
        'dl_ebay_seller': 'Verkäufer', 'dl_ebay_brand': 'Neu',
        'dl_walmart_rollback': 'Sonderpreis', 'dl_walmart_was': 'Vorher', 'dl_walmart_save': 'Sie sparen 20%',
        'dl_etsy_handmade': 'Handgefertigt · Versandfertig',
        'dl_shopee_sold': '5,2k verkauft',
        'dl_taobao_shop': 'Offizieller Flagship-Store', 'dl_taobao_rating': 'Beschreibung 4.9 · Service 4.8 · Logistik 4.9',
        'jd_authentic': 'Echtheit garantiert', 'jd_fast': 'Schnelle Lieferung', 'jd_service': 'Sorgloser Kundendienst', 'jd_7day': '7 Tage Rückgabe',
        'in_stock_units': ' (%d Stück)',
    },
    'es': {
        'site_suffix': 'Fabricante y proveedor profesional', 'products_suffix': 'Colección',
        'products_sub_default': 'Productos de alta calidad a precios competitivos. Las consultas son bienvenidas.',
        'hero_empty': 'Suba imágenes de banner en el panel de administración',
        'no_products': 'Aún no hay productos. Añada productos en el panel de administración.',
        'no_contact': 'Aún no hay información de contacto.',
        'contact_sub': 'Contáctenos para cualquier pregunta o cotización.',
        'why_us': 'Por qué elegirnos',
        'why_factory': 'Directo de fábrica', 'why_factory_d': 'Precios competitivos sin intermediarios.',
        'why_fast': 'Respuesta rápida', 'why_fast_d': 'Respuesta en 24 horas en días laborables.',
        'why_global': 'Envío mundial', 'why_global_d': 'Envío marítimo, aéreo y exprés a todo el mundo.',
        'why_quality': 'Garantía de calidad', 'why_quality_d': 'Control de calidad estricto antes del envío.',
        'co_company': 'Empresa', 'co_address': 'Dirección', 'co_phone': 'Teléfono', 'co_email': 'Correo',
        'no_specs': 'Sin especificaciones.', 'no_product_image': 'Sin imagen de producto',
        'shipping_packing': 'Envío y embalaje', 'after_sales_service': 'Servicio postventa',
        'ship_pack': 'Embalaje estándar de exportación: caja/caja de madera/palet, a prueba de humedad.',
        'ship_methods': 'Envío: exprés (DHL/UPS/FedEx), aéreo, marítimo.',
        'ship_lead': 'Plazo: muestra 3-7 días, pedido grande 15-30 días.',
        'after_free': 'Reemplazo o reenvío gratuito por problemas de calidad.',
        'after_warranty': 'Garantía de 12 meses en la mayoría de productos.',
        'after_support': 'Soporte técnico y orientación en cualquier momento.',
        'trust_factory': 'Directo de fábrica', 'trust_fast': 'Envío rápido', 'trust_quality': 'Garantía de calidad', 'trust_24h': 'Servicio 24h',
        'no_faq': 'Aún no hay preguntas frecuentes.',
        'sec_why_us': 'Por qué elegirnos', 'sec_team': 'Nuestro equipo', 'sec_cases': 'Casos de clientes',
        'sec_news': 'Noticias', 'sec_faq': 'Preguntas frecuentes', 'sec_testimonials': 'Testimonios',
        'sec_stats': 'Números de la empresa', 'sec_partners': 'Nuestros socios', 'sec_payments': 'Métodos de pago',
        'wa_help': '¿Necesita ayuda? Chatee por WhatsApp', 'search_placeholder': 'Buscar productos y páginas...', 'search_no_result': 'No se encontraron resultados.', 'cat_all': 'Todos', 'sec_certificates': 'Certificados y cualificaciones', 'no_certificates': 'Aún no hay certificados.', 'cta_title': '¿Listo para comenzar su proyecto?', 'cta_subtitle': 'Reciba un presupuesto gratuito en 24 horas.', 'cta_btn': 'Presupuesto gratuito',
        'sec_contacts': 'Contáctenos', 'contacts_now_suffix': 'Ahora',
        'sec_video': 'Video', 'sec_map': 'Encuéntrenos', 'sec_trust': 'Nuestra promesa', 'sec_friend_links': 'Enlaces',
        'about_founded': 'Fundada', 'about_scale': 'Tamaño',
        'payments_desc': 'Aceptamos varios métodos de pago seguros.',
        'no_payment': 'Configure métodos de pago en el panel de administración.',
        'no_video': 'Establezca una URL de video en el panel de administración.',
        'browser_no_video': 'Su navegador no admite la etiqueta de video.',
        'no_map': 'Establezca una dirección o URL de mapa en el panel de administración.',
        'inq_whatsapp': 'WhatsApp (opcional)', 'inq_wechat': 'WeChat (opcional)',
        'inq_required_hint': 'Nombre y al menos un contacto (Email/WhatsApp/WeChat) son obligatorios.',
        'js_sending': 'Enviando...', 'js_required': 'Complete todos los campos obligatorios.',
        'js_success': '¡Gracias! Responderemos dentro de 24 horas.',
        'js_mailto_sent': 'Enviado a través del cliente de correo. Responderemos pronto.',
        'js_copied': 'Copiado: ', 'js_copy_manual': 'Por favor copie manualmente: ',
        'dl_amazon_sold': '1.200+ vendidos', 'dl_pdd_group': 'Grupo de 2', 'dl_pdd_sold': '8.653 artículos unidos',
        'dl_alibaba_moq': 'MOQ: 100 piezas', 'dl_alibaba_trade': 'Garantía comercial', 'dl_alibaba_returns': 'Devolución en 15 días',
        'dl_rakuten_code': 'N.º de artículo', 'dl_rakuten_ship': 'Envío: Gratis en todo el país',
        'dl_ebay_seller': 'Vendedor', 'dl_ebay_brand': 'Nuevo',
        'dl_walmart_rollback': 'Rebaja', 'dl_walmart_was': 'Antes', 'dl_walmart_save': 'Ahorra 20%',
        'dl_etsy_handmade': 'Hecho a mano · Listo para enviar',
        'dl_shopee_sold': '5,2k vendidos',
        'dl_taobao_shop': 'Tienda oficial insignia', 'dl_taobao_rating': 'Descripción 4.9 · Servicio 4.8 · Logística 4.9',
        'jd_authentic': 'Autenticidad garantizada', 'jd_fast': 'Entrega rápida', 'jd_service': 'Postventa sin preocupaciones', 'jd_7day': 'Devolución en 7 días',
        'in_stock_units': ' (%d unidades)',
    },
    'ru': {
        'site_suffix': 'Профессиональный производитель и поставщик', 'products_suffix': 'Коллекция',
        'products_sub_default': 'Высококачественная продукция по конкурентоспособным ценам. Запросы приветствуются.',
        'hero_empty': 'Загрузите изображения баннера в панели администратора',
        'no_products': 'Пока нет товаров. Добавьте товары в панели администратора.',
        'no_contact': 'Контактная информация пока отсутствует.',
        'contact_sub': 'Свяжитесь с нами по любым вопросам или запросам цен.',
        'why_us': 'Почему выбирают нас',
        'why_factory': 'Прямо с завода', 'why_factory_d': 'Конкурентоспособные цены без посредников.',
        'why_fast': 'Быстрый ответ', 'why_fast_d': 'Ответ в течение 24 часов в рабочие дни.',
        'why_global': 'Доставка по всему миру', 'why_global_d': 'Морская, авиа и экспресс-доставка по всему миру.',
        'why_quality': 'Гарантия качества', 'why_quality_d': 'Строгий контроль качества перед отправкой.',
        'co_company': 'Компания', 'co_address': 'Адрес', 'co_phone': 'Телефон', 'co_email': 'Почта',
        'no_specs': 'Нет характеристик.', 'no_product_image': 'Нет изображения товара',
        'shipping_packing': 'Доставка и упаковка', 'after_sales_service': 'Послепродажное обслуживание',
        'ship_pack': 'Стандартная экспортная упаковка: картон/деревянный ящик/паллет, влагозащита.',
        'ship_methods': 'Доставка: экспресс (DHL/UPS/FedEx), авиа, море.',
        'ship_lead': 'Срок: образец 3-7 дней, опт 15-30 дней.',
        'after_free': 'Бесплатная замена или повторная отправка при проблемах с качеством.',
        'after_warranty': 'Гарантия 12 месяцев на большинство товаров.',
        'after_support': 'Техническая поддержка в любое время.',
        'trust_factory': 'Прямо с завода', 'trust_fast': 'Быстрая доставка', 'trust_quality': 'Гарантия качества', 'trust_24h': 'Сервис 24 часа',
        'no_faq': 'Пока нет FAQ.',
        'sec_why_us': 'Почему выбирают нас', 'sec_team': 'Наша команда', 'sec_cases': 'Кейсы клиентов',
        'sec_news': 'Новости', 'sec_faq': 'Частые вопросы', 'sec_testimonials': 'Отзывы',
        'sec_stats': 'Показатели компании', 'sec_partners': 'Партнеры', 'sec_payments': 'Способы оплаты',
        'wa_help': 'Нужна помощь? Напишите в WhatsApp', 'search_placeholder': 'Поиск товаров и страниц...', 'search_no_result': 'Ничего не найдено.', 'cat_all': 'Все', 'sec_certificates': 'Сертификаты и лицензии', 'no_certificates': 'Сертификаты пока отсутствуют.', 'cta_title': 'Готовы начать свой проект?', 'cta_subtitle': 'Получите бесплатное предложение в течение 24 часов.', 'cta_btn': 'Получить предложение',
        'sec_contacts': 'Связаться', 'contacts_now_suffix': 'Сейчас',
        'sec_video': 'Видео', 'sec_map': 'Найти нас', 'sec_trust': 'Наши обещания', 'sec_friend_links': 'Ссылки',
        'about_founded': 'Основана', 'about_scale': 'Размер',
        'payments_desc': 'Мы поддерживаем несколько безопасных способов оплаты.',
        'no_payment': 'Настройте способы оплаты в панели администратора.',
        'no_video': 'Укажите URL видео в панели администратора.',
        'browser_no_video': 'Ваш браузер не поддерживает тег видео.',
        'no_map': 'Укажите адрес или URL карты в панели администратора.',
        'inq_whatsapp': 'WhatsApp (необязательно)', 'inq_wechat': 'WeChat (необязательно)',
        'inq_required_hint': 'Имя и хотя бы один контакт (Email/WhatsApp/WeChat) обязательны.',
        'js_sending': 'Отправка...', 'js_required': 'Заполните все обязательные поля.',
        'js_success': 'Спасибо! Мы ответим в течение 24 часов.',
        'js_mailto_sent': 'Отправлено через почтовый клиент. Мы скоро ответим.',
        'js_copied': 'Скопировано: ', 'js_copy_manual': 'Пожалуйста, скопируйте вручную: ',
        'dl_amazon_sold': '1 200+ продано', 'dl_pdd_group': 'Группа из 2', 'dl_pdd_sold': '8 653 позиции присоединились',
        'dl_alibaba_moq': 'МОЗ: 100 шт.', 'dl_alibaba_trade': 'Торговая гарантия', 'dl_alibaba_returns': 'Возврат за 15 дней',
        'dl_rakuten_code': 'Артикул', 'dl_rakuten_ship': 'Доставка: бесплатно по стране',
        'dl_ebay_seller': 'Продавец', 'dl_ebay_brand': 'Новый',
        'dl_walmart_rollback': 'Скидка', 'dl_walmart_was': 'Было', 'dl_walmart_save': 'Вы экономите 20%',
        'dl_etsy_handmade': 'Ручная работа · Готов к отправке',
        'dl_shopee_sold': '5,2 тыс. продано',
        'dl_taobao_shop': 'Официальный флагманский магазин', 'dl_taobao_rating': 'Описание 4.9 · Сервис 4.8 · Логистика 4.9',
        'jd_authentic': 'Гарантия подлинности', 'jd_fast': 'Быстрая доставка', 'jd_service': 'Надежный сервис', 'jd_7day': 'Возврат за 7 дней',
        'in_stock_units': ' (%d шт.)',
    },
    'fr': {
        'site_suffix': 'Fabricant et fournisseur professionnel', 'products_suffix': 'Collection',
        'products_sub_default': 'Produits de haute qualité à prix compétitifs. Demandes de renseignements bienvenues.',
        'hero_empty': 'Téléchargez les images de bannière dans le panneau d\'administration',
        'no_products': 'Aucun produit pour le moment. Ajoutez des produits dans le panneau d\'administration.',
        'no_contact': 'Aucune information de contact pour le moment.',
        'contact_sub': 'Contactez-nous pour toute question ou demande de devis.',
        'why_us': 'Pourquoi nous choisir',
        'why_factory': 'Direct usine', 'why_factory_d': 'Prix compétitifs sans intermédiaires.',
        'why_fast': 'Réponse rapide', 'why_fast_d': 'Réponse sous 24h en jours ouvrés.',
        'why_global': 'Expédition mondiale', 'why_global_d': 'Expédition maritime, aérienne et express dans le monde entier.',
        'why_quality': 'Assurance qualité', 'why_quality_d': 'Contrôle qualité strict avant expédition.',
        'co_company': 'Société', 'co_address': 'Adresse', 'co_phone': 'Téléphone', 'co_email': 'E-mail',
        'no_specs': 'Aucune spécification.', 'no_product_image': 'Aucune image produit',
        'shipping_packing': 'Expédition et emballage', 'after_sales_service': 'Service après-vente',
        'ship_pack': 'Emballage d\'exportation standard : carton / caisse en bois / palette, résistant à l\'humidité.',
        'ship_methods': 'Expédition : express (DHL/UPS/FedEx), aérienne, maritime.',
        'ship_lead': 'Délai : échantillon 3-7 jours, commande en gros 15-30 jours.',
        'after_free': 'Remplacement ou réexpédition gratuit en cas de problème de qualité.',
        'after_warranty': 'Garantie de 12 mois sur la plupart des produits.',
        'after_support': 'Support technique et conseils à tout moment.',
        'trust_factory': 'Direct usine', 'trust_fast': 'Expédition rapide', 'trust_quality': 'Garantie de qualité', 'trust_24h': 'Service 24h/24',
        'no_faq': 'Aucune FAQ pour le moment.',
        'sec_why_us': 'Pourquoi nous choisir', 'sec_team': 'Notre équipe', 'sec_cases': 'Réalisations clients',
        'sec_news': 'Actualités', 'sec_faq': 'FAQ', 'sec_testimonials': 'Témoignages',
        'sec_stats': 'Chiffres clés', 'sec_partners': 'Nos partenaires', 'sec_payments': 'Moyens de paiement',
        'wa_help': 'Besoin d\'aide ? Discutez sur WhatsApp', 'search_placeholder': 'Rechercher produits et pages...', 'search_no_result': 'Aucun résultat trouvé.', 'cat_all': 'Tous', 'sec_certificates': 'Certificats et qualifications', 'no_certificates': 'Aucun certificat pour le moment.', 'cta_title': 'Prêt à lancer votre projet ?', 'cta_subtitle': 'Obtenez un devis gratuit sous 24 heures.', 'cta_btn': 'Devis gratuit',
        'sec_contacts': 'Contact', 'contacts_now_suffix': 'Maintenant',
        'sec_video': 'Vidéo', 'sec_map': 'Nous trouver', 'sec_trust': 'Notre promesse', 'sec_friend_links': 'Liens',
        'about_founded': 'Fondée', 'about_scale': 'Taille',
        'payments_desc': 'Nous acceptons plusieurs modes de paiement sécurisés.',
        'no_payment': 'Configurez les moyens de paiement dans le panneau d\'administration.',
        'no_video': 'Définissez une URL de vidéo dans le panneau d\'administration.',
        'browser_no_video': 'Votre navigateur ne prend pas en charge la balise vidéo.',
        'no_map': 'Définissez une adresse ou une URL de carte dans le panneau d\'administration.',
        'inq_whatsapp': 'WhatsApp (facultatif)', 'inq_wechat': 'WeChat (facultatif)',
        'inq_required_hint': 'Nom et au moins un contact (Email/WhatsApp/WeChat) sont requis.',
        'js_sending': 'Envoi...', 'js_required': 'Veuillez remplir tous les champs obligatoires.',
        'js_success': 'Merci ! Nous répondrons sous 24 heures.',
        'js_mailto_sent': 'Envoyé via le client de messagerie. Nous répondrons bientôt.',
        'js_copied': 'Copié : ', 'js_copy_manual': 'Veuillez copier manuellement : ',
        'dl_amazon_sold': '1 200+ vendus', 'dl_pdd_group': 'Groupe de 2', 'dl_pdd_sold': '8 653 articles rejoints',
        'dl_alibaba_moq': 'MOQ : 100 pièces', 'dl_alibaba_trade': 'Garantie commerciale', 'dl_alibaba_returns': 'Retour sous 15 jours',
        'dl_rakuten_code': 'N° d\'article', 'dl_rakuten_ship': 'Livraison : gratuite partout',
        'dl_ebay_seller': 'Vendeur', 'dl_ebay_brand': 'Neuf',
        'dl_walmart_rollback': 'Promotion', 'dl_walmart_was': 'Avant', 'dl_walmart_save': 'Vous économisez 20%',
        'dl_etsy_handmade': 'Fait main · Prêt à expédier',
        'dl_shopee_sold': '5,2k vendus',
        'dl_taobao_shop': 'Boutique officielle', 'dl_taobao_rating': 'Description 4.9 · Service 4.8 · Logistique 4.9',
        'jd_authentic': 'Authenticité garantie', 'jd_fast': 'Livraison rapide', 'jd_service': 'SAV sans souci', 'jd_7day': 'Retour sous 7 jours',
        'in_stock_units': ' (%d pièces)',
    },
    'pt': {
        'site_suffix': 'Fabricante e fornecedor profissional', 'products_suffix': 'Coleção',
        'products_sub_default': 'Produtos de alta qualidade a preços competitivos. Consultas são bem-vindas.',
        'hero_empty': 'Envie imagens de banner no painel de administração',
        'no_products': 'Ainda não há produtos. Adicione produtos no painel de administração.',
        'no_contact': 'Ainda não há informações de contato.',
        'contact_sub': 'Fale conosco para qualquer pergunta ou cotação.',
        'why_us': 'Por que nos escolher',
        'why_factory': 'Direto da fábrica', 'why_factory_d': 'Preços competitivos sem intermediários.',
        'why_fast': 'Resposta rápida', 'why_fast_d': 'Resposta em 24 horas em dias úteis.',
        'why_global': 'Envio mundial', 'why_global_d': 'Envio marítimo, aéreo e expresso para todo o mundo.',
        'why_quality': 'Garantia de qualidade', 'why_quality_d': 'Controle de qualidade rigoroso antes do envio.',
        'co_company': 'Empresa', 'co_address': 'Endereço', 'co_phone': 'Telefone', 'co_email': 'E-mail',
        'no_specs': 'Sem especificações.', 'no_product_image': 'Sem imagem do produto',
        'shipping_packing': 'Envio e embalagem', 'after_sales_service': 'Atendimento pós-venda',
        'ship_pack': 'Embalagem padrão de exportação: caixa/caixa de madeira/palete, à prova de umidade.',
        'ship_methods': 'Envio: expresso (DHL/UPS/FedEx), aéreo, marítimo.',
        'ship_lead': 'Prazo: amostra 3-7 dias, pedido grande 15-30 dias.',
        'after_free': 'Substituição ou reenvio gratuito por problemas de qualidade.',
        'after_warranty': 'Garantia de 12 meses na maioria dos produtos.',
        'after_support': 'Suporte técnico e orientação a qualquer momento.',
        'trust_factory': 'Direto da fábrica', 'trust_fast': 'Envio rápido', 'trust_quality': 'Garantia de qualidade', 'trust_24h': 'Serviço 24h',
        'no_faq': 'Ainda não há perguntas frequentes.',
        'sec_why_us': 'Por que nos escolher', 'sec_team': 'Nossa equipe', 'sec_cases': 'Casos de clientes',
        'sec_news': 'Notícias', 'sec_faq': 'Perguntas frequentes', 'sec_testimonials': 'Depoimentos',
        'sec_stats': 'Números da empresa', 'sec_partners': 'Nossos parceiros', 'sec_payments': 'Formas de pagamento',
        'wa_help': 'Precisa de ajuda? Fale no WhatsApp', 'search_placeholder': 'Pesquisar produtos e páginas...', 'search_no_result': 'Nenhum resultado encontrado.', 'cat_all': 'Todos', 'sec_certificates': 'Certificados e qualificações', 'no_certificates': 'Ainda não há certificados.', 'cta_title': 'Pronto para começar seu projeto?', 'cta_subtitle': 'Receba um orçamento gratuito em até 24 horas.', 'cta_btn': 'Orçamento gratuito',
        'sec_contacts': 'Contato', 'contacts_now_suffix': 'Agora',
        'sec_video': 'Vídeo', 'sec_map': 'Encontre-nos', 'sec_trust': 'Nossa promessa', 'sec_friend_links': 'Links',
        'about_founded': 'Fundada', 'about_scale': 'Porte',
        'payments_desc': 'Aceitamos várias formas de pagamento seguras.',
        'no_payment': 'Configure formas de pagamento no painel de administração.',
        'no_video': 'Defina uma URL de vídeo no painel de administração.',
        'browser_no_video': 'Seu navegador não suporta a tag de vídeo.',
        'no_map': 'Defina um endereço ou URL de mapa no painel de administração.',
        'inq_whatsapp': 'WhatsApp (opcional)', 'inq_wechat': 'WeChat (opcional)',
        'inq_required_hint': 'Nome e pelo menos um contato (Email/WhatsApp/WeChat) são obrigatórios.',
        'js_sending': 'Enviando...', 'js_required': 'Preencha todos os campos obrigatórios.',
        'js_success': 'Obrigado! Responderemos dentro de 24 horas.',
        'js_mailto_sent': 'Enviado pelo cliente de e-mail. Responderemos em breve.',
        'js_copied': 'Copiado: ', 'js_copy_manual': 'Copie manualmente: ',
        'dl_amazon_sold': '1.200+ vendidos', 'dl_pdd_group': 'Grupo de 2', 'dl_pdd_sold': '8.653 itens aderidos',
        'dl_alibaba_moq': 'MOQ: 100 peças', 'dl_alibaba_trade': 'Garantia comercial', 'dl_alibaba_returns': 'Devolução em 15 dias',
        'dl_rakuten_code': 'N.º do item', 'dl_rakuten_ship': 'Envio: grátis em todo o país',
        'dl_ebay_seller': 'Vendedor', 'dl_ebay_brand': 'Novo',
        'dl_walmart_rollback': 'Promoção', 'dl_walmart_was': 'Antes', 'dl_walmart_save': 'Economize 20%',
        'dl_etsy_handmade': 'Feito à mão · Pronto para envio',
        'dl_shopee_sold': '5,2k vendidos',
        'dl_taobao_shop': 'Loja oficial', 'dl_taobao_rating': 'Descrição 4.9 · Serviço 4.8 · Logística 4.9',
        'jd_authentic': 'Autenticidade garantida', 'jd_fast': 'Entrega rápida', 'jd_service': 'Pós-venda sem preocupações', 'jd_7day': 'Devolução em 7 dias',
        'in_stock_units': ' (%d unidades)',
    },
    'ar': {
        'site_suffix': 'مصنع ومورد محترف', 'products_suffix': 'مجموعة',
        'products_sub_default': 'منتجات عالية الجودة بأسعار تنافسية. نرحب باستفساراتكم.',
        'hero_empty': 'قم برفع صور البانر في لوحة الإدارة',
        'no_products': 'لا توجد منتجات بعد. يرجى إضافة المنتجات في لوحة الإدارة.',
        'no_contact': 'لا توجد معلومات اتصال بعد.',
        'contact_sub': 'تواصل معنا لأي استفسار أو طلب عرض سعر.',
        'why_us': 'لماذا تختارنا',
        'why_factory': 'مباشرة من المصنع', 'why_factory_d': 'أسعار تنافسية بدون وسطاء.',
        'why_fast': 'رد سريع', 'why_fast_d': 'نرد خلال 24 ساعة في أيام العمل.',
        'why_global': 'شحن عالمي', 'why_global_d': 'شحن بحري وجوي وسريع حول العالم.',
        'why_quality': 'ضمان الجودة', 'why_quality_d': 'فحص جودة صارم قبل الشحن.',
        'co_company': 'الشركة', 'co_address': 'العنوان', 'co_phone': 'الهاتف', 'co_email': 'البريد الإلكتروني',
        'no_specs': 'لا توجد مواصفات.', 'no_product_image': 'لا توجد صورة للمنتج',
        'shipping_packing': 'الشحن والتغليف', 'after_sales_service': 'خدمة ما بعد البيع',
        'ship_pack': 'تغليف تصدير قياسي: كرتون/صندوق خشبي/منصة، مقاوم للرطوبة.',
        'ship_methods': 'الشحن: سريع (DHL/UPS/FedEx)، جوي، بحري.',
        'ship_lead': 'المدة: عينة 3-7 أيام، طلب كبير 15-30 يومًا.',
        'after_free': 'استبدال أو إعادة شحن مجانية لمشاكل الجودة.',
        'after_warranty': 'ضمان 12 شهرًا على معظم المنتجات.',
        'after_support': 'دعم فني وإرشاد في أي وقت.',
        'trust_factory': 'مباشرة من المصنع', 'trust_fast': 'شحن سريع', 'trust_quality': 'ضمان الجودة', 'trust_24h': 'خدمة 24 ساعة',
        'no_faq': 'لا توجد أسئلة شائعة بعد.',
        'sec_why_us': 'لماذا تختارنا', 'sec_team': 'فريقنا', 'sec_cases': 'حالات العملاء',
        'sec_news': 'الأخبار', 'sec_faq': 'الأسئلة الشائعة', 'sec_testimonials': 'آراء العملاء',
        'sec_stats': 'أرقام الشركة', 'sec_partners': 'شركاؤنا', 'sec_payments': 'طرق الدفع',
        'wa_help': 'تحتاج مساعدة؟ تواصل عبر واتساب', 'search_placeholder': 'ابحث في المنتجات والصفحات...', 'search_no_result': 'لم يتم العثور على نتائج.', 'cat_all': 'الكل', 'sec_certificates': 'الشهادات والمؤهلات', 'no_certificates': 'لا توجد شهادات بعد.', 'cta_title': 'مستعد لبدء مشروعك؟', 'cta_subtitle': 'احصل على عرض سعر مجاني خلال 24 ساعة.', 'cta_btn': 'احصل على عرض سعر',
        'sec_contacts': 'اتصل بنا', 'contacts_now_suffix': 'الآن',
        'sec_video': 'فيديو', 'sec_map': 'موقعنا', 'sec_trust': 'وعدنا', 'sec_friend_links': 'روابط',
        'about_founded': 'تأسست', 'about_scale': 'الحجم',
        'payments_desc': 'ندعم عدة طرق دفع آمنة لراحتك.',
        'no_payment': 'قم بإعداد طرق الدفع في لوحة الإدارة.',
        'no_video': 'قم بتعيين رابط الفيديو في لوحة الإدارة.',
        'browser_no_video': 'متصفحك لا يدعم تشغيل الفيديو.',
        'no_map': 'قم بتعيين عنوان أو رابط خريطة في لوحة الإدارة.',
        'inq_whatsapp': 'واتساب (اختياري)', 'inq_wechat': 'وي شات (اختياري)',
        'inq_required_hint': 'الاسم ووسيلة تواصل واحدة على الأقل (البريد الإلكتروني/واتساب/وي شات) مطلوبة.',
        'js_sending': 'جارٍ الإرسال...', 'js_required': 'يرجى ملء جميع الحقول المطلوبة.',
        'js_success': 'شكرًا لك! سنرد خلال 24 ساعة.',
        'js_mailto_sent': 'تم الإرسال عبر برنامج البريد. سنرد قريبًا.',
        'js_copied': 'تم النسخ: ', 'js_copy_manual': 'يرجى النسخ يدويًا: ',
        'dl_amazon_sold': 'تم بيع 1,200+', 'dl_pdd_group': 'مجموعة من 2', 'dl_pdd_sold': 'انضم 8,653 عنصرًا',
        'dl_alibaba_moq': 'الحد الأدنى للطلب: 100 قطعة', 'dl_alibaba_trade': 'ضمان التجارة', 'dl_alibaba_returns': 'إرجاع خلال 15 يومًا',
        'dl_rakuten_code': 'رقم السلعة', 'dl_rakuten_ship': 'الشحن: مجاني في جميع أنحاء البلاد',
        'dl_ebay_seller': 'البائع', 'dl_ebay_brand': 'جديد',
        'dl_walmart_rollback': 'تخفيض', 'dl_walmart_was': 'كان', 'dl_walmart_save': 'توفر 20%',
        'dl_etsy_handmade': 'صنع يدوي · جاهز للشحن',
        'dl_shopee_sold': 'تم بيع 5.2k',
        'dl_taobao_shop': 'المتجر الرسمي', 'dl_taobao_rating': 'الوصف 4.9 · الخدمة 4.8 · اللوجستيات 4.9',
        'jd_authentic': 'ضمان الأصالة', 'jd_fast': 'شحن سريع', 'jd_service': 'خدمة ما بعد البيع', 'jd_7day': 'إرجاع خلال 7 أيام',
        'in_stock_units': ' (%d قطعة)',
    },
}
# 板块级补充键（products_title / sec_about / trust 副标题）
_SECTION_EXTRA = {
    'en': {'products_title': 'Our Products', 'sec_about': 'About Us',
           'trust_factory_d': '100% authentic, quality assured.', 'trust_fast_d': 'Shipping within 24-48 hours.',
           'trust_quality_d': 'Worry-free support after purchase.', 'trust_24h_d': 'Online service around the clock.',
           'dl_shopee_ship': 'Free Shipping', 'dl_shopee_voucher': 'Voucher 10% off'},
    'zh': {'products_title': '我们的产品', 'sec_about': '关于我们',
           'trust_factory_d': '100% 正品，品质有保障。', 'trust_fast_d': '24-48 小时内发货。',
           'trust_quality_d': '售后无忧。', 'trust_24h_d': '全天候在线服务。'},
    'zh-Hant': {'products_title': '我們的產品', 'sec_about': '關於我們',
                'trust_factory_d': '100% 正品，品質有保障。', 'trust_fast_d': '24-48 小時內出貨。',
                'trust_quality_d': '售後無憂。', 'trust_24h_d': '全天候線上服務。'},
    'ja': {'products_title': '製品一覧', 'sec_about': '会社概要',
           'trust_factory_d': '100%本物、品質保証。', 'trust_fast_d': '24〜48時間以内に発送。',
           'trust_quality_d': 'アフター安心。', 'trust_24h_d': '年中無休のオンラインサービス。'},
    'ko': {'products_title': '우리 제품', 'sec_about': '회사 소개',
           'trust_factory_d': '100% 정품, 품질 보증.', 'trust_fast_d': '24-48시간 내 발송.',
           'trust_quality_d': 'A/S 걱정 없음.', 'trust_24h_d': '연중무휴 온라인 서비스.'},
    'de': {'products_title': 'Unsere Produkte', 'sec_about': 'Über uns',
           'trust_factory_d': '100% authentisch, Qualität garantiert.', 'trust_fast_d': 'Versand innerhalb von 24-48 Stunden.',
           'trust_quality_d': 'Sorgloser Kundendienst.', 'trust_24h_d': 'Online-Service rund um die Uhr.'},
    'es': {'products_title': 'Nuestros Productos', 'sec_about': 'Sobre Nosotros',
           'trust_factory_d': '100% auténticos, calidad garantizada.', 'trust_fast_d': 'Envío en 24-48 horas.',
           'trust_quality_d': 'Postventa sin preocupaciones.', 'trust_24h_d': 'Servicio online las 24 horas.'},
    'ru': {'products_title': 'Наши товары', 'sec_about': 'О нас',
           'trust_factory_d': '100% оригинально, гарантия качества.', 'trust_fast_d': 'Отправка в течение 24-48 часов.',
           'trust_quality_d': 'Надежный сервис.', 'trust_24h_d': 'Онлайн-сервис круглосуточно.'},
    'fr': {'products_title': 'Nos Produits', 'sec_about': 'À Propos',
           'trust_factory_d': '100% authentiques, qualité garantie.', 'trust_fast_d': 'Expédition sous 24-48 heures.',
           'trust_quality_d': 'SAV sans souci.', 'trust_24h_d': 'Service en ligne 24h/24.'},
    'pt': {'products_title': 'Nossos Produtos', 'sec_about': 'Sobre Nós',
           'trust_factory_d': '100% autênticos, qualidade garantida.', 'trust_fast_d': 'Envio em 24-48 horas.',
           'trust_quality_d': 'Pós-venda sem preocupações.', 'trust_24h_d': 'Serviço online 24 horas.'},
    'ar': {'products_title': 'منتجاتنا', 'sec_about': 'من نحن',
           'trust_factory_d': 'أصلي 100%، جودة مضمونة.', 'trust_fast_d': 'الشحن خلال 24-48 ساعة.',
           'trust_quality_d': 'خدمة ما بعد البيع.', 'trust_24h_d': 'خدمة عبر الإنترنت على مدار الساعة.'},
}
for _lang, _extra in _SECTION_EXTRA.items():
    I18N.setdefault(_lang, {}).update(_extra)

# Shopee 风格补充键（免运费 / 优惠券）
_SHOPEE_EXTRA = {
    'zh': {'dl_shopee_ship': '免运费', 'dl_shopee_voucher': '优惠券10%折扣'},
    'zh-Hant': {'dl_shopee_ship': '免運費', 'dl_shopee_voucher': '優惠券10%折扣'},
    'ja': {'dl_shopee_ship': '送料無料', 'dl_shopee_voucher': 'クーポン10%オフ'},
    'ko': {'dl_shopee_ship': '무료 배송', 'dl_shopee_voucher': '10% 할인 쿠폰'},
    'de': {'dl_shopee_ship': 'Kostenloser Versand', 'dl_shopee_voucher': 'Gutschein 10% Rabatt'},
    'es': {'dl_shopee_ship': 'Envío gratis', 'dl_shopee_voucher': 'Cupón 10% dto.'},
    'ru': {'dl_shopee_ship': 'Бесплатная доставка', 'dl_shopee_voucher': 'Купон со скидкой 10%'},
    'fr': {'dl_shopee_ship': 'Livraison gratuite', 'dl_shopee_voucher': 'Bon de réduction 10%'},
    'pt': {'dl_shopee_ship': 'Frete grátis', 'dl_shopee_voucher': 'Cupom 10% off'},
    'ar': {'dl_shopee_ship': 'شحن مجاني', 'dl_shopee_voucher': 'قسيمة خصم 10%'},
}
for _lang, _extra in _SHOPEE_EXTRA.items():
    I18N.setdefault(_lang, {}).update(_extra)

for _lang, _extra in I18N_EXTRA.items():
    I18N.setdefault(_lang, {}).update(_extra)

def t(lang, key, default=''):
    """按语言取固定文案，缺失时回退英文/默认值"""
    lang = lang or 'en'
    if lang not in I18N:
        lang = 'en'
    val = I18N[lang].get(key)
    if val is None:
        val = I18N['en'].get(key, default)
    return val

def detail_layout_by_id(layout_id):
    """按 id 取风格元数据，未知回退 classic"""
    for lay in DETAIL_LAYOUTS:
        if lay['id'] == layout_id:
            return lay
    return DETAIL_LAYOUTS[-1]


def detail_layouts():
    """返回全部平台风格列表（供 /api/detail_layouts 与表单下拉）"""
    return DETAIL_LAYOUTS


def i18n_languages():
    """返回支持的语言 id 列表"""
    return list(I18N.keys())


# ---------------- 询盘收集 ----------------

def save_inquiry(name, email, country, message, product_id=None, product_name='',
                 whatsapp='', wechat=''):
    """写入询盘记录，返回新记录 id"""
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO inquiries (name, email, country, message, product_id, product_name, whatsapp, wechat, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (name, email, country, message, product_id, product_name, whatsapp, wechat,
         datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def get_inquiries(limit=200):
    """读取询盘列表（最新在前）"""
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM inquiries ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_inquiry(iid):
    """删除指定询盘"""
    conn = get_db()
    cur = conn.execute('DELETE FROM inquiries WHERE id=?', (iid,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


# ---------------- 新手注册教程 ----------------

def tutorial_content():
    """新手教程：GitHub 注册、Token 获取、登录、翻墙注意事项（多语言）"""
    return {
        'title': '新手注册与发布教程',
        'subtitle': '从零开始，把你的外贸网站免费发布到 GitHub Pages',
        'steps': [
            {
                'no': 1,
                'title': '注册 GitHub 账号',
                'items': [
                    '打开官网 https://github.com 点击右上角 Sign up（注册）。',
                    '依次填写邮箱、密码、用户名，并完成人机验证（Puzzle）。',
                    '选择 Free 免费版即可，按提示完成邮箱验证（去邮箱点 Verify 链接）。',
                    '注册完成后在 GitHub 首页能看到自己的头像即成功。',
                ],
                'tips': '建议使用企业邮箱或常用邮箱；用户名会出现在你的网站地址里，尽量简洁好记。',
            },
            {
                'no': 2,
                'title': '获取 Personal Access Token（访问令牌）',
                'items': [
                    '登录 GitHub 后，点头像 → Settings → Developer settings → Personal access tokens。',
                    '方式一（推荐）Fine-grained：点击 Generate new token (fine-grained)，选择仓库，勾选 Contents 与 Pages 权限，有效期最长 1 年。',
                    '方式二 Classic：点击 Generate new token (classic)，勾选 repo 与 workflow 权限，有效期默认 30 天，可手动延长。',
                    '点击 Generate token 后，复制生成的 ghp_ 开头令牌，只显示一次，请立即粘贴到本工具后台。',
                ],
                'tips': 'Token 相当于密码，不要泄露给他人、不要提交到代码仓库；到期后到后台重新生成并更新即可。',
            },
            {
                'no': 3,
                'title': '在本工具登录并连接 GitHub',
                'items': [
                    '回到本工具后台，点击右上角「GitHub 登录」，填入 GitHub 用户名与刚才的 Token。',
                    '点击连接后，工具会自动校验仓库权限（repo/pages）。',
                    '首次使用建议新建仓库：填写仓库名（如 mysite），工具会自动创建并初始化。',
                    '之后点击「生成站点」→「部署到 GitHub Pages」，等待 1-3 分钟即可通过 https://用户名.github.io/仓库名 访问。',
                ],
                'tips': '部署失败时，到仓库 Settings → Pages 检查分支是否为 gh-pages 或 main；常见错误会在页面下方提示原因。',
            },
            {
                'no': 4,
                'title': '网络访问 GitHub 注意事项（翻墙/代理）',
                'items': [
                    '中国大陆网络访问 GitHub 可能不稳定，建议使用正规代理工具（科学上网）。',
                    '在代理软件中开启「全局模式」或为 github.com / api.github.com 添加代理规则。',
                    '系统代理设置：macOS 在 系统设置 → 网络 → 代理；Windows 在 设置 → 网络和 Internet → 代理。',
                    '命令行代理示例：git config --global http.proxy http://127.0.0.1:7890（端口以代理软件为准）。',
                    '常见失败排查：ping 不通 → 检查代理；token 无效 → 重新生成；仓库已存在 → 换仓库名；端口被占用 → 重启工具。',
                ],
                'tips': '使用代理时请遵守当地法律法规；GitHub Pages 国内访问偶尔较慢，可配置 CDN 加速。',
            },
        ],
    }


# ---------------- 站点统计 ----------------

def site_stats():
    """后台统计面板：产品数 / 询盘数 / 版本数 / 最近部署 / 部署次数"""
    conn = get_db()
    products = conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    inquiries = conn.execute('SELECT COUNT(*) AS c FROM inquiries').fetchone()['c']
    versions = conn.execute('SELECT COUNT(*) AS c FROM versions').fetchone()['c']
    deploy_count = get_config('deploy_count', 0)
    try:
        deploy_count = int(deploy_count or 0)
    except Exception:
        deploy_count = 0
    last_deploy = conn.execute('SELECT MAX(created_at) AS m FROM versions').fetchone()['m']
    conn.close()
    return {
        'products': products,
        'inquiries': inquiries,
        'versions': versions,
        'deploy_count': deploy_count,
        'last_deploy': last_deploy or '',
    }

# ---------------- 板块库定义 ----------------
# 每个板块：id / 名称 / 用途说明 / 默认标题 / 是否需要后台配置数据
SECTION_TYPES = [
    {'id': 'hero', 'name': 'Hero 横幅轮播', 'desc': '首页顶部大图轮播，展示品牌形象与主推产品，图片在「横幅轮播管理」上传。'},
    {'id': 'products', 'name': '产品列表', 'desc': '展示全部产品卡片（分类/价格/库存/支付按钮），点击进入京东式详情页。'},
    {'id': 'about', 'name': '公司介绍', 'desc': '展示公司简介与 Logo，塑造企业形象，可写公司故事与核心优势。'},
    {'id': 'why_us', 'name': '服务优势 Why Us', 'desc': '用图标+标题+说明的卡片矩阵呈现选择贵司的理由（品质/交期/售后等）。'},
    {'id': 'team', 'name': '团队介绍', 'desc': '展示核心团队成员头像、姓名、职位与简介，增强信任感。'},
    {'id': 'cases', 'name': '客户案例', 'desc': '展示成功案例/项目合作，用图片+标题+描述增强说服力。'},
    {'id': 'gallery', 'name': '作品画廊 Gallery', 'desc': '九宫格图片画廊，多图展示工厂实景、产品细节或项目案例照片（纯图片墙，点击可看大图）。'},
    {'id': 'news', 'name': '新闻/博客', 'desc': '发布公司新闻、行业动态、新品发布，利于 SEO 与客户了解动态。'},
    {'id': 'faq', 'name': 'FAQ 问答', 'desc': '常见问题问答（一个问题+一个回答，自动成条）。启用板块后前台自动出现 FAQ 独立页面并在导航展示；停用板块（或停用网站）后前台无 FAQ 页面。同时输出 FAQPage 结构化数据。'},
    {'id': 'testimonials', 'name': '客户评价', 'desc': '展示客户好评与评分，提升转化信任。'},
    {'id': 'stats', 'name': '数据统计', 'desc': '大数字展示（年产量/出口国家/客户数/年限，可自定义数字+标签），强化实力背书。'},
    {'id': 'partners', 'name': '客户 Logo 墙 / 合作伙伴', 'desc': '横向展示合作/客户品牌 Logo（支持图片+链接），体现市场认可。'},
    {'id': 'certificates', 'name': '资质证书', 'desc': '荣誉证书/专利/认证卡片墙，每项含证书图片、标题与说明。'},
    {'id': 'cta', 'name': '行动号召 CTA', 'desc': '醒目渐变横幅 + 按钮（标题/副标题/按钮文字/按钮链接），引导询盘转化。'},
    {'id': 'payments', 'name': '支付方式', 'desc': '展示支持的全球移动/网络支付渠道，配置在「支付配置」卡片，可自选多条并填收款账号/链接。'},
    {'id': 'contacts', 'name': '联系方式', 'desc': '展示全部联系方式按钮，客户可一键联系/复制。'},
    {'id': 'trust', 'name': '信任保障', 'desc': '图标化展示服务承诺（正品保障/极速发货/售后无忧等）。'},
    {'id': 'video', 'name': '视频展示', 'desc': '嵌入 YouTube/Vimeo 等视频，展示产品演示或公司宣传片。'},
    {'id': 'map', 'name': '地图', 'desc': '嵌入 Google 地图或展示公司地址，方便客户查找。'},
    {'id': 'friend_links', 'name': '友情链接', 'desc': '展示友情链接（可配置 nofollow），链接管理在「友情链接」卡片。'},
]
SECTION_TYPES.append({'id': 'spider_pool', 'name': '高级试验：隐藏链接', 'desc': '高风险试验，默认不输出。需要在 SEO 高级试验区单独开启；不保证排名提升。', 'risk': 'blackhat'})
SECTION_TYPE_IDS = [s['id'] for s in SECTION_TYPES]


def _parse_content(raw):
    """把板块 content 解析为 dict；兼容双重 JSON 编码（str 再 parse 一次）"""
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw) if isinstance(raw, str) and raw.strip() else {}
    except Exception:
        return {}
    while isinstance(v, str):
        try:
            v = json.loads(v)
        except Exception:
            break
    return v if isinstance(v, dict) else {}


def get_sections(enabled_only=True):
    """读取板块列表（按 sort_order 排序）"""
    conn = get_db()
    sql = 'SELECT * FROM sections'
    if enabled_only:
        sql += ' WHERE enabled=1'
    sql += ' ORDER BY sort_order ASC, id ASC'
    rows = conn.execute(sql).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d['content'] = _parse_content(d.get('content'))
        out.append(d)
    return out


def get_pages(enabled_only=True):
    """读取自定义页面列表"""
    conn = get_db()
    sql = 'SELECT * FROM pages'
    if enabled_only:
        sql += ' WHERE enabled=1'
    sql += ' ORDER BY sort_order ASC, id ASC'
    rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_friend_links():
    """读取友情链接"""
    conn = get_db()
    rows = conn.execute('SELECT * FROM friend_links ORDER BY sort_order ASC, id ASC').fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_categories(enabled_only=True):
    """分类列表：优先取 categories 表；若为空则从 products.category 去重推导（demo 站常不填 categories 表）"""
    conn = get_db()
    rows = conn.execute('SELECT id, name FROM categories ORDER BY sort_order ASC, id ASC').fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT DISTINCT category AS name FROM products WHERE category IS NOT NULL AND category != '' ORDER BY category ASC").fetchall()
        rows = [{'id': i + 1, 'name': r['name']} for i, r in enumerate(rows)]
    conn.close()
    return [dict(r) for r in rows]


def get_product_count():
    """产品总数（products 表无 enabled 列）"""
    conn = get_db()
    c = conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
    conn.close()
    return c


def company_info():
    """公司信息（来自 site_config）"""
    return {
        'name': get_config('company_name', ''),
        'logo': get_config('company_logo', ''),
        'brief': get_config('company_brief', ''),
        'address': get_config('company_address', ''),
        'phone': get_config('company_phone', ''),
        'email': get_config('company_email', ''),
        'whatsapp': get_config('company_whatsapp', ''),
        'founded': get_config('company_founded', ''),
        'size': get_config('company_size', ''),
        'industry': get_config('company_industry', ''),
        'products': get_config('company_products', ''),
        'workshop_area': get_config('company_workshop_area', ''),
        'certifications': get_config('company_certifications', ''),
        'warranty': get_config('company_warranty', ''),
        'footer_copyright': get_config('footer_copyright', ''),
        'footer_icp': get_config('footer_icp', ''),
    }


def seo_site():
    """站点级 SEO / AI GEO 配置

    AI GEO（生成式引擎优化，Generative Engine Optimization）配置：
    - brand_summary: 品牌一句话简介（ChatGPT/Gemini/Perplexity 等引用品牌时的默认描述）
    - selling_points: 核心卖点（每行一条，3-8 条，AI 引荐时使用）
    - target_markets: 目标客户市场（每行一个）
    - certifications: 认证资质（每行一个）
    - service_capabilities: 服务能力（每行一条：OEM/ODM/交期/MOQ/样品）
    - faq: 常见问题 list（[{q,a},...]），llms/FAQPage 优先于板块 FAQ
    - ai_enabled: 是否允许 AI 引擎引用本品牌内容（1/0）
    - site_url: 站点正式发布网址（用于 canonical / hreflang / sitemap / llms.txt 绝对链接）
    """
    return {
        'title': get_config('seo_site_title', ''),
        'site_title': get_config('seo_site_title', ''),
        'site_description': get_config('seo_site_description', ''),
        'site_keywords': get_config('seo_site_keywords', ''),
        'description': get_config('seo_site_description', ''),
        'keywords': get_config('seo_site_keywords', ''),
        'author': get_config('seo_author', ''),
        'robots': get_config('seo_robots', 'index,follow'),
        'hidden_keywords': get_config('seo_hidden_keywords', ''),
        'geo_address': get_config('geo_address', ''),
        'geo_region': get_config('geo_region', ''),
        # ---- AI GEO ----
        'brand_summary': get_config('geo_brand_summary', ''),
        'selling_points': get_config('geo_selling_points', ''),
        # ---- AI GEO 精致化（P2）：目标市场 / 认证 / 服务能力 / FAQ ----
        'target_markets': _geo_lines('geo_target_markets'),
        'certifications': _geo_lines('geo_certifications'),
        'service_capabilities': _geo_lines('geo_service_capabilities'),
        'faq': _geo_faq_pairs(),
        'ai_enabled': get_config('geo_ai_enabled', '1'),
        'training_enabled': get_config('geo_training_enabled', '0'),
        'site_url': get_config('site_url', ''),
        'analytics_code': get_config('analytics_code', ''),
        'cookie_enabled': get_config('cookie_enabled', '1'),
    }


# ---------------- AI GEO 辅助 ----------------

def _brand_name_fallback(site_name='My Export Site'):
    """站点品牌兜底名：公司名 > 站点名 > 默认"""
    comp = company_info()
    return (comp.get('name') or site_name or 'My Export Site').strip()


def _geo_ai_enabled():
    """AI 展示开关：是否允许 AI 引擎引用本站内容（默认允许）"""
    return str(get_config('geo_ai_enabled', '1')).strip().lower() in ('1', 'true', 'on', 'yes', '允许', '开启')


def _site_url_base():
    """正式发布网址（去尾部斜杠），未配置返回空串"""
    return valid_site_url(get_config('site_url', ''))


def _page_abs_url(page_name='index.html'):
    """页面最终 URL：配置了正式网址用绝对地址，否则用相对文件路径"""
    base = _site_url_base()
    if page_name in ('', 'index.html', './', '/'):
        page_name = 'index.html'
    if base:
        return base + '/' + page_name if page_name != 'index.html' else base + '/'
    return page_name


def _selling_points_list():
    """核心卖点列表（每行一条，最多 8 条）"""
    raw = (get_config('geo_selling_points', '') or '')
    pts = [ln.strip() for ln in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
    return pts[:8]


def _geo_lines(key, max_n=50):
    """site_config 多行文本字段 → 去空行列表（目标市场 / 认证 / 服务能力共用）"""
    raw = (get_config(key, '') or '')
    vals = [ln.strip() for ln in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n') if ln.strip()]
    return vals[:max_n]


def _geo_faq_pairs():
    """geo_faq（AI GEO FAQ）→ [(q, a), ...]；site_config 存 JSON 字符串 [{q,a},...]"""
    raw = (get_config('geo_faq', '') or '').strip()
    if not raw:
        return []
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(items, list):
        return []
    pairs = []
    for it in items[:50]:
        if isinstance(it, dict):
            q = str(it.get('q') or '').strip()[:300]
            a = str(it.get('a') or '').strip()[:3000]
            if q and a:
                pairs.append((q, a))
    return pairs


def _seo_keywords_all():
    """站点关键词全集：经典 keywords + 补充关键词（白帽用途，随 meta / JSON-LD 输出，不再渲染隐藏文字）"""
    seo = seo_site()
    keys = []
    if seo.get('keywords'):
        keys.append(seo['keywords'])

    return ', '.join([k for k in keys if k])


def _site_alt_fallback():
    """图片 alt 兜底文案：品牌名（用于板块图/背景图等缺少描述的场景）"""
    return _brand_name_fallback()


def _same_as_links():
    """Organization sameAs：联系方式中可公开展示的主页型链接（Website/社媒等）"""
    conn = get_db()
    try:
        rows = conn.execute('SELECT contact_type, contact_value FROM contacts ORDER BY id ASC').fetchall()
    finally:
        conn.close()
    links = []
    for r in rows:
        ct = str(r['contact_type'] or '').strip()
        cv = str(r['contact_value'] or '').strip()
        if not cv:
            continue
        if ct in ('Website', 'AliTrade', 'Facebook', 'Instagram', 'YouTube', 'TikTok', 'LinkedIn', 'Trademanager'):
            url = cv
            if ct in ('Facebook', 'Instagram', 'YouTube', 'TikTok', 'LinkedIn'):
                url = 'https://' + cv.lstrip('/') if not cv.startswith('http') else cv
            if url.startswith(('http://', 'https://')):
                links.append(url)
    return links[:8]


def _faq_pairs_from_text(content):
    """从富文本/纯文本中启发式提取 (问题, 答案) 对，用于 FAQPage JSON-LD（AI 可直接引用）"""
    if not content:
        return []
    text = str(content).replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'<[^>]+>', '', text)
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
    pairs = []
    i = 0
    while i < len(lines):
        if re.search(r'[?？]', lines[i]) and len(lines[i]) <= 180:
            q = lines[i].strip()[:160]
            # 答案：问题行之后若干非问题行（最多 6 行，压缩为一段）
            ans_lines = []
            j = i + 1
            while j < len(lines) and len(ans_lines) < 6 and not re.search(r'[?？]$', lines[j]):
                ans_lines.append(lines[j])
                j += 1
            ans = ' '.join(ans_lines)[:500] if ans_lines else ''
            if ans:
                pairs.append((q, ans))
            i = j
        else:
            i += 1
    return pairs[:20]


def _faq_ld_html(pairs, main_entity_only=False):
    """FAQPage JSON-LD HTML"""
    if not pairs:
        return ''
    qlist = [{'@type': 'Question', 'name': q,
              'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in pairs]
    return '<script type="application/ld+json">%s</script>' % json.dumps(
        {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': qlist},
        ensure_ascii=False).replace('<', chr(92) + 'u003c')


def _jsonld_script(obj):
    return '<script type="application/ld+json">%s</script>' % json.dumps(obj, ensure_ascii=False).replace('<', chr(92) + 'u003c')


def esc(s):
    return html.escape(str(s if s is not None else ''))


def row_get(row, key, default=''):
    """安全读取 sqlite3.Row 字段（兼容旧库缺少新列的情况）"""
    try:
        if key in row.keys():
            val = row[key]
            return val if val is not None else default
    except Exception:
        pass
    return default


def _site_img_url(rel, prefix='static/uploads/'):
    """后台图片路径 /uploads/xxx.png -> 站点内可访问路径（生成站为 static/uploads/，预览为 /uploads/）"""
    if not rel:
        return ''
    if str(rel).startswith(('http://', 'https://', '//')):
        from catalog_data import web_url
        try:
            return web_url(rel)
        except ValueError:
            return ''
    if re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', str(rel)):
        return ''
    return prefix + os.path.basename(rel)


def site_img(rel, prefix='static/uploads/'):
    return esc(_site_img_url(rel, prefix))



def contact_href(ctype, value):
    """根据联系方式类型生成可点击链接；无法直连的类型返回 ''（前端走复制）"""
    v = str(value or '').strip()
    if not v:
        return ''
    if ctype == 'WhatsApp':
        digits = ''.join(ch for ch in v if ch.isdigit())
        return 'https://wa.me/' + digits if digits else ''
    if ctype == '电话':
        return 'tel:' + v
    if ctype == 'Email':
        return 'mailto:' + v
    if ctype == 'Telegram':
        return 'https://t.me/' + v.lstrip('@')
    if ctype == 'Skype':
        return 'skype:' + v + '?chat'
    if ctype == 'LINE':
        return 'https://line.me/R/ti/p/~' + v
    if ctype == 'Facebook':
        return 'https://facebook.com/' + v.lstrip('/')
    if ctype == 'Instagram':
        return 'https://instagram.com/' + v.lstrip('@/')
    if ctype == 'YouTube':
        return 'https://youtube.com/@' + v.lstrip('@/')
    if ctype == 'TikTok':
        return 'https://tiktok.com/@' + v.lstrip('@/')
    if ctype == 'LinkedIn':
        return 'https://linkedin.com/in/' + v.lstrip('/')
    if ctype in ('Website', 'AliTrade'):
        return v if v.startswith(('http://', 'https://')) else 'https://' + v
    if ctype in ('Twitter', 'X'):
        return v if v.startswith(('http://', 'https://')) else 'https://twitter.com/' + v.lstrip('@/')
    if ctype == 'Trademanager':
        return 'https://wa.me/?text=' + quote('Alibaba Trademanager: ' + v)
    return ''



def product_images(p):
    """产品多图列表（images JSON 优先，回退 img 单图）"""
    imgs = []
    raw = row_get(p, 'images', '')
    if raw:
        try:
            imgs = json.loads(raw)
        except Exception:
            imgs = []
    if not imgs and p['img']:
        imgs = [p['img']]
    return imgs


# ---------------- 支付配置 ----------------

# 全球主流移动/网络支付渠道展示名（前台英文外贸风；未知类型回落为首字母大写）
PAY_LABELS = {
    'paypal': 'PayPal', 'stripe': 'Stripe',
    'visa': 'Visa', 'mastercard': 'Mastercard', 'amex': 'American Express', 'jcb': 'JCB',
    'discover': 'Discover', 'card': 'Credit / Debit Card',
    'applepay': 'Apple Pay', 'googlepay': 'Google Pay',
    'unionpay': 'UnionPay', 'alipay': 'Alipay', 'wechat': 'WeChat Pay',
    'usdt': 'USDT (Crypto)', 'bitcoin': 'Bitcoin (Crypto)',
    'banktt': 'Bank Transfer (T/T)', 'westernunion': 'Western Union', 'moneygram': 'MoneyGram', 'wise': 'Wise',
    'payoneer': 'Payoneer', 'skrill': 'Skrill', 'neteller': 'Neteller',
    'cashapp': 'Cash App', 'venmo': 'Venmo', 'zelle': 'Zelle',
    'webmoney': 'WebMoney', 'yandexpay': 'Yandex Pay', 'pix': 'Pix', 'oxxo': 'OXXO',
    'klarna': 'Klarna', 'afterpay': 'Afterpay', 'shoppay': 'Shop Pay',
    'paytm': 'Paytm', 'gcash': 'GCash', 'grabpay': 'GrabPay', 'touchngo': "Touch 'n Go",
    'dana': 'DANA', 'ovo': 'OVO', 'maya': 'Maya', 'kakao': 'KakaoPay', 'naver': 'Naver Pay',
    'linepay': 'LINE Pay', 'phonepe': 'PhonePe', 'razerpay': 'RazerPay', 'razorpay': 'Razorpay',
    'paynow': 'PayNow', 'promptpay': 'PromptPay',
    'kpay': 'KBZ Pay', 'bkash': 'bKash', 'mpesa': 'M-Pesa',
    'custom': 'Custom Link',
    'other': 'Other',
}

PAY_BRANDS = {
    # id -> 品牌色（用于前台徽章字标 / 后台行预览）；无品牌色渠道前台自动用中性灰
    'paypal': '#003087', 'stripe': '#635bff', 'visa': '#1a1f71', 'mastercard': '#eb001b',
    'amex': '#2e77bb', 'jcb': '#0b4c9e', 'discover': '#f76f1c', 'card': '#5a6577',
    'applepay': '#0b0b0d', 'googlepay': '#4285f4', 'unionpay': '#c8102e',
    'alipay': '#1677ff', 'wechat': '#07c160',
    'usdt': '#26a17b', 'bitcoin': '#f7931a', 'cashapp': '#00c244', 'venmo': '#3d95ce',
    'zelle': '#6d1ed4', 'klarna': '#e0416f', 'afterpay': '#1f9d64', 'shoppay': '#5a31f4',
    'payoneer': '#ff6b00', 'skrill': '#941b80', 'neteller': '#8fc31f', 'wise': '#0a6e52',
    'webmoney': '#0b61c5', 'yandexpay': '#fc3f1d', 'pix': '#32bcad', 'oxxo': '#1a6ed8',
    'paytm': '#002e6e', 'gcash': '#0071ce', 'grabpay': '#00b14f', 'touchngo': '#009a44',
    'dana': '#108ee9', 'ovo': '#512da8', 'maya': '#2557e7', 'kakao': '#ffcd00',
    'naver': '#03c75a', 'linepay': '#06c755', 'phonepe': '#5f259f', 'razorpay': '#3395ff',
    'razerpay': '#00a84d', 'paynow': '#f36f21', 'promptpay': '#5e2c8e', 'kpay': '#1eae4c',
    'bkash': '#e2136e', 'mpesa': '#00a94e', 'banktt': '#2563eb', 'westernunion': '#d71920',
    'moneygram': '#ff6600', 'custom': '#5a6577', 'other': '#6b7280',
}

# 系统内置真实品牌 logo SVG 资源目录（Simple Icons CC0 免费许可，static/pay_icons/{渠道id}.svg）。
# 由生成站点复制到 output_site/static/pay_icons/，后台预览经 /static/pay_icons/ 访问，单源一致。
PAY_ICON_DIR = os.path.join(BASE_DIR, 'static', 'pay_icons')
_pay_icon_file_cache = None


def pay_icon_files():
    """内置品牌 logo 文件清单：{渠道id: 'pay_icons/xxx.svg'}。
    有官方免费 SVG 资源（如 PayPal/Visa/Mastercard/Stripe 等）的渠道收录于此；
    无官方单色资源的通用/地区渠道不收录，前台回退纯品牌字标。"""
    global _pay_icon_file_cache
    if _pay_icon_file_cache is not None:
        return _pay_icon_file_cache
    out = {}
    try:
        for fn in sorted(os.listdir(PAY_ICON_DIR)):
            if fn.endswith('.svg'):
                out[fn[:-4]] = 'pay_icons/' + fn
    except OSError:
        pass
    _pay_icon_file_cache = out
    return out


def _pay_icon_src(rel, img_prefix='static/uploads/'):
    """内置品牌 logo 相对站点根 / 服务根路径：
    - 生成站（img_prefix=static/uploads/）→ static/pay_icons/xxx.svg
    - 后台预览/API 预览（img_prefix=/uploads/）→ /static/pay_icons/xxx.svg"""
    if img_prefix.startswith('/'):
        return '/static/' + rel
    # 生成站资源统一放在 static/ 下，rel 形如 'pay_icons/xxx.svg'
    return 'static/' + rel


def _payment_badge_html(m, img_prefix='static/uploads/'):
    """单个支付徽章：优先渲染自定义上传图标（img）；无上传图标时，若渠道有内置真实官方品牌
    logo SVG（static/pay_icons/ 内的 Simple Icons CC0 资源）则直接加载该 logo 文件；
    无官方 logo 资源的通用/地区渠道回退到纯品牌字标（wordmark 文本），不再使用自绘渐变徽章。"""
    label = m.get('label') or ''
    icon = (m.get('icon') or '').strip()
    esc_label = esc(label)
    if icon:
        src = site_img(icon, img_prefix) if icon.startswith('/uploads/') else icon
        return ('<span class="pm pm-img" title="%s"><img class="pm-ico" src="%s" alt="%s" loading="lazy">'
                '<span class="pm-name">%s</span></span>'
                % (esc_label, esc(src), esc_label, esc_label))
    pid = m.get('id') or ''
    rel = pay_icon_files().get(pid)
    if rel:
        src = _pay_icon_src(rel, img_prefix)
        return ('<span class="pm pm-svg" title="%s"><img class="pm-logo" src="%s" alt="%s" loading="lazy"></span>'
                % (esc_label, esc(src), esc_label))
    color = PAY_BRANDS.get(pid, '#5b6572')
    return '<span class="pm pm-txt" title="%s" style="--pmc:%s"><span class="pm-name">%s</span></span>' \
           % (esc_label, color, esc_label)


def payment_methods():
    """读取已配置支付方式列表：[{id,label,value,icon}]。
    icon 为自定义渠道上传的图标路径（/uploads/xxx.png 或 ''）。
    兼容旧版 4 个固定字段（paypal_email/stripe_link/custom_*），避免老数据丢失。"""
    raw = get_config('pay_methods_json')
    # 仅当从未写入新结构（None/''）时才回落旧字段；显式保存的空列表 '[]' 表示用户已清空渠道，不得回落
    has_new = raw is not None and str(raw).strip() != ''
    try:
        arr = json.loads(raw) if has_new else []
    except Exception:
        arr = []
    if not isinstance(arr, list):
        arr = []
    out, seen = [], set()
    for it in arr:
        if not isinstance(it, dict):
            continue
        pid = str(it.get('type') or '').strip().lower()
        val = str(it.get('value') or '').strip()
        nm = str(it.get('name') or '').strip()
        icon = str(it.get('icon') or '').strip()
        if not pid:
            continue
        key = ('other:' + nm.lower()) if pid == 'other' and nm else pid
        if key in seen:
            continue
        seen.add(key)
        if pid == 'other' and nm:
            label = nm
        elif pid == 'custom' and get_config('custom_label'):
            label = get_config('custom_label')
        else:
            label = PAY_LABELS.get(pid, pid.replace('_', ' ').title())
        out.append({'id': pid, 'label': label, 'value': val, 'icon': icon})
    # 兼容旧版固定字段配置（paypal_email / stripe_link / custom_link）——仅当无新结构时执行
    if not has_new:
        legacy = [
            ('paypal', get_config('paypal_email')),
            ('stripe', get_config('stripe_link')),
            ('custom', get_config('custom_link')),
        ]
        for pid, val in legacy:
            val = (val or '').strip()
            if not val or pid in seen:
                continue
            seen.add(pid)
            label = get_config('custom_label') if pid == 'custom' and get_config('custom_label') else PAY_LABELS.get(pid, 'Custom')
            out.append({'id': pid, 'label': label, 'value': val, 'icon': ''})
    return out


def payment_badges_html(limit=0, img_prefix='static/uploads/', with_title=False):
    """纯展示徽章行：不可点击、无按钮行为；limit>0 时仅取前 N 个并显示剩余计数（用于产品卡等紧凑区）"""
    ms = payment_methods()
    if not ms:
        return ''
    shown = ms[:limit] if limit > 0 else ms
    inner = ''.join(_payment_badge_html(m, img_prefix) for m in shown)
    if limit > 0 and len(ms) > len(shown):
        inner += '<span class="pm pm-more" title="%s">+%d</span>' % (
            esc(', '.join(m['label'] for m in ms[len(shown):])), len(ms) - len(shown))
    head = ('<span class="pay-badges-title">We accept</span>' if with_title else '')
    return '<div class="pay-badges">%s%s</div>' % (head, inner)


def payment_panel_html(p=None, img_prefix='static/uploads/'):
    """产品详情页的支付展示面板：纯徽章横向排列，仅声明支持渠道，无链接无按钮"""
    if not payment_methods():
        return ''
    return ('<div class="pay-panel">'
            '<h3>We accept</h3>'
            '<p class="pay-tip">Secure payment via global mobile &amp; online payment methods</p>%s</div>'
            % payment_badges_html(0, img_prefix))


# ---------------- 联系方式区块 ----------------

# 统一渠道解析：把 DB 行转换为前台渲染字典
def _std_contact(c):
    """DB contacts 行 -> dict(label,value,href,kind,verb,color,short)"""
    ct = str(c['contact_type'] or '').strip()
    val = str(c['contact_value'] or '').strip()
    if not val:
        return None
    key, d = _contact_std_lookup(ct, val)
    if not d:
        # 完全未知类型：按复制展示（保留类型名）
        return {'label': ct or 'Contact', 'value': val, 'href': '', 'kind': 'copy',
                'verb': '', 'color': '#5b6572', 'short': (ct or '?')[:2].upper()}
    label, color, verb, short = d['label'], d['color'], d['verb'], d['short']
    # 小写键 key 若为中文(电话/微信) 还原为英文再求 href
    href_ctype = {'电话': '电话', '微信': '微信'}.get(key, label)
    href = contact_href(href_ctype, val)
    kind = 'link' if href else 'text'
    if key in ('phone', 'tel', '电话') and href:
        kind = 'link'
    elif key in ('wechat', '微信', 'qq', 'address') and not href:
        kind = 'copy' if key in ('wechat', '微信', 'qq') else 'text'
    # 社交类型值已是完整链接（如后台直接填 https://...）直接直达
    if val.startswith(('http://', 'https://')) and label not in ('Email',):
        href = val
        kind = 'link'
    # 未知类型识别为 email/phone/website 时一并归入直达
    if not href and _contact_std_lookup('', val)[1] is not None:
        k2, d2 = _contact_std_lookup('', val)
        href = contact_href({'phone': '电话', 'email': 'Email', 'website': 'Website'}.get(k2, 'Website'), val) or ''
        kind = 'link' if href else 'text'
    return {'label': label, 'value': val, 'href': href, 'kind': kind,
            'verb': verb, 'color': color, 'short': short, 'raw_type': ct}


def _contact_items():
    """读取并规范全部联系方式（过滤空值、相同 href/值去重，杜绝重复堆叠）"""
    conn = get_db()
    rows = conn.execute('SELECT * FROM contacts ORDER BY id ASC').fetchall()
    conn.close()
    out, seen = [], set()
    for c in rows:
        it = _std_contact(c)
        if not it:
            continue
        if it['kind'] == 'link':
            k = 'l:' + (it['href'] or '')
        else:
            k = 't:' + it['label'] + ':' + (it['value'] or '').strip().lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def _contact_badge_html(it, size=40):
    """品牌徽章：品牌色圆形底 + 白字标识（WhatsApp 用官方图标路径）"""
    short = it['short'] or '?'
    if it['label'] == 'WhatsApp' and short == 'WA':
        inner = ('<svg viewBox="0 0 32 32" width="18" height="18" aria-hidden="true"><path fill="#fff" d="M16.1 3C9.3 3 3.8 8.5 3.8 15.3c0 2.4.7 4.8 2 6.8L4 28.4l6.5-1.8c2 .8 3.8 1.2 5.6 1.2 6.8 0 12.3-5.5 12.3-12.3S22.9 3 16.1 3zm0 22.2c-1.9 0-3.8-.5-5.4-1.5l-.4-.2-4 1.1 1.1-3.9-.3-.4c-1.2-1.7-1.9-3.8-1.9-6 0-5.5 4.5-10 10-10s10 4.5 10 10-4.5 10-10 10zm5.5-7.5c-.3-.2-1.8-.9-2.1-1-.3-.1-.5-.2-.7.2-.2.3-.8 1-.9 1.2-.2.2-.3.2-.6.1-.3-.2-1.3-.5-2.4-1.5-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6l.5-.6c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.6-.1-.2-.7-1.7-1-2.3-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.2 5.1 4.5.7.3 1.3.5 1.7.6.7.2 1.4.2 1.9.1.6-.1 1.8-.7 2-1.4.3-.7.3-1.3.2-1.4-.1-.1-.2-.2-.5-.4z"/></svg>')
    else:
        inner = esc(short)
    return ('<span class="cc-badge" style="--ccb:%s" aria-hidden="true">%s</span>'
            % (it['color'], inner))


def _contact_go_html(it):
    """直达按钮/不可链接文本/复制按钮的统一小部件"""
    label, value = it['label'], it['value']
    if it['kind'] == 'link':
        rel = ' target="_blank" rel="noopener"' if it['href'].startswith(('http://', 'https://')) else ''
        return ('<a class="cc-go" href="%s"%s><span class="cc-go-verb">%s</span>'
                '<span class="cc-go-ic">↗</span></a>'
                % (esc(it['href']), rel, esc(it['verb'] or 'Open')))
    if it['kind'] == 'copy':
        return ('<button type="button" class="cc-go cc-go-copy" onclick="copyText(\'%s\')"><span class="cc-go-verb">Copy</span></button>'
                % esc(value).replace('\\', '\\\\').replace('\'', '\\\''))
    if it['kind'] == 'text':
        return '<span class="cc-text">%s</span>' % esc(value)
    return ''


def _contact_card_html(it):
    """单渠道卡片：图标徽章 + 品牌名 + 直达按钮。可直连渠道（link）不裸显号码/URL，
    仅保留按钮直达；不可链接渠道（address 文本 / 复制类）在值区显示一次可读文本。"""
    val_html = ''
    if it['kind'] != 'link':
        val_html = '<span class="cc-val">%s</span>' % esc(it['value'])
    return ('<div class="cc-item">%s<div class="cc-meta">'
            '<span class="cc-name">%s</span>%s</div>%s</div>'
            % (_contact_badge_html(it), esc(it['label']), val_html,
               _contact_go_html(it)))


def contact_buttons_html(img_prefix='static/uploads/'):
    """前台联系方式区（首页联系板块）：统一「品牌徽章+品牌名」直达按钮行，禁止号码文本重复堆叠。
    可直连渠道为可点击按钮；仅能复制的渠道点击复制；地址等显示文本。"""
    items = _contact_items()
    if not items:
        return ''
    pills = []
    for it in items:
        if it['kind'] == 'link':
            rel = ' target="_blank" rel="noopener"' if it['href'].startswith(('http://', 'https://')) else ''
            pills.append('<a class="cc-pill" style="--ccb:%s" href="%s"%s title="%s">%s<span>%s</span></a>'
                         % (it['color'], esc(it['href']), rel, esc(it['label']),
                            _contact_badge_html(it, 24), esc(it['label'])))
        elif it['kind'] == 'copy':
            pills.append('<button type="button" class="cc-pill cc-pill-copy" style="--ccb:%s" onclick="copyText(\'%s\')" title="%s">%s<span>%s</span></button>'
                         % (it['color'], esc(it['value']).replace('\\', '\\\\').replace('\'', '\\\''),
                            esc(it['label']), _contact_badge_html(it, 24), esc(it['label'])))
        else:
            pills.append('<span class="cc-pill cc-pill-text" style="--ccb:%s" title="%s">%s<span>%s</span></span>'
                         % (it['color'], esc(it['value']), _contact_badge_html(it, 24), esc(it['label'])))
    out = '<div class="cc-pills">' + ''.join(pills) + '</div>'
    return out


def inquire_panel_html(links, img_prefix='static/uploads/', lang='en'):
    """无在线支付时展示的询盘面板：提示联系获取报价/起订量，并列联系方式"""
    btns = contact_buttons_html(img_prefix)
    body = ('<div class="inquire-box"><h4>📩 %s</h4>'
            '<p class="inq-sub">%s</p>'
            % (t(lang, 'inq_title'), t(lang, 'inq_sub')))
    if btns:
        body += btns
    body += ('<a class="btn btn-light inq-more" href="%s">%s →</a>'
             '</div>' % (links['contact'], t(lang, 'nav_contact')))
    return body


def contact_direct_html(lang='en', compact=False):
    """“直接联系我们”统一卡片区：每种联系方式一个卡片（品牌徽章+名称+值+直达按钮），
    号码/链接只出现一次。可直连类型：WhatsApp wa.me / Phone tel: / Email mailto:
    社交型 URL 新窗直达；仅可复制渠道（微信/QQ）点按复制；地址清晰文本展示。"""
    items = _contact_items()
    if not items:
        return '<div class="empty-tip">%s</div>' % esc(t(lang, 'no_contact'))
    cls = 'cc-grid' + (' cc-grid-compact' if compact else '')
    inner = ''.join(_contact_card_html(it) for it in items)
    return ('<div class="contact-direct-wrap" id="contact-direct">'
            '<h4 class="cd-title">📞 %s</h4>'
            '<p class="cd-sub">%s</p>'
            '<div class="%s">%s</div>'
            '</div>'
            % (esc(t(lang, 'inq_direct_title')), esc(t(lang, 'inq_direct_sub')), cls, inner))


def inquire_form_html(links, img_prefix='static/uploads/', lang='en', product=None):
    """B2B 询盘表单：姓名/邮箱/国家/WhatsApp/微信/留言；无后端时展示联系方式直联"""
    pid = product['id'] if product else 0
    pname = esc((product['name'] if product else ''))
    # 表单下方附“直接联系我们”联系方式（电话 / WhatsApp / 微信 / 邮箱）
    _conn = get_db()
    _contacts = _conn.execute('SELECT contact_type, contact_value FROM contacts ORDER BY id ASC').fetchall()
    _conn.close()
    _direct = []
    for _c in _contacts:
        _cv = str(_c['contact_value'] or '').strip()
        if not _cv:
            continue
        _ct = str(_c['contact_type'] or '').strip()
        if _ct in ('电话', 'phone', 'tel', 'Phone'):
            _direct.append('<a class="if-direct-link" href="tel:%s">📞 %s</a>' % (esc(_cv.replace(' ', '')), esc(_cv)))
        elif _ct in ('WhatsApp', 'whatsapp', 'WhatsApp 号码', 'WhatsApp号码'):
            _wa = _cv.replace('+', '').replace(' ', '').replace('-', '')
            _direct.append('<a class="if-direct-link" href="https://wa.me/%s" target="_blank" rel="noopener">WhatsApp: %s</a>' % (esc(_wa), esc(_cv)))
        elif _ct in ('微信', 'wechat', 'WeChat'):
            _direct.append('<span class="if-direct-link">微信: %s</span>' % esc(_cv))
        elif _ct in ('Email', 'email', '邮箱', 'E-mail', 'E-Mail'):
            _direct.append('<a class="if-direct-link" href="mailto:%s">✉️ %s</a>' % (esc(_cv), esc(_cv)))
        else:
            _direct.append('<span class="if-direct-link">%s: %s</span>' % (esc(_ct), esc(_cv)))
    contact_block = ('<div class="if-direct"><span class="if-direct-label">%s</span><span class="if-direct-list">%s</span></div>'
                     % (esc(t(lang, 'inq_direct')), '&nbsp;&nbsp;'.join(_direct))) if _direct else ''
    return ('''
<div class="inquiry-form-wrap" data-pid="%d" data-pname="%s">
  <h4 class="if-title">📩 %s</h4>
  <p class="if-sub">%s</p>
  <form class="inquiry-form" onsubmit="return submitInquiry(this)">
    <input type="hidden" name="product_id" value="%d">
    <input type="hidden" name="product_name" value="%s">
    <div class="if-grid">
      <div class="if-field"><label>%s *</label><input type="text" name="name" required placeholder="John Smith"></div>
      <div class="if-field"><label>%s</label><input type="email" name="email" placeholder="sales@example.com"></div>
      <div class="if-field"><label>%s</label><input type="text" name="country" placeholder="China / USA / Germany..."></div>
      <div class="if-field"><label>%s</label><input type="text" name="whatsapp" placeholder="+86 138 0000 0000"></div>
      <div class="if-field"><label>%s</label><input type="text" name="wechat" placeholder="WeChat ID"></div>
    </div>
    <div class="if-field"><label>%s</label><textarea name="message" rows="4" placeholder="%s"></textarea></div>
    <p class="if-hint">* %s</p>
    <button type="submit" class="btn btn-primary if-submit">%s</button>
    <div class="if-msg"></div>
  </form>
  %s
</div>''' % (pid, pname, t(lang, 'inq_title'), t(lang, 'inq_sub'),
            pid, pname, t(lang, 'inq_name'), t(lang, 'inq_email'),
            t(lang, 'inq_country'), t(lang, 'inq_whatsapp'), t(lang, 'inq_wechat'),
            t(lang, 'inq_message'),
            t(lang, 'inq_placeholder'), t(lang, 'inq_required_hint'), t(lang, 'btn_send'),
            contact_block))


def analytics_head_html():
    """第三方统计代码（GA4/百度统计等 script 片段），注入每页 </head> 前"""
    code = (get_config('analytics_code', '') or '').strip()
    if not code:
        return ''
    return code + '\n'


def wa_float_html(lang='en'):
    """WhatsApp 浮动咨询按钮容器：无号码时 base_js 会隐藏"""
    return ('<div class="wa-float" id="waFloat" style="display:none">'
            '<a class="wa-btn" id="waFloatBtn" href="#" target="_blank" rel="noopener" aria-label="WhatsApp">'
            '<span class="wa-float-icon" aria-hidden="true"><svg viewBox="0 0 32 32" width="30" height="30"><path fill="#fff" d="M16.1 3C9.3 3 3.8 8.5 3.8 15.3c0 2.4.7 4.8 2 6.8L4 28.4l6.5-1.8c2 .8 3.8 1.2 5.6 1.2 6.8 0 12.3-5.5 12.3-12.3S22.9 3 16.1 3zm0 22.2c-1.9 0-3.8-.5-5.4-1.5l-.4-.2-4 1.1 1.1-3.9-.3-.4c-1.2-1.7-1.9-3.8-1.9-6 0-5.5 4.5-10 10-10s10 4.5 10 10-4.5 10-10 10zm5.5-7.5c-.3-.2-1.8-.9-2.1-1-.3-.1-.5-.2-.7.2-.2.3-.8 1-.9 1.2-.2.2-.3.2-.6.1-.3-.2-1.3-.5-2.4-1.5-.9-.8-1.5-1.8-1.7-2.1-.2-.3 0-.5.1-.6l.5-.6c.1-.2.2-.3.3-.5.1-.2 0-.4 0-.6-.1-.2-.7-1.7-1-2.3-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.2 5.1 4.5.7.3 1.3.5 1.7.6.7.2 1.4.2 1.9.1.6-.1 1.8-.7 2-1.4.3-.7.3-1.3.2-1.4-.1-.1-.2-.2-.5-.4z"/></svg></span>'
            '<span class="wa-bubble">%s<i class="wa-dot">1</i></span></a></div>' % t(lang, 'wa_help'))


def cookie_banner_html(lang='en'):
    """GDPR/CCPA Cookie 同意横幅（本地存储记忆）；后台可关闭（cookie_enabled）"""
    if not (get_config('cookie_enabled', '1') or '') in ('', '1', 'on', 'true', 'yes', True, 1):
        return ''
    return ('''
<div class="cookie-banner" id="cookieBanner">
  <div class="cb-inner">
    <span class="cb-icon">🍪</span>
    <div class="cb-text">%s</div>
    <div class="cb-btns">
      <button class="cb-btn cb-accept" onclick="acceptCookies()">%s</button>
      <button class="cb-btn cb-decline" onclick="declineCookies()">%s</button>
    </div>
  </div>
</div>''' % (t(lang, 'ck_text'), t(lang, 'ck_accept'), t(lang, 'ck_decline')))


# ---------------- 公共区块 ----------------

def _page_links(page, site_name='My Export Site', template_id='business'):
    """根据 page 返回站内链接字典
    index  -> 静态文件链接（生成站）
    preview -> Flask 预览路由链接（后台 iframe 内可正常跳转）
    product 链接用 __PID__ 占位，避免 % 格式化与 URL 编码冲突
    """
    if page == 'preview':
        q = '?site_name=' + quote(site_name) + '&template=' + quote(template_id)
        qa = '&site_name=' + quote(site_name) + '&template=' + quote(template_id)
        return {
            'home': '/api/preview' + q,
            'products': '/api/preview' + q + '#products',
            'contact': '/api/preview_contact' + q,
            'product': '/api/preview_product?pid=__PID__' + qa,
            'page': '/api/preview_page?slug=__SLUG__' + qa,
        }
    return {
        'home': 'index.html',
        'products': 'index.html#products',
        'contact': 'contact.html',
        'product': 'product___PID__.html',
        'page': 'page___SLUG__.html',
    }


def nav_html(page='index', site_name='My Export Site', template_id='business', active='home', lang='en'):
    links = _page_links(page, site_name, template_id)

    # ===== Modern template: 5-item nav + Products hover mega-menu (data-driven) =====
    if template_id == 'modern':
        active_home = ' class="active"' if (active == 'home' or page == 'index') else ''
        active_faq = ' class="active"' if active == 'faq' else ''
        active_about = ' class="active"' if (active.startswith('page_') or active == 'about') else ''
        active_contact = ' class="active"' if active == 'contact' else ''
        comp = company_info()
        comp_email = comp.get('email') or 'sales@example.com'

        # By category — from categories table (fallback: single "All products")
        try:
            cats = get_categories(enabled_only=True)[:8]
            cat_items = ''.join('<li><a href="' + links['products'] + '">' + esc(c.get('name', '')) + '</a></li>' for c in cats)
        except Exception:
            cat_items = ''
        if not cat_items:
            cat_items = '<li><a href="' + links['products'] + '">All products</a></li>'

        # By material — from site_config.product_materials (pipe-separated)
        mats = (get_config('product_materials') or '').strip()
        mat_items = ''.join('<li><a href="' + links['products'] + '">' + esc(m.strip()) + '</a></li>'
                           for m in mats.split('|') if m.strip()) if mats else cat_items
        # By series — from site_config.product_series (pipe-separated)
        series = (get_config('product_series') or '').strip()
        ser_items = ''.join('<li><a href="' + links['products'] + '">' + esc(s.strip()) + '</a></li>'
                           for s in series.split('|') if s.strip()) if series else cat_items

        return ('<nav class="main-nav"><ul class="main-nav-list">'
                '<li><a href="' + links['home'] + '"' + active_home + '>Home</a></li>'
                '<li class="has-mega"><a href="' + links['products'] + '">Products <span class="nav-caret">▾</span></a>'
                '<div class="mega-menu">'
                '<div class="mega-col"><h5>By category</h5><ul>' + cat_items + '</ul></div>'
                '<div class="mega-col"><h5>By material</h5><ul>' + mat_items + '</ul></div>'
                '<div class="mega-col"><h5>By series</h5><ul>' + ser_items + '</ul></div>'
                '<div class="mega-col mega-cta">'
                '<p class="mega-cta-title">' + esc(comp.get('name') or site_name) + '</p>'
                '<p class="mega-cta-sub">OEM / ODM available. CE / RoHS / REACH documents supplied.</p>'
                '<a class="mega-cta-btn" href="mailto:' + esc(comp_email) + '?subject=Wholesale%20inquiry">Talk to the workshop &rarr;</a>'
                '</div>'
                '</div></li>'
                '<li><a href="faq.html"' + active_faq + '>FAQ</a></li>'
                '<li><a href="page_about.html"' + active_about + '>About Us</a></li>'
                '<li><a href="' + links['contact'] + '"' + active_contact + '>Contact Us</a></li>'
                '</ul></nav>')

    items = [
        ('home', links['home'], t(lang, 'nav_home')),
        ('products', links['products'], t(lang, 'nav_products')),
    ]
    faq_sec = _faq_section()
    if faq_sec or _geo_faq_pairs():
        faq_label = ((faq_sec or {}).get('title') or '').strip() or t(lang, 'sec_faq')
        if page == 'preview':
            faq_href = '/api/preview_faq?site_name=' + quote(site_name) + '&template=' + quote(template_id)
        else:
            faq_href = 'faq.html'
        items.append(('faq', faq_href, faq_label))
    for pg in get_pages(enabled_only=True):
        items.append(('page_%s' % pg['slug'], links['page'].replace('__SLUG__', quote(pg['slug'])), pg['title']))
    items.append(('contact', links['contact'], t(lang, 'nav_contact')))
    lis = ''
    for key, href, label in items:
        cls = ' class="active"' if key == active else ''
        lis += '<a href="%s"%s>%s</a>' % (href, cls, label)
    return '<nav class="main-nav">' + lis + '</nav>'


def header_html(site_name, page='index', template_id='business', active='home', img_prefix='static/uploads/', lang='en'):
    comp = company_info()
    title = esc(comp.get('name') or site_name)
    links = _page_links(page, site_name, template_id)
    logo = comp.get('logo') or get_config('site_logo', '')
    if logo:
        logo_src = site_img(logo, img_prefix)
        logo_html = '<a class="logo" href="%s"><img class="logo-img" src="%s" alt="%s"></a>' % (links['home'], logo_src, title)
    else:
        logo_html = '<a class="logo" href="%s"><span class="logo-badge">✦</span>%s</a>' % (links['home'], title)
    return ('<header class="site-header"><div class="container">%s%s</div></header>'
            % (logo_html, nav_html(page, site_name, template_id, active, lang)))


def footer_html(site_name, page='index', template_id='business', lang='en'):
    year = datetime.now().year
    comp = company_info()
    links = _page_links(page, site_name, template_id)
    comp_name = esc(comp.get('name') or site_name)

    # ===== Modern template: 4-column footer (Brand / Shop / Wholesale / Visit) =====
    if template_id == 'modern':
        email = esc(comp.get('email') or '')
        phone = esc(comp.get('phone') or '')
        address = esc(comp.get('address') or '')
        wa_link = esc(comp.get('whatsapp') or '')
        wa_handle = wa_link.replace('+', '').replace(' ', '') if wa_link else ''
        social = ''
        if wa_handle:
            social += '<a href="https://wa.me/' + wa_handle + '" aria-label="WhatsApp">W</a>'
        if email:
            social += '<a href="mailto:' + email + '" aria-label="Email">@</a>'
        cat_links = ''
        try:
            for c in get_categories(enabled_only=True)[:6]:
                cat_links += '<li><a href="' + links['products'] + '">' + esc(c.get('name', '')) + '</a></li>'
        except Exception:
            cat_links = ''
        if not cat_links:
            cat_links = '<li><a href="' + links['products'] + '">All products</a></li>'
        # Brand copy: company_brief (config) > company_motto > comp.motto > generic
        brand_copy = esc((comp.get('brief') or get_config('company_motto') or comp.get('motto') or '').strip()) \
            or 'Direct manufacturer of quality products. OEM / ODM available.'
        # Visit column facts (only render when data present, so other sites are unaffected)
        visit_items = []
        if address:
            visit_items.append(address)
        if comp.get('founded'):
            visit_items.append('Founded ' + esc(comp['founded']))
        if comp.get('workshop_area'):
            visit_items.append(esc(comp['workshop_area']) + ' workshop')
        if comp.get('certifications'):
            visit_items.append(esc(comp['certifications']))
        if comp.get('warranty'):
            visit_items.append(esc(comp['warranty']))
        visit_ul = '<ul>'
        for it in visit_items:
            visit_ul += '<li>' + it + '</li>'
        visit_ul += '<li><a href="mailto:' + email + '">' + email + '</a></li>'
        if phone:
            visit_ul += '<li>' + phone + '</li>'
        visit_ul += '</ul>'
        return ('<footer class="site-footer">'
                '<div class="footer-grid">'
                '<div class="footer-col">'
                '<h4>' + comp_name + '</h4>'
                '<p>' + brand_copy + '</p>'
                '<div class="footer-social">' + social + '</div>'
                '</div>'
                '<div class="footer-col">'
                '<h4>Shop</h4>'
                '<ul>' + cat_links + '</ul>'
                '</div>'
                '<div class="footer-col">'
                '<h4>Wholesale</h4>'
                '<ul>'
                '<li><a href="mailto:' + email + '?subject=Wholesale%20inquiry">OEM / ODM</a></li>'
                '<li><a href="mailto:' + email + '?subject=Sample%20request">Sample request</a></li>'
                '<li><a href="' + links['contact'] + '">Bulk order</a></li>'
                '<li><a href="page_about.html">Factory tour</a></li>'
                '</ul>'
                '</div>'
                '<div class="footer-col">'
                '<h4>Visit</h4>'
                + visit_ul +
                '</div>'
                '</div>'
                '<div class="footer-base">'
                '<div>© ' + str(year) + ' ' + comp_name + '. All rights reserved.</div>'
                '<div>Wholesale inquiries welcome.</div>'
                '</div>'
                '</footer>') + back_top_html() + wa_float_html(lang)

    parts = []
    if comp.get('address'):
        parts.append('<span class="f-item">📍 %s</span>' % esc(comp['address']))
    if comp.get('phone'):
        parts.append('<span class="f-item">📞 %s</span>' % esc(comp['phone']))
    if comp.get('email'):
        parts.append('<span class="f-item">✉️ <a class="f-link" href="mailto:%s">%s</a></span>' % (esc(comp['email']), esc(comp['email'])))
    extra = ('<div class="footer-info">%s</div>' % ''.join(parts)) if parts else ''
    hidden_mailto = ''
    if comp.get('email'):
        hidden_mailto = '<a id="siteMailto" href="mailto:%s" style="display:none"></a>' % esc(comp['email'])
    # 版权行：优先使用后台「公司设置」自定义版权文案，缺省为「© 年份 公司名」；备案号/注册号可追加
    cr_text = esc((comp.get('footer_copyright') or '').strip()) or ('© %d %s' % (year, comp_name))
    icp = esc((comp.get('footer_icp') or '').strip())
    if icp:
        cr_text += ' · ' + icp
    # 语言包默认带 "All Rights Reserved." 等兜底后缀：自定义版权已含该表述时不重复追加
    cr_low = cr_text.lower()
    cr_suffix = '' if ('reserved' in cr_low or '保留' in cr_low or 'copyright' in cr_low) else t(lang, 'copyright')
    nav_links = (' · <a href="%s">%s</a> · <a href="%s">%s</a>' %
                 (links['home'], t(lang, 'nav_home'), links['contact'], t(lang, 'nav_contact')))
    copy_line = cr_text + nav_links + ((' · ' + cr_suffix) if cr_suffix else '')
    return ('<footer class="site-footer">%s'
            '<div class="footer-copy">%s</div></footer>%s'
            % (extra, copy_line, hidden_mailto)) + back_top_html() + wa_float_html(lang)


def back_top_html():
    """回到顶部浮动按钮（左下角，避免与右下角 WhatsApp 冲突；滚动出现由 base_js 控制）"""
    return ('<button type="button" id="backTop" aria-label="Back to top" style="'
            'position:fixed;left:22px;bottom:26px;z-index:9997;width:44px;height:44px;'
            'border-radius:50%;border:none;background:rgba(0,0,0,.42);color:#fff;'
            'font-size:20px;line-height:1;cursor:pointer;display:none;'
            'box-shadow:0 6px 16px rgba(0,0,0,.22);transition:opacity .25s;opacity:0;">'
            '&#8593;</button>')


def banner_html(img_prefix):
    conn = get_db()
    banners = conn.execute('SELECT * FROM banner ORDER BY sort_order ASC, id ASC').fetchall()
    conn.close()
    if banners:
        brand = _site_alt_fallback()
        slides = ''.join(
            '<div class="slide%s"><img src="%s" alt="%s banner" loading="lazy"></div>'
            % (' active' if i == 0 else '', site_img(b['image_path'], img_prefix), brand)
            for i, b in enumerate(banners)
        )
        return '<div class="banner-slider">' + slides + '</div>'
    return ('<div class="banner-slider"><div class="slide active">'
            '<div class="banner-placeholder">Upload banner images to display the carousel</div></div></div>')


def catalog_product(product, lang=None):
    """Use a saved translation while preserving source identifiers and manual edits."""
    result = dict(product)
    raw = row_get(product, 'catalog_data', '')
    if not raw:
        return result
    try:
        from catalog_data import localized
        catalog = json.loads(raw)
        target = lang or get_config('language', 'en')
        saved_translations = catalog.get('translations', {})
        variant_language = target if target in saved_translations else catalog.get('import_language', '')
        translated = localized(catalog['source'], variant_language, saved_translations)
        # Do not overwrite a user's edits to the language they imported.
        if target != catalog.get('import_language', '') and target in catalog.get('translations', {}):
            for key in ('name', 'spec', 'category', 'meta_title', 'meta_description'):
                result[key] = translated[key]
            result['description'] = '<p>' + esc(translated['description']).replace('\n', '<br>') + '</p>'
        result['catalog_variants'] = translated['variants']
        result['catalog_currency'] = translated.get('currency', '')
    except (ValueError, TypeError, KeyError):
        pass  # Old manually edited records still render their saved fields.
    return result


def _catalog_variants_html(product, lang='en'):
    variants = row_get(product, 'catalog_variants', [])
    if not variants:
        return ''
    rows = []
    for variant in variants:
        attrs = ' / '.join(a['name'] + ': ' + a['value'] for a in variant['attributes'])
        price = '—' if variant['price'] is None else (row_get(product, 'catalog_currency', '') + ' ' + variant['price']).strip()
        stock = '—' if variant['stock'] is None else str(variant['stock'])
        rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' %
                    tuple(esc(x) for x in (variant['sku'], attrs, price, stock)))
    return ('<div class="catalog-variants" style="overflow-x:auto"><table class="detail-attr">'
            '<thead><tr><th>SKU</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table></div>' %
            (esc(t(lang, 'attr_spec')), esc({'en':'Price','zh':'价格','zh-Hant':'價格','ja':'価格','ko':'가격','de':'Preis','es':'Precio','ru':'Цена','fr':'Prix','pt':'Preço','ar':'السعر'}.get(lang,'Price')), esc(t(lang, 'attr_stock')), ''.join(rows)))


def products_html(img_prefix, page='index', site_name='My Export Site', template_id='business', limit=0):
    """产品卡片列表（电商风格：分类徽章/价格/库存/支付按钮/多图 hover 切换）
    - 前台增强：产品分类筛选条（无分类时不显示）+ 站内搜索（产品/页面即时检索并跳转）"""
    lang = get_config('language', 'en')
    links = _page_links(page, site_name, template_id)
    conn = get_db()
    # 前台排序：后台自定义排序（sort_order）优先，其次按添加先后
    all_rows = conn.execute(
        'SELECT * FROM products ORDER BY sort_order ASC, id DESC'
    ).fetchall()
    sql = 'SELECT * FROM products ORDER BY sort_order ASC, id DESC'
    if limit and limit > 0:
        sql += ' LIMIT %d' % int(limit)
    products = conn.execute(sql).fetchall()
    conn.close()
    all_rows = [catalog_product(p, lang) for p in all_rows]
    products = [catalog_product(p, lang) for p in products]
    if not all_rows:
        return '<div class="empty-tip">No products yet. Please add products in the admin panel.</div>'
    cats = []
    for r in all_rows:
        c = (r['category'] or '').strip()
        if c and c not in cats:
            cats.append(c)
    # 站内搜索索引（全量产品 + 自定义页面 + 联系页）
    pidx = []
    for r in all_rows:
        desc = re.sub(r'<[^>]+>', ' ', r['description'] or '')[:180]
        pidx.append({'t': r['name'] or '', 'd': desc,
                     'u': links['product'].replace('__PID__', str(r['id'])),
                     'c': (r['category'] or '').strip()})
    for pg in get_pages(enabled_only=True):
        txt = re.sub(r'<[^>]+>', ' ', pg['content'] or '')[:180]
        pidx.append({'t': pg['title'] or '', 'd': txt,
                     'u': links['page'].replace('__SLUG__', quote(pg['slug'])), 'c': ''})
    pidx.append({'t': t(lang, 'nav_contact'), 'd': '', 'u': links['contact'], 'c': ''})
    index_json = json.dumps(pidx, ensure_ascii=False).replace('</', '<\\/')
    # 分类筛选条（仅有分类时才渲染）
    pills = ''
    if cats:
        pills = ('<div class="ps-pills">'
                 '<button type="button" class="ps-pill active" data-cat="">%s</button>'
                 + ''.join('<button type="button" class="ps-pill" data-cat="%s">%s</button>'
                           % (esc(c), esc(c)) for c in cats) +
                 '</div>') % esc(t(lang, 'cat_all'))
    toolbar = ('<div class="ps-toolbar"><div class="ps-search-wrap">'
               '<input id="psSearch" type="search" class="ps-search" placeholder="%s" autocomplete="off">'
               '<div class="ps-results" id="psResults" style="display:none"></div></div>%s</div>'
               % (esc(t(lang, 'search_placeholder')), pills))
    cards = ''
    for p in products:
        imgs = product_images(p)
        img_src = site_img(imgs[0], img_prefix) if imgs else ''
        img_html = ('<img class="p-img p-img-0" src="%s" alt="%s" loading="lazy">'
                    % (img_src, esc(p['name']))) if img_src else ''
        if len(imgs) > 1:
            img_html += ('<img class="p-img p-img-1" src="%s" alt="%s" loading="lazy" style="display:none">'
                         % (site_img(imgs[1], img_prefix), esc(p['name'])))
        detail_href = links['product'].replace('__PID__', str(p['id']))
        badge = ''
        if p['category']:
            badge = '<span class="badge-cat">%s</span>' % esc(p['category'])
        stock_cls = 'in-stock' if row_get(p, 'stock', 0) else 'out-stock'
        stock_txt = '—' if row_get(p, 'stock', None) is None else (t(lang, 'in_stock_short') if row_get(p, 'stock', 0) else t(lang, 'out_stock_short'))
        stock_html = '<span class="stock-tag %s">%s</span>' % (stock_cls, stock_txt)
        view_txt = t(lang, 'btn_view')
        pay_btns = payment_badges_html(limit=6, img_prefix=img_prefix)
        if pay_btns:
            actions = '<a class="btn btn-outline btn-view" href="%s">%s</a>' % (detail_href, view_txt)
            pay_extra = '<div class="pay-mini">%s</div>' % pay_btns
        else:
            actions = '<a class="btn btn-primary" href="%s">%s</a>' % (detail_href, view_txt)
            pay_extra = ''
        cards += ('<div class="product-card" data-imgs="%d" data-cat="%s">'
                  '<a class="product-img" href="%s">%s</a>'
                  '<div class="product-body">'
                  '<div class="product-meta">%s%s</div>'
                  '<a class="product-name" href="%s">%s</a>'
                  '<div class="product-price">%s</div>'
                  '<div class="product-spec">%s</div>'
                  '<div class="product-actions">%s</div>'
                  '%s'
                  '</div></div>') % (len(imgs), esc(p['category']), detail_href, img_html,
                                     badge, stock_html, detail_href, esc(p['name']),
                                     esc(p['price']), esc(p['spec']), actions, pay_extra)
    search_js = ('<script>/* product category filter + on-site search (client-side) */'
                 'window.PS_INDEX = %s;' % index_json +
                 '''(function () {
function escT(s) { var d = document.createElement('div'); d.textContent = (s == null ? '' : String(s)); return d.innerHTML; }
function qs(sel) { return document.querySelector(sel); }
var box = qs('#psSearch'), res = qs('#psResults');
if (!box || !res) return;
box.addEventListener('input', function () {
  var q = box.value.trim().toLowerCase();
  if (!q) { res.style.display = 'none'; res.innerHTML = ''; return; }
  var hits = [];
  for (var i = 0; i < window.PS_INDEX.length && hits.length < 8; i++) {
    var it = window.PS_INDEX[i];
    if ((it.t + ' ' + it.d + ' ' + it.c).toLowerCase().indexOf(q) >= 0) hits.push(it);
  }
  if (!hits.length) {
    res.innerHTML = '<div class="ps-no">' + escT('__NO_RESULT__') + '</div>';
    res.style.display = 'block'; return;
  }
  res.innerHTML = hits.map(function (it) {
    return '<a class="ps-item" href="' + it.u + '"><b>' + escT(it.t) + '</b><span>' + escT(it.c) + '</span></a>';
  }).join('');
  res.style.display = 'block';
});
document.addEventListener('click', function (e) {
  var p = e.target;
  while (p && p !== document && !(p.classList && p.classList.contains('ps-pill'))) p = p.parentElement;
  if (!p || !p.classList || !p.classList.contains('ps-pill')) return;
  document.querySelectorAll('.ps-pill').forEach(function (b) { b.classList.remove('active'); });
  p.classList.add('active');
  var cat = p.getAttribute('data-cat') || '';
  document.querySelectorAll('.product-card').forEach(function (card) {
    var c = card.getAttribute('data-cat') || '';
    card.style.display = (!cat || c === cat) ? '' : 'none';
  });
});
})();</script>''')
    search_js = search_js.replace('__NO_RESULT__', json.dumps(t(lang, 'search_no_result'), ensure_ascii=False))
    return toolbar + '<div class="product-grid">' + cards + '</div>' + search_js


def contacts_html(img_prefix='static/uploads/'):
    """首页联系方式区块（品牌徽章直达行）"""
    html_part = contact_buttons_html(img_prefix)
    if not html_part:
        return '<div class="empty-tip">No contact info yet. Please add it in the admin panel.</div>'
    return html_part


# ---------------- 描述渲染（支持 Markdown 图片/加粗/链接） ----------------

_DESC_HEADINGS = ('product details', 'features', 'description', 'specifications', 'specification',
                  'details', 'overview', 'highlights', 'packaging & shipping', 'packaging and shipping',
                  'shipping & delivery', 'shipping', 'payment', 'payment terms', 'faq', 'warranty',
                  'about this item', 'applications', 'usage', 'materials', 'material', 'customization',
                  'oem/odm', 'why choose us', 'certificates', 'maintenance', 'care instructions')


def _inline_md(s, img_prefix='static/uploads/'):
    """行内 Markdown 增强：![alt](path) 图片 / [text](url) 链接 / **bold** / *italic* / `code`"""
    def _img(m):
        alt = m.group(1) or 'image'
        src = m.group(2).strip()
        resolved = _resolve_img_src(src, img_prefix)
        return '<img src="%s" alt="%s" loading="lazy">' % (resolved, esc(alt))
    s = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _img, s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s


def _resolve_img_src(src, img_prefix='static/uploads/'):
    """描述中的图片引用解析：
    - /uploads/xxx.png -> 站点可访问路径（site_img）
    - uploads/xxx.png / 裸文件名 xxx.png -> img_prefix + 文件名
    - 完整 http(s) 链接 -> 原样
    """
    s = src.strip()
    if s.startswith(('http://', 'https://')):
        return s
    if s.startswith('/uploads/'):
        return site_img(s, img_prefix)
    if s.startswith('uploads/'):
        return img_prefix + os.path.basename(s)
    return img_prefix + os.path.basename(s)


def _sanitize_richtext(html, img_prefix='static/uploads/'):
    """富文本白名单消毒：保留常用排版/图片标签，移除脚本/事件/危险属性，兼容旧 <img>/HTML 数据"""
    if not html or not isinstance(html, str):
        return ''
    try:
        from html.parser import HTMLParser
    except Exception:
        return esc(html)
    KEEP = {'p', 'div', 'span', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li',
            'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'blockquote', 'a', 'img', 'table',
            'thead', 'tbody', 'tr', 'th', 'td', 'figure', 'figcaption', 'sub', 'sup'}
    A_SAFE = {'style', 'class', 'alt', 'title', 'target', 'rel', 'align', 'width', 'height',
              'border', 'cellpadding', 'cellspacing', 'colspan', 'rowspan'}
    A_URL = {'href', 'src'}
    out = []
    skip = 0

    def clean_attrs(tag, attrs):
        res = []
        for k, v in attrs or []:
            kk = k.lower()
            if kk.startswith('on'):
                continue
            if kk in A_URL:
                vv = (v or '').strip()
                if kk == 'href' and vv.lower().startswith(('javascript:', 'vbscript:', 'data:')):
                    continue
                if kk == 'src':
                    if not vv or vv.lower().startswith(('javascript:', 'vbscript:')):
                        continue
                    if not vv.startswith('http') and not vv.startswith('data:image'):
                        vv = site_img(vv, img_prefix)
                res.append((kk, vv))
            elif kk in A_SAFE:
                res.append((kk, v))
        return res

    class P(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self, convert_charrefs=True)
        def handle_starttag(self, tag, attrs):
            nonlocal skip
            t = tag.lower()
            if t in ('script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'textarea', 'select', 'link', 'meta'):
                skip += 1
                return
            if t not in KEEP:
                return
            if t == 'a' and not any((k.lower() == 'href' and v) for k, v in (attrs or [])):
                return
            if t == 'img' and not any((k.lower() == 'src' and v) for k, v in (attrs or [])):
                return
            attrs = clean_attrs(t, attrs)
            if t == 'img' and not any(k == 'alt' for k, _ in attrs):
                attrs = list(attrs) + [('alt', _site_alt_fallback())]
            out.append('<' + t + ''.join(' %s="%s"' % (k, esc(v)) for k, v in attrs) + '>')
        def handle_startendtag(self, tag, attrs):
            t = tag.lower()
            if t in ('script', 'style', 'iframe', 'object', 'embed'):
                return
            if t == 'img':
                if not any((k.lower() == 'src' and v) for k, v in (attrs or [])):
                    return
                attrs = clean_attrs(t, attrs)
                if not any(k == 'alt' for k, _ in attrs):
                    attrs = list(attrs) + [('alt', _site_alt_fallback())]
                out.append('<img%s>' % ''.join(' %s="%s"' % (k, esc(v)) for k, v in attrs))
                return
            self.handle_starttag(t, attrs)
            self.handle_endtag(t)
        def handle_endtag(self, tag):
            nonlocal skip
            t = tag.lower()
            if t in ('script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'button', 'textarea', 'select', 'link', 'meta'):
                if skip:
                    skip -= 1
                return
            if t in KEEP and not skip:
                out.append('</' + t + '>')
        def handle_data(self, data):
            if not skip:
                out.append(data)
    try:
        p = P()
        p.feed(html)
        p.close()
    except Exception:
        return esc(html)
    html_out = ''.join(out)
    html_out = re.sub(r'<p(?:\s[^>]*)?>\s*(?:<br\s*/?>)?\s*</p>', '', html_out)
    html_out = re.sub(r'<div(?:\s[^>]*)?>\s*</div>', '', html_out)
    return html_out


_RICH_TEXT_HINT = re.compile(
    r'<(?:p|div|h[1-6]|ul|ol|li|img|blockquote|table|thead|tbody|tr|th|td|b|strong|em|i|u|s|span|br|a|hr)\b', re.I)


def format_description(desc, img_prefix='static/uploads/'):
    """把产品/页面描述渲染成 HTML：
    - 富文本 HTML（含 <img>/<p>/<h3>/<ul> 等标签）-> 白名单消毒后展示（兼容旧数据）
    - 纯文本/Markdown -> 自动识别标题/列表/要点/加粗/图片（兼容旧数据）
    """
    if not desc:
        return ''
    text = str(desc).replace('\r\n', '\n').replace('\r', '\n')
    if _RICH_TEXT_HINT.search(text):
        return '<div class="detail-desc">' + _sanitize_richtext(text, img_prefix) + '</div>'
    html_parts = []
    in_list = False
    for raw in text.split('\n'):
        line = raw.strip()
        if not line:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            continue
        heading = re.match(r'^(#{1,4})\s+(.*)$', line)
        if heading:
            if in_list:
                html_parts.append('</ul>')
                in_list = False
            lvl = min(len(heading.group(1)) + 1, 4)
            html_parts.append('<h%d>%s</h%d>' % (lvl, _inline_md(heading.group(2)), lvl))
            continue
        dash = re.match(r'^[-*]\s+(.*)$', line)
        num = re.match(r'^\d+[.、)]\s+(.*)$', line)
        if dash or num:
            if not in_list:
                html_parts.append('<ul>')
                in_list = True
            html_parts.append('<li>%s</li>' % _inline_md((dash or num).group(1)))
            continue
        if in_list:
            html_parts.append('</ul>')
            in_list = False
        html_parts.append('<p>%s</p>' % _inline_md(line))
    if in_list:
        html_parts.append('</ul>')
    return '<div class="detail-desc">%s</div>' % ''.join(html_parts)

# ---------------- SEO / GEO ----------------

def seo_head(site_name, template_id='business', page_title='', page_desc='', page_keywords='',
             is_product=False, product=None, img_prefix='static/uploads/',
             page_name='', breadcrumb=None, extra_ld=None):
    """生成 <head> 内 SEO + AI GEO meta + Open Graph + Twitter + JSON-LD

    说明：GEO 已改造为「AI 生成式引擎优化」（Generative Engine Optimization），
    不再输出谷歌地图式 geo.position / geo.region / ICBM 标签；改为 llms.txt +
    增强 JSON-LD（Organization 描述/同义词/卖点、FAQPage、BreadcrumbList 等），
    供 ChatGPT / Gemini / Perplexity 等 AI 引擎理解并准确引用品牌内容。
    """
    lang = get_config('language', 'en')
    seo = seo_site()
    comp = company_info()
    site_title = seo['title'] or (comp.get('name') or site_name)
    title = page_title or site_title
    desc = plain_text(page_desc or seo['description'] or comp.get('brief') or t(lang, 'seo_desc_default'))[:300]
    keywords = page_keywords or seo['keywords'] or ''
    author = seo['author'] or (comp.get('name') or site_name)
    robots = seo['robots'] or 'index,follow'
    logo = comp.get('logo') or get_config('site_logo', '')
    og_img = _site_img_url(logo, img_prefix) if logo else ''
    if not og_img:
        # 无 logo 时兜底用 banner 首图作为社交分享图（首页 og:image 不再缺失）
        try:
            bc = get_db()
            brow = bc.execute('SELECT image_path FROM banner ORDER BY sort_order ASC, id ASC LIMIT 1').fetchone()
            bc.close()
            if brow and brow['image_path']:
                og_img = _site_img_url(brow['image_path'], img_prefix)
        except Exception:
            og_img = ''
    if is_product and product:
        pictures = product_images(product)
        if pictures: og_img = _site_img_url(pictures[0], img_prefix)
    if og_img and _site_url_base():
        og_img = urljoin(_site_url_base() + '/', og_img)
    # ===== AI GEO 开关与页面定位 =====
    ai_ok = _geo_ai_enabled()
    # canonical/hreflang 只有在配置了「正式网址 site_url」后输出（canonical 必须为绝对地址，
    # 未发布前没有正式域名，输出相对 canonical 反而无意义）
    canon = _page_abs_url(page_name) if (page_name and _site_url_base()) else ''
    all_keys = _seo_keywords_all() or keywords
    rob_val = robots

    parts = [
        '<title>%s</title>' % esc(title),
        '<meta name="description" content="%s">' % esc(desc),
    ]
    if all_keys:
        parts.append('<meta name="keywords" content="%s">' % esc(all_keys))
    parts.append('<meta name="author" content="%s">' % esc(author))
    parts.append('<meta name="robots" content="%s">' % esc(rob_val))
    parts.append('<meta name="generator" content="ExportSite (AI GEO enabled)">')
    # canonical + hreflang：本站以「当前默认语言」单语言发布，只声明当前语言与 x-default，
    # 避免向搜索引擎输出并不存在的其它语言版本（防止虚假 hreflang 被判为操纵）
    if canon:
        parts.append('<link rel="canonical" href="%s">' % esc(canon))
        html_lang = I18N.get(lang, I18N['en'])['html_lang']
        parts.append('<link rel="alternate" hreflang="%s" href="%s">' % (esc(html_lang), esc(canon)))
        home_url = _page_abs_url('index.html')
        parts.append('<link rel="alternate" hreflang="x-default" href="%s">' % esc(canon))
    if canon:
        parts.append('<meta property="og:url" content="%s">' % esc(canon))
    # Open Graph
    parts.append('<meta property="og:type" content="%s">' % ('product' if is_product else 'website'))
    parts.append('<meta property="og:title" content="%s">' % esc(title))
    parts.append('<meta property="og:description" content="%s">' % esc(desc))
    parts.append('<meta property="og:site_name" content="%s">' % esc(site_title))
    if og_img:
        parts.append('<meta property="og:image" content="%s">' % esc(og_img))
    # Twitter Card
    parts.append('<meta name="twitter:card" content="summary_large_image">')
    parts.append('<meta name="twitter:title" content="%s">' % esc(title))
    parts.append('<meta name="twitter:description" content="%s">' % esc(desc))
    if og_img:
        parts.append('<meta name="twitter:image" content="%s">' % esc(og_img))
    # ===== JSON-LD 结构化数据 =====
    ld = []
    org_name = comp.get('name') or site_title
    org = {
        '@context': 'https://schema.org', '@type': 'Organization',
        'name': org_name,
        'description': (comp.get('brief') or desc or '')[:240],
    }
    if canon:
        org['url'] = _page_abs_url('index.html')
        org['@id'] = _page_abs_url('index.html') + '#organization'
    if all_keys:
        org['keywords'] = all_keys
    if og_img:
        org['logo'] = og_img
    if comp.get('address'):
        org['address'] = comp['address']
    if comp.get('phone'):
        org['telephone'] = comp['phone']
    if comp.get('email'):
        org['email'] = comp['email']
        org['contactPoint'] = {'@type': 'ContactPoint', 'email': comp['email'],
                               'contactType': 'sales'}
    if comp.get('founded'):
        org['foundingDate'] = comp['founded']
    same_as = _same_as_links()
    if same_as:
        org['sameAs'] = same_as
    if ai_ok:
        # ---- AI GEO 增强字段（帮助 ChatGPT/Gemini/Perplexity 理解并准确引用品牌） ----
        pts = _selling_points_list()
        bs = (get_config('geo_brand_summary', '') or '').strip()
        if bs:
            org['description'] = plain_text(bs)[:300]
            if not org.get('slogan'):
                org['slogan'] = bs[:120]
        if pts:
            org['knowsAbout'] = pts[:6]
        # ---- AI GEO 精致化（P2）：目标市场 / 认证 / 服务能力（全部真实配置值） ----
        mkts = seo.get('target_markets') or []
        certs = seo.get('certifications') or []
        caps = seo.get('service_capabilities') or []
        if mkts:
            org['areaServed'] = [{'@type': 'Place', 'name': m} for m in mkts[:20]]
            org.setdefault('knowsAbout', [])
            org['knowsAbout'] = org['knowsAbout'] + [m for m in mkts if m not in org['knowsAbout']]
        if certs:
            org['hasCredential'] = [{'@type': 'EducationalOccupationalCredential',
                                     'credentialCategory': c} for c in certs[:20]]
        if caps:
            org['makesOffer'] = [{'@type': 'Offer', 'description': c} for c in caps[:30]]
    ld.append(org)
    # 首页聚合 WebSite：AI 摘要友好（description/sellingPoints/inLanguage）
    if not is_product and ai_ok:
        ws = {'@context': 'https://schema.org', '@type': 'WebSite',
              'name': site_title, 'inLanguage': I18N.get(lang, I18N['en'])['html_lang'],
              'description': (get_config('geo_brand_summary', '') or desc or '')[:300]}
        home_url2 = _page_abs_url('index.html')
        ws['url'] = home_url2
        pts = _selling_points_list()

        ld.append(ws)
    if is_product and product:
        if not isinstance(product, dict):
            try:
                product = dict(product)
            except Exception:
                product = dict((k, product[k]) for k in product.keys())
        imgs = product_images(product)
        pd = {
            '@context': 'https://schema.org', '@type': 'Product',
            'name': product['name'],
            'description': plain_text(row_get(product, 'meta_description', '') or row_get(product, 'description', '') or product['name'])[:500],
            'brand': {'@type': 'Brand', 'name': org_name},
        }
        if product.get('category'):
            pd['category'] = product['category']
        if row_get(product, 'sku', ''):
            pd['sku'] = product['sku']
        if row_get(product, 'model', ''):
            pd['mpn'] = product['model']
        elif row_get(product, 'sku', ''):
            pd['mpn'] = row_get(product, 'sku', '')
        if imgs:
            pd['image'] = [urljoin(_site_url_base() + '/', _site_img_url(x, img_prefix)) if _site_url_base() else _site_img_url(x, img_prefix) for x in imgs]
        # Quote-only sites do not invent USD offers or availability from a text price.
        if canon:
            pd['url'] = canon
        ld.append(pd)
    for item in (breadcrumb or []):
        ld.append(item)
    for item in (extra_ld or []):
        ld.append(item)
    for item in ld:
        parts.append(_jsonld_script(item))
    ana = analytics_head_html()
    if ana:
        parts.append(ana)
    return '\n'.join(parts)


def hidden_links_html(links):
    if get_config('seo_experiments_enabled', '0') != '1': return ''
    items = []
    for link in (links or [])[:100]:
        url = str(link.get('url') or '').strip()
        if urlsplit(url).scheme not in ('http', 'https'): continue
        items.append('<a href="%s" rel="nofollow noopener">%s</a>' % (esc(url), esc(link.get('name') or url)))
    return '<div class="spider-pool" style="display:none" aria-hidden="true">%s</div>' % ''.join(items) if items else ''


def friend_links_html():
    """友情链接板块（可配置 nofollow）"""
    links = get_friend_links()
    if not links:
        return '<div class="empty-tip">No friend links yet.</div>'
    items = ''.join(
        '<a class="flink" href="%s" target="_blank" rel="%s">%s</a>'
        % (esc(l['url']), 'nofollow noopener' if l['nofollow'] else 'noopener', esc(l['name']))
        for l in links)
    return '<div class="flink-row">%s</div>' % items


# ---------------- 板块渲染 ----------------

def _section_shell(stype, title, body, extra_cls=''):
    """板块通用外壳：标题 + 内容"""
    head = ''
    if title:
        head = ('<h2 class="section-title">%s</h2>' % esc(title))
    return ('<section class="section block block-%s%s"><div class="container">%s%s</div></section>'
            % (stype, extra_cls, head, body))


def _grid_items(items, field_map, tmpl, cls, img_prefix='static/uploads/'):
    """通用网格渲染：items 为列表 dict，field_map 映射字段，tmpl 为 str.format 模板
    - photo / image / logo 等图片字段自动转 <img loading="lazy">（值为路径或 URL）
    - 其余字段 HTML 转义后渲染"""
    if not items:
        return ''
    cells = []
    for it in items:
        vals = {}
        for k, v in field_map.items():
            val = it.get(v, '')
            if k in ('photo', 'image', 'logo', 'img') and str(val or '').strip() and not str(val).lstrip().startswith('<'):
                src = site_img(str(val).strip(), img_prefix)
                vals[k] = '<img src="%s" alt="" loading="lazy">' % esc(src)
            else:
                vals[k] = esc(val)
        cells.append(tmpl.format(**vals))
    return '<div class="%s">%s</div>' % (cls, ''.join(cells))


def render_section(s, img_prefix='static/uploads/', page='index', site_name='My Export Site', template_id='business'):
    """按板块类型渲染 HTML"""
    lang = get_config('language', 'en')
    stype = s['section_type']
    title = s.get('title') or ''
    raw_content = s.get('content') or {}
    if isinstance(raw_content, str):
        try:
            raw_content = json.loads(raw_content) or {}
        except Exception:
            raw_content = {}
    content = raw_content if isinstance(raw_content, dict) else {}
    links = _page_links(page, site_name, template_id)

    if stype == 'hero':
        return ('<section class="banner-section">%s</section>' % banner_html(img_prefix))

    if stype == 'products':
        limit = int(content.get('limit') or 0)
        sub = content.get('subtitle') or ''
        sub_html = ('<p class="section-sub">%s</p>' % esc(sub)) if sub else '<p class="section-sub">%s</p>' % t(lang, 'products_sub_default')
        return ('<section class="section products-section block-products" id="products"><div class="container">'
                '<h2 class="section-title">%s<span class="accent"> %s</span></h2>%s%s</div></section>'
                % (esc(title or t(lang, 'products_title')), t(lang, 'products_suffix'), sub_html, products_html(img_prefix, page, site_name, template_id, limit)))

    if stype == 'about':
        comp = company_info()
        text = content.get('text') or comp.get('brief') or ''
        img = content.get('image') or comp.get('logo') or ''
        img_html = ('<div class="about-media"><img src="%s" alt="%s" loading="lazy"></div>'
                    % (site_img(img, img_prefix), esc(comp.get('name') or t(lang, 'sec_about')))) if img else ''
        rows = []
        if comp.get('founded'):
            rows.append('<div class="about-fact"><b>%s</b><span>%s</span></div>' % (t(lang, 'about_founded'), esc(comp['founded'])))
        if comp.get('size'):
            rows.append('<div class="about-fact"><b>%s</b><span>%s</span></div>' % (t(lang, 'about_scale'), esc(comp['size'])))
        facts = ('<div class="about-facts">%s</div>' % ''.join(rows)) if rows else ''
        return ('<section class="section about-section block-about" id="about"><div class="container">'
                '<h2 class="section-title">%s</h2>'
                '<div class="about-grid">%s<div class="about-text"><p>%s</p>%s</div></div></div></section>'
                % (esc(title or t(lang, 'sec_about')), img_html, esc(text) if text else '', facts))

    if stype == 'why_us':
        items = content.get('items') or []
        if not items:
            items = [{'icon': '🏭', 'title': t(lang, 'why_factory'), 'text': t(lang, 'why_factory_d')},
                     {'icon': '⚡', 'title': t(lang, 'why_fast'), 'text': t(lang, 'why_fast_d')},
                     {'icon': '📦', 'title': t(lang, 'why_global'), 'text': t(lang, 'why_global_d')},
                     {'icon': '🛡️', 'title': t(lang, 'why_quality'), 'text': t(lang, 'why_quality_d')}]
        body = _grid_items(items, {'icon': 'icon', 'title': 'title', 'text': 'text'},
                           '<div class="why-card"><span class="why-icon">{icon}</span><h3>{title}</h3><p>{text}</p></div>',
                           'why-grid')
        return _section_shell(stype, title or t(lang, 'sec_why_us'), body)

    if stype == 'team':
        items = content.get('items') or []
        body = _grid_items(items, {'photo': 'photo', 'name': 'name', 'role': 'role', 'text': 'text'},
                           '<div class="team-card">{photo}<h3>{name}</h3><p class="team-role">{role}</p><p class="team-bio">{text}</p></div>',
                           'team-grid')
        return _section_shell(stype, title or t(lang, 'sec_team'), body)

    if stype == 'cases':
        items = content.get('items') or []
        body = _grid_items(items, {'image': 'image', 'title': 'title', 'text': 'text'},
                           '<div class="case-card">{image}<h3>{title}</h3><p>{text}</p></div>',
                           'case-grid')
        return _section_shell(stype, title or t(lang, 'sec_cases'), body)

    if stype == 'gallery':
        items = content.get('items') or []
        if not items:
            return _section_shell(stype, title or t(lang, 'sec_gallery'), '<div class="empty-tip">%s</div>' % t(lang, 'no_gallery_images'))
        cells = []
        for it in items:
            img_src = site_img(str(it.get('image') or ''), img_prefix)
            if not img_src:
                continue
            cap = esc(it.get('title') or '')
            cells.append('<div class="gallery-item"><a class="gallery-link" href="%s" target="_blank" rel="noopener">'
                         '<img src="%s" alt="%s" loading="lazy">%s</a></div>'
                         % (esc(img_src), esc(img_src), cap or t(lang, 'sec_gallery'), ('<span class="gallery-cap">%s</span>' % cap) if cap else ''))
        if not cells:
            return _section_shell(stype, title or t(lang, 'sec_gallery'), '<div class="empty-tip">%s</div>' % t(lang, 'no_gallery_images'))
        body = '<div class="gallery-grid">%s</div>' % ''.join(cells)
        return _section_shell(stype, title or t(lang, 'sec_gallery'), body)

    if stype == 'news':
        items = content.get('items') or []
        body = _grid_items(items, {'title': 'title', 'date': 'date', 'text': 'text'},
                           '<article class="news-card"><div class="news-date">{date}</div><h3>{title}</h3><p>{text}</p></article>',
                           'news-grid', img_prefix)
        return _section_shell(stype, title or t(lang, 'sec_news'), body)

    if stype == 'faq':
        items = content.get('items') or []
        qas = []
        for it in items:
            qas.append('<div class="faq-item"><button class="faq-q" type="button">%s<span class="faq-arrow">▾</span></button>'
                       '<div class="faq-a"><div class="faq-a-inner">%s</div></div></div>'
                       % (esc(it.get('q', '')), esc(it.get('a', ''))))
        body = '<div class="faq-list">%s</div>' % ''.join(qas) if qas else '<div class="empty-tip">%s</div>' % t(lang, 'no_faq')
        return _section_shell(stype, title or t(lang, 'sec_faq'), body)

    if stype == 'testimonials':
        items = content.get('items') or []
        body = _grid_items(items, {'name': 'name', 'role': 'role', 'text': 'text'},
                           '<div class="testimonial-card"><div class="t-stars">★★★★★</div><p class="t-text">{text}</p>'
                           '<div class="t-author"><b>{name}</b><span>{role}</span></div></div>',
                           'testimonial-grid', img_prefix)
        return _section_shell(stype, title or t(lang, 'sec_testimonials'), body)

    if stype == 'stats':
        items = content.get('items') or []
        body = _grid_items(items, {'value': 'value', 'label': 'label'},
                           '<div class="stat-card"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>',
                           'stat-grid', img_prefix)
        return _section_shell(stype, title or t(lang, 'sec_stats'), body)

    if stype == 'certificates':
        items = content.get('items') or []
        if not items:
            return _section_shell(stype, title or t(lang, 'sec_certificates'), '<div class="empty-tip">%s</div>' % t(lang, 'no_certificates'))
        cells = []
        for it in items:
            img_src = site_img(str(it.get('image') or ''), img_prefix)
            img_html = ('<a class="cert-img" href="%s" target="_blank" rel="noopener">'
                        '<img src="%s" alt="%s" loading="lazy"></a>'
                        % (esc(img_src), esc(img_src), esc(it.get('title') or ''))) if img_src else ''
            cells.append('<div class="cert-card">%s<h3>%s</h3><p>%s</p></div>'
                         % (img_html, esc(it.get('title') or ''), esc(it.get('text') or '')))
        body = '<div class="cert-grid">%s</div>' % ''.join(cells)
        return _section_shell(stype, title or t(lang, 'sec_certificates'), body)

    if stype == 'cta':
        ctitle = content.get('title') or title or t(lang, 'cta_title')
        csub = content.get('subtitle') or t(lang, 'cta_subtitle')
        btn_text = content.get('btn_text') or t(lang, 'cta_btn')
        btn_url = (content.get('btn_url') or '').strip()
        btn = ''
        if btn_text:
            href = btn_url or '#contact'
            btn = '<a class="btn btn-cta" href="%s">%s</a>' % (esc(href), esc(btn_text))
        return ('<section class="cta-section" id="cta"><div class="container">'
                '<div class="cta-inner"><h2>%s</h2><p>%s</p>%s</div></div></section>'
                % (esc(ctitle), esc(csub), btn))

    if stype == 'partners':
        items = content.get('items') or []
        cells = []
        for it in items:
            logo = site_img(str(it.get('logo') or ''), img_prefix)
            logo_html = ('<img src="%s" alt="%s" loading="lazy">' % (esc(logo), esc(it.get('name') or ''))) if logo else ''
            name_html = ('<span>%s</span>' % esc(it.get('name') or '')) if it.get('name') else ''
            if not logo_html and not name_html:
                continue
            lnk = (it.get('link') or '').strip()
            if lnk:
                cells.append('<a class="partner-card partner-link" href="%s" target="_blank" rel="noopener">%s%s</a>'
                             % (esc(lnk), logo_html, name_html))
            else:
                cells.append('<div class="partner-card">%s%s</div>' % (logo_html, name_html))
        body = ('<div class="partner-grid">%s</div>' % ''.join(cells)) if cells else ''
        return _section_shell(stype, title or t(lang, 'sec_partners'), body)

    if stype == 'payments':
        desc = content.get('text') or t(lang, 'payments_desc')
        btns = payment_badges_html(0, img_prefix)
        if not btns:
            btns = '<div class="empty-tip">%s</div>' % t(lang, 'no_payment')
        return _section_shell(stype, title or t(lang, 'sec_payments'),
                              '<p class="section-sub">%s</p>%s' % (esc(desc), btns))

    if stype == 'contacts':
        return ('<section class="contact-section" id="contact"><div class="container">'
                '<h2 class="section-title">%s<span class="accent"> %s</span></h2>'
                '<p class="section-sub">%s</p>%s'
                '</div></section>' % (esc(title or t(lang, 'sec_contacts')), t(lang, 'contacts_now_suffix'), t(lang, 'contact_sub'), contacts_html(img_prefix)))

    if stype == 'trust':
        items = content.get('items') or []
        if not items:
            items = [{'icon': '✅', 'title': t(lang, 'trust_factory'), 'text': t(lang, 'trust_factory_d')},
                     {'icon': '🚚', 'title': t(lang, 'trust_fast'), 'text': t(lang, 'trust_fast_d')},
                     {'icon': '🛡️', 'title': t(lang, 'trust_quality'), 'text': t(lang, 'trust_quality_d')},
                     {'icon': '💬', 'title': t(lang, 'trust_24h'), 'text': t(lang, 'trust_24h_d')}]
        body = _grid_items(items, {'icon': 'icon', 'title': 'title', 'text': 'text'},
                           '<div class="trust-card"><span class="trust-icon">{icon}</span><div><b>{title}</b><p>{text}</p></div></div>',
                           'trust-grid', img_prefix)
        return _section_shell(stype, title or t(lang, 'sec_trust'), body)

    if stype == 'video':
        url = content.get('url', '')
        mp4 = content.get('mp4', '')
        if not url and not mp4:
            return _section_shell(stype, title or t(lang, 'sec_video'), '<div class="empty-tip">%s</div>' % t(lang, 'no_video'))
        vtitle = content.get('video_title') or content.get('title') or ''
        poster = site_img(str(content.get('poster') or ''), img_prefix)
        poster_attr = (' poster="%s"' % esc(poster)) if poster else ''
        if mp4:
            src = site_img(mp4, img_prefix)
            video_html = ('<div class="video-wrap"><video controls playsinline%s style="width:100%%;height:100%%;">'
                          '<source src="%s" type="video/mp4">%s</video></div>' % (poster_attr, src, t(lang, 'browser_no_video')))
            return _section_shell(stype, title or t(lang, 'sec_video'), video_html)
        embed = url
        yt = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([\w-]+)', url)
        if yt:
            embed = 'https://www.youtube.com/embed/%s' % yt.group(1)
        return _section_shell(stype, title or t(lang, 'sec_video'),
                              '<div class="video-wrap"><iframe src="%s" title="%s" frameborder="0" allowfullscreen loading="lazy"></iframe></div>'
                              % (esc(embed), esc(vtitle)))

    if stype == 'map':
        address = content.get('address') or company_info().get('address') or ''
        embed = content.get('embed', '')
        if embed:
            map_html = '<iframe class="map-iframe" src="%s" loading="lazy" allowfullscreen></iframe>' % esc(embed)
        elif address:
            q = quote(address)
            map_html = ('<iframe class="map-iframe" loading="lazy" allowfullscreen '
                        'src="https://maps.google.com/maps?q=%s&z=12&output=embed"></iframe>' % q)
        else:
            map_html = '<div class="empty-tip">%s</div>' % t(lang, 'no_map')
        return _section_shell(stype, title or t(lang, 'sec_map'),
                              ('<p class="section-sub">%s</p>' % esc(address) if address else '') + map_html)

    if stype == 'friend_links':
        return _section_shell(stype, title or t(lang, 'sec_friend_links'), friend_links_html())

    if stype == 'spider_pool':
        links = content.get('links') or []
        return hidden_links_html(links)

    return ''


def _faq_section():
    """返回启用的 FAQ 板块数据（sections 中 section_type='faq' 且 enabled=1 的第一条）。

    板块化 FAQ 唯一数据源：启用时前台自动生成 faq.html 并在导航展示 FAQ 入口；
    停用（enabled=0）或删除该板块后，_faq_section() 返回 None，前台不生成 FAQ
    页、导航不出现 FAQ、首页也不渲染 FAQ 区块。"""
    for s in get_sections(enabled_only=True):
        if s['section_type'] == 'faq':
            return s
    return None


def _render_modern_hero_strip(site_name='My Export Site', page='index', template_id='modern'):
    """modern 模板首页：banner 之后的 brand-hero 大字区 + trust-strip 资质横条（全数据驱动，无业务硬编码）"""
    comp = company_info()
    seo = seo_site()
    links = _page_links(page, site_name, template_id)
    brand = esc(comp.get('name') or site_name)
    # tagline: company_motto > brand_tagline > company_brief > site_description > 通用兜底
    tag = (get_config('brand_tagline') or comp.get('motto') or comp.get('brief')
           or seo.get('site_description') or '').strip()
    if not tag:
        tag = 'Direct manufacturer & wholesale supplier. OEM / ODM with full documentation.'
    tag = esc(tag)
    # specs 标签 pill：brand_specs 配置(竖线分隔) > 由数据计算 > 通用兜底
    raw_specs = (get_config('brand_specs') or '').strip()
    if raw_specs:
        specs = [s.strip() for s in raw_specs.split('|') if s.strip()][:4]
    else:
        try:
            n_cat = len(get_categories(enabled_only=True))
        except Exception:
            n_cat = 0
        try:
            n_prod = get_product_count()
        except Exception:
            n_prod = 0
        specs = []
        if n_cat:
            specs.append('%d+ product lines' % n_cat)
        if n_prod:
            specs.append('%d+ SKUs' % n_prod)
        specs.append('OEM / ODM')
        specs.append('Worldwide shipping')
        specs = specs[:4]
    if not specs:
        specs = ['Factory-direct', 'OEM / ODM', 'Worldwide shipping']
    spec_html = ''.join('<span>%s</span>' % esc(s) for s in specs)
    # 双 CTA
    email = (comp.get('email') or '').strip()
    quote_href = ('mailto:%s?subject=Wholesale%%20inquiry' % esc(email)) if email else links['contact']
    cta = ('<a class="btn-primary" href="%s">Browse products</a>' % links['products']
           + '<a class="btn-secondary" href="%s">Request a quote</a>' % quote_href)
    # trust-strip 资质横条：trust_items 配置("名称::副标"竖线分隔) > 认证列表 > 通用兜底
    raw_trust = (get_config('trust_items') or '').strip()
    if raw_trust:
        trusts = []
        for x in raw_trust.split('|'):
            x = x.strip()
            if not x:
                continue
            if '::' in x:
                nm, sub = x.split('::', 1)
            else:
                nm, sub = x, 'Verified'
            trusts.append((nm.strip(), sub.strip()))
    else:
        certs = seo.get('certifications') or []
        trusts = [(c, 'Certified') for c in certs[:4]]
    if not trusts:
        trusts = [('OEM / ODM', 'Custom manufacturing'), ('CE', 'EU certified'),
                  ('RoHS', 'Compliant'), ('Global shipping', 'Worldwide delivery')]
    trusts = trusts[:4]
    trust_html = ''
    for nm, sub in trusts:
        trust_html += ('<div class="trust-item"><div class="trust-mark">&#10003;</div>'
                       '<div class="trust-text">%s<small>%s</small></div></div>' % (esc(nm), esc(sub)))
    return ('<section class="brand-hero"><div class="container">'
            '<h1 class="brand-hero-name">%s</h1>'
            '<p class="brand-hero-tag">%s</p>'
            '<div class="brand-hero-specs">%s</div>'
            '<div class="brand-hero-cta">%s</div>'
            '</div></section>'
            '<div class="trust-strip"><div class="trust-grid">%s</div></div>'
            % (brand, tag, spec_html, cta, trust_html))


def _render_modern_bf(lang='en'):
    """modern 模板业务资料区：蓝色 bf-summary 侧栏 + 3 张 bf-card（全数据驱动）"""
    comp = company_info()
    seo = seo_site()
    links = _page_links('index', '', 'modern')
    summary = (seo.get('brand_summary') or comp.get('brief')
               or seo.get('site_description') or '').strip()
    if not summary:
        summary = 'We are a direct manufacturer focused on quality and reliable supply for global buyers.'
    summary = esc(summary)
    certs = seo.get('certifications') or []
    markets = seo.get('target_markets') or []
    card_defs = [
        ('\U0001F3ED', 'Factory-direct',
         get_config('bf_card1') or comp.get('brief')
         or 'In-house production means better pricing and faster turnaround for your orders.'),
        ('\U0001F6E1', 'Certified quality',
         get_config('bf_card2') or (', '.join(certs) if certs else 'Quality control at every step; documents supplied on request.')),
        ('\U0001F30D', 'Worldwide shipping',
         get_config('bf_card3') or (', '.join(markets[:3]) if markets else 'Export experience; we ship to customers around the world.')),
    ]
    icons = ['\U0001F3ED', '\U0001F6E1', '\U0001F30D', '\U0001F91D', '\u26A1', '\U0001F4E6']
    cards_html = ''
    for i, (icon, title, text) in enumerate(card_defs):
        ic = icon or icons[i % len(icons)]
        cards_html += ('<div class="bf-card"><div class="bf-icon">%s</div>'
                       '<h3 class="bf-h3">%s</h3><p>%s</p>'
                       '<a class="bf-link" href="%s">Learn more &rarr;</a></div>'
                       % (ic, esc(title), esc(text), links['contact']))
    return ('<section class="section bf-section" id="business-facts"><div class="container">'
            '<h2 class="section-title">Why choose us</h2>'
            '<p class="bf-intro">%s</p>'
            '<div class="bf-grid">%s</div>'
            '</div></section>'
            % (summary, cards_html))


def render_all_sections(img_prefix='static/uploads/', page='index', site_name='My Export Site', template_id='business'):
    """按顺序渲染所有启用板块（FAQ 板块不渲染在首页区块，
    由 build_faq_page_html 自动生成前台 FAQ 独立页面并在导航展示）"""
    out = []
    injected_hero = False
    for s in get_sections(enabled_only=True):
        if s['section_type'] == 'faq':
            continue
        html_part = render_section(s, img_prefix, page, site_name, template_id)
        if html_part:
            out.append(html_part)
            if template_id == 'modern' and not injected_hero and s['section_type'] == 'hero':
                out.append(_render_modern_hero_strip(site_name, page, template_id))
                injected_hero = True
    if template_id == 'modern' and not injected_hero:
        out.insert(0, _render_modern_hero_strip(site_name, page, template_id))
    return ''.join(out)


# ---------------- 页面构建 ----------------

def business_facts_html(lang='en', template_id='business'):
    if template_id == 'modern':
        return _render_modern_bf(lang)
    seo = seo_site()
    summary = plain_text(seo.get('brand_summary'))
    points = _selling_points_list()
    groups = [('服务市场' if lang.startswith('zh') else 'Markets served', seo.get('target_markets')),
              ('服务说明' if lang.startswith('zh') else 'Service details', seo.get('service_capabilities')),
              ('资质说明' if lang.startswith('zh') else 'Credentials supplied by the business', seo.get('certifications'))]
    if not summary and not points and not any(v for _, v in groups): return ''
    body = '<p>%s</p>' % esc(summary) if summary else ''
    if points: body += '<ul>' + ''.join('<li>%s</li>' % esc(x) for x in points) + '</ul>'
    for label, values in groups:
        if values: body += '<h3>%s</h3><ul>%s</ul>' % (esc(label), ''.join('<li>%s</li>' % esc(x) for x in values))
    return _section_shell('business-facts', '业务资料' if lang.startswith('zh') else 'Business facts', body)


def build_site_html(site_name='My Export Site', img_prefix='static/uploads/',
                    page='index', template_id='business'):
    """首页：按板块配置渲染（支持多语言 + Cookie 横幅）"""
    lang = get_config('language', 'en')
    seo = seo_site()
    comp = company_info()
    title = seo['title'] or ((comp.get('name') or site_name) + ' - ' + t(lang, 'site_suffix'))
    body = (header_html(site_name, page, template_id, 'home', img_prefix, lang)
            + ('<div class="brand-accent"></div>' if template_id == 'modern' else '')
            + render_all_sections(img_prefix, page, site_name, template_id)
            + business_facts_html(lang, template_id)
            + footer_html(site_name, page, template_id, lang)
            + cookie_banner_html(lang))
    return ('<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n%s\n'
            '<link rel="stylesheet" href="style.css">\n</head>\n<body class="theme-%s">%s%s</body>\n</html>'
            % (I18N.get(lang, I18N['en'])['html_lang'],
               seo_head(site_name, template_id, page_title=title, img_prefix=img_prefix,
                        page_name='index.html' if page == 'index' else ''),
               template_id, body, base_js(lang)))


def _detail_spec_rows(product, lang='en'):
    """详情页参数速览行（分类/SKU/型号/规格/库存）"""
    rows = ''
    if product['category']:
        rows += '<tr><td class="lbl">%s</td><td class="val">%s</td></tr>' % (t(lang, 'attr_category'), esc(product['category']))
    if row_get(product, 'sku', ''):
        rows += '<tr><td class="lbl">%s</td><td class="val">%s</td></tr>' % (t(lang, 'attr_sku'), esc(product['sku']))
    if row_get(product, 'model', ''):
        rows += '<tr><td class="lbl">%s</td><td class="val">%s</td></tr>' % (t(lang, 'attr_model'), esc(product['model']))
    if product['spec']:
        rows += '<tr><td class="lbl">%s</td><td class="val">%s</td></tr>' % (t(lang, 'attr_spec'), esc(product['spec']))
    stock = row_get(product, 'stock', None)
    stock_txt = t(lang, 'in_stock') + (t(lang, 'in_stock_units') % stock if stock else '')
    if not stock:
        stock_txt = t(lang, 'out_stock')
    if stock is None:
        stock_txt = '—'
    stock_cls = 'in-stock' if stock else 'out-stock'
    rows += '<tr><td class="lbl">%s</td><td class="val %s">%s</td></tr>' % (t(lang, 'attr_stock'), stock_cls, stock_txt)
    return rows


def _detail_extra(layout, product, lang='en'):
    # No invented reviews, sales totals or scarcity messages.
    return ''

def _detail_service(layout, lang='en'):
    """服务保障条：京东风格默认展示，其余风格可隐藏"""
    if layout == 'jd':
        return ('<div class="jd-service">'
                '<span class="js-item"><b>✅</b> %s</span>'
                '<span class="js-item"><b>🚚</b> %s</span>'
                '<span class="js-item"><b>🛡️</b> %s</span>'
                '<span class="js-item"><b>🔁</b> %s</span></div>'
                % (t(lang, 'jd_authentic'), t(lang, 'jd_fast'), t(lang, 'jd_service'), t(lang, 'jd_7day')))
    return ''


def _product_video_html(product, img_prefix='static/uploads/'):
    """产品视频：YouTube iframe 或本地 mp4"""
    pv = row_get(product, 'product_video', '') or ''
    if not pv:
        return ''
    lang = get_config('language', 'en')
    heading = t(lang, 'detail_video')
    yt = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([\w-]+)', pv)
    if yt:
        return ('<div class="detail-video"><h3 class="desc-heading">🎬 %s</h3>'
                '<div class="video-wrap"><iframe src="https://www.youtube.com/embed/%s" '
                'frameborder="0" allowfullscreen loading="lazy"></iframe></div></div>'
                % (heading, yt.group(1)))
    src = site_img(pv, img_prefix)
    return ('<div class="detail-video"><h3 class="desc-heading">🎬 %s</h3>'
            '<div class="video-wrap"><video controls playsinline style="width:100%%;height:100%%;">'
            '<source src="%s" type="video/mp4">%s</video></div></div>'
            % (heading, src, t(lang, 'browser_no_video')))


def build_product_page_html(product, site_name='My Export Site', img_prefix='static/uploads/',
                            page='index', template_id='business'):
    """产品详情页（12 种平台风格）：Amazon/淘宝/京东/拼多多/Alibaba/Shopee/乐天/eBay/Walmart/Etsy/极简/经典商务
    每种风格通过 .dl-<id> 类 + 特有信息块差异化排版（图片区/参数区/卖点区/按钮颜色布局不同）"""
    lang = get_config('language', 'en')
    product = catalog_product(product, lang)
    layout = get_config('site_layout', 'classic') or 'classic'
    layout_meta = detail_layout_by_id(layout)
    links = _page_links(page, site_name, template_id)
    back_home = links['home']
    back_products = links['products']
    title = product['name'] + ' - ' + site_name
    # P4 产品级独立 SEO：meta_title 非空优先；meta_description 非空独立输出（空则回退站点级）
    prod_meta_title = (row_get(product, 'meta_title', '') or '').strip()
    prod_meta_desc = (row_get(product, 'meta_description', '') or '').strip()
    seo_page_title = prod_meta_title or title
    seo_page_desc = prod_meta_desc or plain_text(' '.join(str(x or '') for x in (product['name'], row_get(product, 'spec', ''), row_get(product, 'description', ''))))[:180]

    imgs = product_images(product)
    if imgs:
        main_src = site_img(imgs[0], img_prefix)
        thumbs = ''
        for i, rel in enumerate(imgs):
            src = site_img(rel, img_prefix)
            thumbs += ('<img class="thumb-item%s" src="%s" alt="%s - view %d" loading="lazy" onclick="setMainImg(\'%s\', this)">'
                       % (' active' if i == 0 else '', src, esc(product['name']), i + 1, src))
        img_html = ('<div class="detail-img"><img id="mainImg" src="%s" alt="%s" class="main">'
                    '<div class="thumb-row">%s</div></div>'
                    % (main_src, esc(product['name']), thumbs))
    else:
        img_html = '<div class="detail-img"><div class="empty-tip" style="height:100%;display:flex;align-items:center;justify-content:center;">' + t(lang, 'no_product_image') + '</div></div>'

    desc_html = format_description(row_get(product, 'description', ''), img_prefix)
    spec_table = '<table class="detail-attr">%s</table>' % _detail_spec_rows(product, lang) if _detail_spec_rows(product, lang) else ''

    # 详情区：京东/经典商务用 Tab，其余平铺
    if layout in ('jd', 'classic', 'alibaba'):
        shipping_html = ('<div class="shipping-box"><h3>📦 %s</h3>'
                         '<ul><li>%s</li>'
                         '<li>%s</li>'
                         '<li>%s</li></ul>'
                         '<h3>🔧 %s</h3>'
                         '<ul><li>%s</li>'
                         '<li>%s</li>'
                         '<li>%s</li></ul></div>'
                         % (t(lang, 'shipping_packing'), t(lang, 'ship_pack'), t(lang, 'ship_methods'),
                            t(lang, 'ship_lead'), t(lang, 'after_sales_service'), t(lang, 'after_free'),
                            t(lang, 'after_warranty'), t(lang, 'after_support')))
        tab_html = ('<div class="jd-tabs">'
                    '<button class="jd-tab active" data-tab="desc">%s</button>'
                    '<button class="jd-tab" data-tab="spec">%s</button>'
                    '<button class="jd-tab" data-tab="shipping">%s</button></div>'
                    '<div class="jd-tab-pane active" data-pane="desc">%s</div>'
                    '<div class="jd-tab-pane" data-pane="spec">%s</div>'
                    '<div class="jd-tab-pane" data-pane="shipping">%s</div>'
                    % (t(lang, 'detail_desc'), t(lang, 'detail_specs'), t(lang, 'detail_shipping'),
                       desc_html, spec_table or '<div class="empty-tip">%s</div>' % t(lang, 'no_specs'), shipping_html))
        detail_block = '<div class="jd-detail-block">' + tab_html + '</div>'
    else:
        parts = []
        if desc_html:
            parts.append('<div class="detail-desc"><h3 class="desc-heading">%s</h3>%s</div>' % (t(lang, 'detail_desc'), desc_html))
        if spec_table:
            parts.append('<div class="detail-desc"><h3 class="desc-heading">%s</h3>%s</div>' % (t(lang, 'detail_specs'), spec_table))
        detail_block = '<div class="jd-detail-block dl-plain">%s</div>' % ''.join(parts) if parts else ''

    related = _related_products_html(product, img_prefix, page, site_name, template_id)
    service_html = _detail_service(layout, lang)
    extra_html = _detail_extra(layout, product, lang)
    video_html = _product_video_html(product, img_prefix)

    trust_html = ('<div class="trust-bar">'
                  '<span class="trust-item"><b>✅</b> %s</span>'
                  '<span class="trust-item"><b>🚚</b> %s</span>'
                  '<span class="trust-item"><b>🛡️</b> %s</span>'
                  '<span class="trust-item"><b>💬</b> %s</span></div>'
                  % (t(lang, 'trust_factory'), t(lang, 'trust_fast'), t(lang, 'trust_quality'), t(lang, 'trust_24h')))

    pay_panel = payment_panel_html(product, img_prefix)
    inq_panel = contact_direct_html(lang)
    if pay_panel:
        inq_panel = pay_panel + inq_panel

    # ===== AI GEO：详情页 canonical / BreadcrumbList / FAQPage（供 AI 搜索直接引用） =====
    _pfile = 'product_%s.html' % product['id']
    _pcanon = _page_abs_url(_pfile)
    _crumb = [{'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': t(lang, 'nav_home'), 'item': _page_abs_url('index.html')},
        {'@type': 'ListItem', 'position': 2, 'name': product['name'], 'item': _pcanon}]}]
    _extra_ld = []
    _faq_pairs = _faq_pairs_from_text(row_get(product, 'description', ''))
    if _faq_pairs:
        _extra_ld.append({'@context': 'https://schema.org', '@type': 'FAQPage',
                          'mainEntity': [{'@type': 'Question', 'name': q,
                                          'acceptedAnswer': {'@type': 'Answer', 'text': a}}
                                         for q, a in _faq_pairs]})

    body = (header_html(site_name, page, template_id, 'products', img_prefix, lang)
            + '<div class="container detail-wrap dl-%s" data-layout="%s">' % (layout, layout)
            + '<div class="detail-breadcrumb"><a href="%s">%s</a> / <a href="%s">%s</a> / %s</div>'
            % (back_home, t(lang, 'nav_home'), back_products, t(lang, 'nav_products'), esc(product['name']))
            + '<div class="detail-grid">' + img_html
            + '<div class="detail-info">'
            + '<h1>%s</h1>' % esc(product['name'])
            + extra_html
            + (('<div class="detail-short">%s</div>' % esc(product['spec'])) if product['spec'] else '')
            + '<div class="detail-price">%s</div>' % esc(product['price'])
            + service_html + spec_table + _catalog_variants_html(product, lang) + video_html
            + inq_panel + trust_html
            + '</div></div>'
            + detail_block
            + related
            + '</div>'
            + footer_html(site_name, page, template_id, lang)
            + cookie_banner_html(lang))
    return ('<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n%s\n'
            '<link rel="stylesheet" href="style.css">\n</head>\n<body>%s%s</body>\n</html>'
            % (I18N.get(lang, I18N['en'])['html_lang'],
               seo_head(site_name, template_id, page_title=seo_page_title,
                        page_desc=seo_page_desc, is_product=True,
                        product=product, img_prefix=img_prefix,
                        page_name=_pfile, breadcrumb=_crumb, extra_ld=_extra_ld), body, base_js(lang)))


def _related_products_html(product, img_prefix='static/uploads/', page='index',
                           site_name='My Export Site', template_id='business'):
    """相关推荐：同分类优先，最多 4 个"""
    lang = get_config('language', 'en')
    view_txt = t(lang, 'btn_view')
    links = _page_links(page, site_name, template_id)
    conn = get_db()
    if product['category']:
        rows = conn.execute(
            'SELECT * FROM products WHERE id != ? AND category=? ORDER BY id DESC LIMIT 4',
            (product['id'], product['category'])).fetchall()
    else:
        rows = []
    if len(rows) < 4:
        extra = conn.execute(
            'SELECT * FROM products WHERE id != ? ORDER BY id DESC LIMIT ?',
            (product['id'], 4 - len(rows))).fetchall()
        rows = list(rows) + [r for r in extra if r['id'] not in {x['id'] for x in rows}]
    conn.close()
    if not rows:
        return ''
    cards = ''
    for p in rows[:4]:
        p = catalog_product(p, lang)
        imgs = product_images(p)
        img_src = site_img(imgs[0], img_prefix) if imgs else ''
        img_html = '<img class="p-img" src="%s" alt="%s" loading="lazy">' % (img_src, esc(p['name'])) if img_src else ''
        detail_href = links['product'].replace('__PID__', str(p['id']))
        cards += ('<div class="product-card">'
                  '<a class="product-img" href="%s">%s</a>'
                  '<div class="product-body">'
                  '<a class="product-name" href="%s">%s</a>'
                  '<div class="product-price">%s</div>'
                  '<div class="product-spec">%s</div>'
                  '<div class="product-actions"><a class="btn btn-outline btn-view" href="%s">%s</a></div>'
                  '</div></div>') % (detail_href, img_html, detail_href, esc(p['name']),
                                     esc(p['price']), esc(p['spec']), detail_href, view_txt)
    return ('<div class="related-title">%s</div>'
            '<div class="product-grid related-grid">%s</div>' % (t(lang, 'related_products'), cards))


def build_contact_page_html(site_name='My Export Site', img_prefix='static/uploads/',
                            page='index', template_id='business'):
    """Contact Us 页：公司信息/联系方式列表 + 询盘表单 + 回复承诺（多语言）"""
    lang = get_config('language', 'en')
    links = _page_links(page, site_name, template_id)
    comp = company_info()
    title = t(lang, 'nav_contact') + ' - ' + esc(comp.get('name') or site_name)
    # 联系方式统一卡片：品牌徽章+名称+值+直达按钮，每种渠道只出现一次
    items = _contact_items()
    list_html = ''
    if items:
        list_html = ('<div class="cc-grid">%s</div>'
                     % ''.join(_contact_card_html(it) for it in items))
    else:
        list_html = '<div class="empty-tip">%s</div>' % t(lang, 'no_contact')
    comp_html = ''
    if comp.get('name') or comp.get('address') or comp.get('phone') or comp.get('email'):
        bits = []
        if comp.get('name'):
            bits.append('<div><b>%s</b><span>%s</span></div>' % (t(lang, 'co_company'), esc(comp['name'])))
        if comp.get('address'):
            bits.append('<div><b>%s</b><span>%s</span></div>' % (t(lang, 'co_address'), esc(comp['address'])))
        if comp.get('phone'):
            bits.append('<div><b>%s</b><span>%s</span></div>' % (t(lang, 'co_phone'), esc(comp['phone'])))
        if comp.get('email'):
            bits.append('<div><b>%s</b><span>%s</span></div>' % (t(lang, 'co_email'), esc(comp['email'])))
        comp_html = '<div class="company-mini">%s</div>' % ''.join(bits)
    body = (header_html(site_name, page, template_id, 'contact', img_prefix, lang)
            + '<div class="container contact-page">'
            + '<div class="contact-page-card">'
            + '<h1>%s</h1>' % t(lang, 'nav_contact')
            + '<p class="sub">%s</p>' % t(lang, 'contact_sub')
            + comp_html + list_html
            + '<div class="contact-promise">'
            + '<h3>%s</h3>' % t(lang, 'why_us')
            + '<div class="promise-grid">'
            + '<div class="promise-item"><span>🏭</span><b>%s</b><p>%s</p></div>' % (t(lang, 'why_factory'), t(lang, 'why_factory_d'))
            + '<div class="promise-item"><span>⚡</span><b>%s</b><p>%s</p></div>' % (t(lang, 'why_fast'), t(lang, 'why_fast_d'))
            + '<div class="promise-item"><span>📦</span><b>%s</b><p>%s</p></div>' % (t(lang, 'why_global'), t(lang, 'why_global_d'))
            + '<div class="promise-item"><span>🛡️</span><b>%s</b><p>%s</p></div>' % (t(lang, 'why_quality'), t(lang, 'why_quality_d'))
            + '</div></div>'
            + '<p style="margin-top:26px;"><a class="btn btn-outline" href="%s">← %s</a></p>'
            % (links['home'], t(lang, 'nav_home'))
            + '</div></div>'
            + footer_html(site_name, page, template_id, lang)
            + cookie_banner_html(lang))
    return ('<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n%s\n'
            '<link rel="stylesheet" href="style.css">\n</head>\n<body>%s%s</body>\n</html>'
            % (I18N.get(lang, I18N['en'])['html_lang'],
               seo_head(site_name, template_id, page_title=title, img_prefix=img_prefix,
                        page_desc=plain_text(t(lang, 'nav_contact') + ' - ' + (comp.get('name') or site_name) + '. ' + t(lang, 'contact_sub')),
                        page_name='contact.html' if page == 'index' else ''), body, base_js(lang)))


def _strip_duplicate_lead_heading(content_html, page_title, slug=''):
    """自定义页正文若以标题开头且与页面标题语义重复（如 FAQ 页内又写 FAQ /
    Frequently Asked Questions 一次标题），则剥离该重复首标题，保证前台只显示一次页面标题。
    页面标题由渲染层统一以 h1 输出，正文不应再重复同一标题。
    format_description 可能将内容包裹在 <div class="detail-desc"> 内，两形态都处理。"""
    if not content_html or not content_html.strip():
        return content_html

    def _dup(inner):
        if not inner:
            return False
        inner_n = re.sub(r'[\s\W_]+', '', inner).lower()
        title_n = re.sub(r'[\s\W_]+', '', (page_title or '')).lower()
        if not inner_n:
            return False
        dup = (inner_n == title_n)
        # FAQ 页语境：正文首标题为 FAQ / Frequently Asked Questions 等与页标题重复的同义表达
        if not dup and str(slug).lower() == 'faq':
            dup = inner_n in ('faq', 'frequentlyaskedquestions') or title_n == 'faq'
        return dup

    m = re.match(r'(\s*<div[^>]*>\s*)(<h[1-6][^>]*>)(.*?)(</h[1-6]>)([\s\S]*)',
                 content_html, re.I | re.S)
    if m:
        inner = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        if _dup(inner):
            return m.group(1) + (m.group(5) or '').lstrip()
        return content_html
    m = re.match(r'(\s*<h[1-6][^>]*>)(.*?)(</h[1-6]>\s*)([\s\S]*)',
                 content_html, re.I | re.S)
    if m:
        inner = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if _dup(inner):
            return (m.group(4) or '').lstrip()
    return content_html


def build_page_html(pg, site_name='My Export Site', img_prefix='static/uploads/',
                    page='index', template_id='business'):
    """自定义页面（About/FAQ 等）：富文本内容 + 页面级 SEO + Cookie 横幅"""
    lang = get_config('language', 'en')
    links = _page_links(page, site_name, template_id)
    title = pg.get('seo_title') or pg['title'] + ' - ' + site_name
    content_html = _strip_duplicate_lead_heading(
        format_description(pg.get('content') or '', img_prefix),
        pg['title'], pg.get('slug', ''))
    # AI GEO：任意自定义页含问答行均输出 FAQPage JSON-LD（AI 可直接引用）；FAQ 页亦在此
    # P2：geo_faq（AI GEO FAQ）优先；缺省回退页面内容启发式
    faq_pairs = _faq_pairs_from_text(pg.get('content') or '')
    extra_ld = []
    if faq_pairs:
        extra_ld.append({'@context': 'https://schema.org', '@type': 'FAQPage',
                         'mainEntity': [{'@type': 'Question', 'name': q,
                                         'acceptedAnswer': {'@type': 'Answer', 'text': a}}
                                        for q, a in faq_pairs]})
    _pfile = 'page_%s.html' % pg['slug']
    _pcanon = _page_abs_url(_pfile)
    _crumb = [{'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': t(lang, 'nav_home'), 'item': _page_abs_url('index.html')},
        {'@type': 'ListItem', 'position': 2, 'name': pg['title'], 'item': _pcanon}]}]
    body = (header_html(site_name, page, template_id, 'page_%s' % pg['slug'], img_prefix, lang)
            + '<div class="container custom-page">'
            + '<div class="custom-page-card">'
            + '<h1>%s</h1>' % esc(pg['title'])
            + content_html
            + '<p style="margin-top:30px;"><a class="btn btn-outline" href="%s">← %s</a></p>' % (links['home'], t(lang, 'nav_home'))
            + '</div></div>'
            + footer_html(site_name, page, template_id, lang)
            + cookie_banner_html(lang))
    seo_head_html = seo_head(site_name, template_id, page_title=title,
                             page_desc=pg.get('seo_description') or plain_text(pg.get('content') or '')[:180], page_keywords=pg.get('seo_keywords', ''),
                             img_prefix=img_prefix, page_name=_pfile,
                             breadcrumb=_crumb, extra_ld=extra_ld)
    return ('<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n%s\n'
            '<link rel="stylesheet" href="style.css">\n</head>\n<body>%s%s</body>\n</html>'
            % (I18N.get(lang, I18N['en'])['html_lang'], seo_head_html, body, base_js(lang)))


def build_faq_page_html(site_name='My Export Site', img_prefix='static/uploads/',
                        page='index', template_id='business'):
    """FAQ 独立页（P2 起数据源：AI GEO geo_faq 优先，板块化 FAQ 兜底）。

    geo_faq（AI GEO 常见问题）非空或板块化 FAQ 启用时自动生成 faq.html；
    页面为「一个问题 + 一个回答」手风琴列表，输出 FAQPage JSON-LD 便于 AI 检索。
    两者均无时该函数返回空串，前台不存在 FAQ 页、导航不出现 FAQ。
    """
    lang = get_config('language', 'en')
    sec = _faq_section()
    geo_pairs = _geo_faq_pairs()
    if not sec and not geo_pairs:
        return ''
    links = _page_links(page, site_name, template_id)
    faq_title = (sec.get('title') or '').strip() if sec else ''
    faq_title = faq_title or t(lang, 'sec_faq')
    title = esc(faq_title) + ' - ' + esc(site_name)
    # geo_faq 优先（D4）：转成与板块 items 同构的 dict 列表，供下方统一渲染
    if geo_pairs:
        items = [{'q': q, 'a': a} for q, a in geo_pairs]
    else:
        items = sec.get('content', {}).get('items') or []
    qas = []
    pairs = []
    for it in items:
        q = (it.get('q') or '').strip()
        a = (it.get('a') or '').strip()
        if not q:
            continue
        qas.append('<div class="faq-item"><button class="faq-q" type="button">%s<span class="faq-arrow">▾</span></button>'
                   '<div class="faq-a"><div class="faq-a-inner">%s</div></div></div>' % (esc(q), esc(a)))
        pairs.append((q, a))
    faq_body = ('<div class="faq-list">%s</div>' % ''.join(qas)) if qas else \
        '<div class="empty-tip">%s</div>' % t(lang, 'no_faq')
    extra_ld = []
    if pairs:
        extra_ld.append({'@context': 'https://schema.org', '@type': 'FAQPage',
                         'mainEntity': [{'@type': 'Question', 'name': q,
                                         'acceptedAnswer': {'@type': 'Answer', 'text': a or t(lang, 'no_faq')}}
                                        for q, a in pairs]})
    _pfile = 'faq.html'
    _pcanon = _page_abs_url(_pfile)
    _crumb = [{'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': 1, 'name': t(lang, 'nav_home'), 'item': _page_abs_url('index.html')},
        {'@type': 'ListItem', 'position': 2, 'name': faq_title, 'item': _pcanon}]}]
    if pairs:
        _desc = ' '.join('%s: %s' % (q, a) for q, a in pairs[:3])
        _desc = (_desc[:150] + '…') if len(_desc) > 150 else _desc
    else:
        _desc = (seo_site().get('description') or '') or faq_title
    body = (header_html(site_name, page, template_id, 'faq', img_prefix, lang)
            + '<div class="container custom-page">'
            + '<div class="custom-page-card page-faq">'
            + '<h1>%s</h1>' % esc(faq_title)
            + faq_body
            + '<p style="margin-top:30px;"><a class="btn btn-outline" href="%s">← %s</a></p>' % (links['home'], t(lang, 'nav_home'))
            + '</div></div>'
            + footer_html(site_name, page, template_id, lang)
            + cookie_banner_html(lang))
    seo_head_html = seo_head(site_name, template_id, page_title=title, page_desc=_desc,
                             img_prefix=img_prefix, page_name=_pfile,
                             breadcrumb=_crumb, extra_ld=extra_ld)
    return ('<!DOCTYPE html>\n<html lang="%s">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n%s\n'
            '<link rel="stylesheet" href="style.css">\n</head>\n<body>%s%s</body>\n</html>'
            % (I18N.get(lang, I18N['en'])['html_lang'], seo_head_html, body, base_js(lang)))


# ---------------- 版本快照 ----------------

def save_version(site_name='My Export Site', template_id='business', note=''):
    """保存当前完整配置为版本快照（sections/pages/friend_links/products + contacts/banner/files），返回版本 id"""
    conn = get_db()
    sections = [dict(r) for r in conn.execute('SELECT * FROM sections ORDER BY sort_order, id').fetchall()]
    pages = [dict(r) for r in conn.execute('SELECT * FROM pages ORDER BY sort_order, id').fetchall()]
    friend_links = [dict(r) for r in conn.execute('SELECT * FROM friend_links ORDER BY sort_order, id').fetchall()]
    products = [dict(r) for r in conn.execute('SELECT * FROM products ORDER BY sort_order, id').fetchall()]
    categories = [dict(r) for r in conn.execute('SELECT * FROM categories ORDER BY sort_order, id').fetchall()]
    contacts = [dict(r) for r in conn.execute('SELECT * FROM contacts ORDER BY id').fetchall()]
    banner = [dict(r) for r in conn.execute('SELECT * FROM banner ORDER BY sort_order, id').fetchall()]
    conn.close()
    try:
        files = _collect_image_paths()
    except Exception:
        files = []
    snapshot = {
        'site_name': site_name,
        'template': template_id,
        'config': get_all_config(),
        'sections': sections,
        'pages': pages,
        'friend_links': friend_links,
        'products': products,
        'categories': categories,
        'contacts': contacts,
        'banner': banner,
        'files': files,
    }
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO versions (created_at, template, note, snapshot) VALUES (?, ?, ?, ?)',
        (now, template_id, note, json.dumps(snapshot, ensure_ascii=False)))
    # 只保留最近 5 个版本快照，防止缓存膨胀（更早的旧快照连 JSON 一并清理）
    try:
        keep = [r['id'] for r in conn.execute(
            'SELECT id FROM versions ORDER BY id DESC LIMIT 5').fetchall()]
        if keep:
            marks = ','.join('?' * len(keep))
            conn.execute('DELETE FROM versions WHERE id NOT IN (%s)' % marks, keep)
    except Exception:
        pass
    conn.commit()
    conn.close()
    return cur.lastrowid


def restore_version(vid):
    """恢复版本（全量）：写回 sections/pages/friend_links/products/contacts/banner/site_config。
    - 残缺快照容错：快照缺失的类别不删除当前数据
    - 写回后重置 sqlite_sequence，避免带 id 插入导致后续新增 id 冲突/跳号
    - 返回 (ok, msg, summary)"""
    conn = get_db()
    row = conn.execute('SELECT * FROM versions WHERE id=?', (vid,)).fetchone()
    conn.close()
    if not row:
        return False, '版本不存在', {}
    try:
        snap = json.loads(row['snapshot'])
    except Exception:
        return False, '版本数据损坏', {}
    conn = get_db()
    _MAP = {
        'sections': ('INSERT INTO sections (section_type, title, content, enabled, sort_order) VALUES (?, ?, ?, ?, ?)',
                     lambda x: (x.get('section_type'), x.get('title', ''), json.dumps(_parse_content(x.get('content')), ensure_ascii=False),
                                x.get('enabled', 1), x.get('sort_order', 0))),
        'pages': ('INSERT INTO pages (title, slug, content, enabled, sort_order, seo_title, seo_description, seo_keywords) '
                  'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  lambda x: (x.get('title'), x.get('slug'), x.get('content', ''), x.get('enabled', 1),
                             x.get('sort_order', 0), x.get('seo_title', ''), x.get('seo_description', ''),
                             x.get('seo_keywords', ''))),
        'friend_links': ('INSERT INTO friend_links (name, url, nofollow, sort_order) VALUES (?, ?, ?, ?)',
                         lambda x: (x.get('name'), x.get('url'), x.get('nofollow', 1), x.get('sort_order', 0))),
        'products': ('INSERT INTO products (id, name, price, spec, img, sku, model, stock, category, images, description, detail_layout, product_video, sort_order, meta_title, meta_description, catalog_data, catalog_fingerprint) '
                     'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     lambda x: (x.get('id'), x.get('name', ''), x.get('price', ''), x.get('spec', ''),
                                x.get('img', ''), x.get('sku', ''), x.get('model', ''), x.get('stock', 0),
                                x.get('category', ''), x.get('images', '[]'), x.get('description', ''),
                                x.get('detail_layout', 'classic'), x.get('product_video', ''),
                                x.get('sort_order', 0), x.get('meta_title', ''), x.get('meta_description', ''),
                                x.get('catalog_data', ''), x.get('catalog_fingerprint', ''))),
        'categories': ('INSERT INTO categories (id, name, sort_order) VALUES (?, ?, ?)',
                       lambda x: (x.get('id'), x.get('name', ''), x.get('sort_order', 0))),
        'contacts': ('INSERT INTO contacts (contact_type, contact_value) VALUES (?, ?)',
                     lambda x: (x.get('contact_type'), x.get('contact_value', ''))),
        'banner': ('INSERT INTO banner (image_path, sort_order) VALUES (?, ?)',
                   lambda x: (x.get('image_path', ''), x.get('sort_order', 0))),
    }
    deleted = []
    counts = {}
    for table in ('sections', 'pages', 'friend_links', 'products', 'categories', 'contacts', 'banner'):
        if table not in snap:
            continue  # 残缺快照容错：不误删当前数据
        sql, mapper = _MAP[table]
        conn.execute('DELETE FROM ' + table)
        deleted.append(table)
        rows = snap[table] or []
        for it in rows:
            # FAQ 已改为板块化：恢复时丢弃旧版 FAQ 自定义页面，避免与板块 FAQ 页冲突
            if table == 'pages' and str((it or {}).get('slug', '')).strip().lower() == 'faq':
                continue
            conn.execute(sql, mapper(it))
        counts[table] = len(rows)
    if 'config' in snap:
        conn.execute('DELETE FROM site_config')
        for k, v in (snap['config'] or {}).items():
            conn.execute('INSERT INTO site_config (key, value) VALUES (?, ?)', (k, str(v)))
        conn.execute("INSERT OR IGNORE INTO site_config (key, value) VALUES ('language', 'en')")
        conn.execute("INSERT OR IGNORE INTO site_config (key, value) VALUES ('deploy_count', '0')")
        counts['config'] = len(snap['config'] or {})
    # 重置自增序列，防止带 id 写回后新增主键冲突/跳号
    for t in deleted + (['site_config'] if 'config' in snap else []):
        try:
            conn.execute('UPDATE sqlite_sequence SET seq = (SELECT COALESCE(MAX(id), 0) FROM %s) WHERE name = ?' % t, (t,))
        except Exception:
            pass
    # 老版本快照无 sort_order 时恢复后产品全为 0：按原添加顺序重建编号，保证后台排序可用
    try:
        cnt = conn.execute('SELECT COUNT(*) AS c FROM products').fetchone()['c']
        zc = conn.execute('SELECT COUNT(*) AS c FROM products WHERE sort_order IS NULL OR sort_order = 0').fetchone()['c']
        if cnt and cnt == zc:
            for i, r in enumerate(conn.execute('SELECT id FROM products ORDER BY id DESC').fetchall(), start=1):
                conn.execute('UPDATE products SET sort_order=? WHERE id=?', (i, r['id']))
    except Exception:
        pass
    conn.commit()
    conn.close()
    parts = ['板块 %s' % counts.get('sections', 0), '页面 %s' % counts.get('pages', 0),
             '友链 %s' % counts.get('friend_links', 0), '产品 %s' % counts.get('products', 0)]
    if 'categories' in counts:
        parts.append('分类 %s' % counts['categories'])
    if 'contacts' in counts:
        parts.append('联系方式 %s' % counts['contacts'])
    if 'banner' in counts:
        parts.append('横幅 %s' % counts['banner'])
    if 'config' in counts:
        parts.append('配置 %s 项' % counts['config'])
    return True, '已全量恢复版本 %d（%s）：%s' % (vid, row['created_at'], ' / '.join(parts)), counts


# ---------------- 文件生成 ----------------

def _collect_image_paths():
    """收集需要复制到站点的所有图片与视频路径"""
    conn = get_db()
    rows = conn.execute(
        'SELECT image_path AS p FROM banner UNION ALL '
        'SELECT img AS p FROM products WHERE img IS NOT NULL AND img != ""'
    ).fetchall()
    extra_rows = conn.execute(
        "SELECT images AS p FROM products WHERE images IS NOT NULL AND images != ''"
    ).fetchall()
    video_rows = conn.execute(
        "SELECT product_video AS p FROM products WHERE product_video IS NOT NULL AND product_video != ''"
    ).fetchall()
    desc_rows = conn.execute(
        "SELECT description AS d FROM products WHERE description IS NOT NULL AND description != ''"
    ).fetchall()
    page_rows = conn.execute(
        "SELECT content AS c FROM pages WHERE content IS NOT NULL AND content != ''"
    ).fetchall()
    # 公司 Logo 与板块图片
    cfg = get_all_config()
    logo = cfg.get('company_logo') or cfg.get('site_logo') or ''
    conn.close()
    all_paths = [r['p'] for r in rows if r['p']]
    if logo:
        all_paths.append(logo)
    # 支付自定义渠道图标（pay_methods_json 每项 icon=/uploads/xxx）
    try:
        _pm_raw = cfg.get('pay_methods_json')
        if _pm_raw:
            for _it in json.loads(_pm_raw) or []:
                _ic = (_it.get('icon') or '') if isinstance(_it, dict) else ''
                if _ic and _ic.startswith('/uploads/'):
                    all_paths.append(_ic)
    except Exception:
        pass
    for r in extra_rows:
        try:
            imgs = json.loads(r['p'])
            all_paths.extend(imgs)
        except Exception:
            pass
    for r in video_rows:
        p = r['p']
        if p and not p.startswith('http'):
            all_paths.append(p)
    # 产品描述 / 自定义页面中的富文本与 Markdown 图片（<img src=...>、![alt](...)、裸 /uploads/xxx）
    for r in list(desc_rows) + list(page_rows):
        d = r['d'] if 'd' in r.keys() else r['c']
        d = d or ''
        for src in re.findall(r'!\[[^\]]*\]\(([^)]+)\)', d):
            src = src.strip()
            if src.startswith('/uploads/'):
                all_paths.append(src)
        for src in re.findall(r'(?<![(\w])/uploads/[A-Za-z0-9._-]+', d):
            if src not in all_paths:
                all_paths.append(src)
    # 板块 content 中的图片/视频字段
    for s in get_sections(enabled_only=False):
        c = s.get('content') or {}
        if c.get('image'):
            all_paths.append(c['image'])
        if c.get('mp4') and not c.get('mp4', '').startswith('http'):
            all_paths.append(c['mp4'])
        for key in ('items', 'links'):
            for it in c.get(key) or []:
                if isinstance(it, dict) and it.get('image'):
                    all_paths.append(it['image'])
                if isinstance(it, dict) and it.get('logo'):
                    all_paths.append(it['logo'])
                if isinstance(it, dict) and it.get('photo'):
                    all_paths.append(it['photo'])
    return all_paths


def _preview_static_links(content, page_path, site_name, template_id):
    """Map this site's static anchors to the existing authenticated preview UI."""
    from html.parser import HTMLParser
    from urllib.parse import parse_qsl, unquote, urlencode
    base = _site_url_base()
    # A placeholder origin lets relative links work before a publish URL exists.
    root = (base or 'https://chatflow-preview.invalid').rstrip('/') + '/'
    current = urljoin(root, page_path)
    root_parts = urlsplit(root)

    def destination(href):
        if not href or href.startswith(('#', '?')):
            return None
        source = urlsplit(href)
        if not base and (source.scheme or source.netloc):
            return None
        target = urlsplit(urljoin(current, href))
        if (target.scheme.lower(), target.netloc.lower()) != (root_parts.scheme.lower(), root_parts.netloc.lower()):
            return None
        if not target.path.startswith(root_parts.path):
            return None
        relative = unquote(target.path[len(root_parts.path):])
        if '/' in relative:
            return None
        selector = []
        if relative in ('', 'index.html'):
            route = '/api/preview'
        elif relative == 'contact.html':
            route = '/api/preview_contact'
        elif relative == 'faq.html':
            route = '/api/preview_faq'
        elif re.fullmatch(r'product_\d+\.html', relative):
            route = '/api/preview_product'
            selector = [('pid', relative[8:-5])]
        elif re.fullmatch(r'page_.+\.html', relative):
            route = '/api/preview_page'
            selector = [('slug', relative[5:-5])]
        else:
            return None
        extras = [(key, value) for key, value in parse_qsl(target.query, keep_blank_values=True)
                  if key not in ('pid', 'slug', 'site_name', 'template')]
        query = urlencode(selector + [('site_name', site_name), ('template', template_id)] + extras)
        return route + '?' + query + ('#' + target.fragment if target.fragment else '')

    class Anchors(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.edits = []
            self.lines = [0] + [match.end() for match in re.finditer('\n', content)]

        def handle_starttag(self, tag, attrs):
            if tag != 'a':
                return
            href = next((value for name, value in attrs if name == 'href'), None)
            try:
                replacement = destination(href)
            except (ValueError, TypeError):
                return  # Leave malformed/custom anchors unchanged.
            if replacement is None:
                return
            raw = self.get_starttag_text()
            # Consume each complete attribute, so a title containing the text
            # "href=..." cannot be mistaken for the real href attribute.
            pattern = r'''\s+(?P<name>[^\s/>=]+)(?:\s*=\s*(?P<value>"[^"]*"|'[^']*'|[^\s>]+))?'''
            for match in re.finditer(pattern, raw):
                if match.group('name').lower() != 'href':
                    continue
                if match.group('value') is not None:
                    line, column = self.getpos()
                    offset = self.lines[line - 1] + column
                    self.edits.append((offset + match.start('value'), offset + match.end('value'),
                                       '"' + html.escape(replacement, quote=True) + '"'))
                break

        handle_startendtag = handle_starttag

    parser = Anchors()
    parser.feed(content)
    parser.close()
    for start, end, replacement in reversed(parser.edits):
        content = content[:start] + replacement + content[end:]
    return content


def _promotion_page(filename):
    import functools
    import inspect
    def decorate(function):
        signature = inspect.signature(function)
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            from promotion_tools import apply_promotions
            content = function(*args, **kwargs)
            if not content:
                return content
            try:
                settings = json.loads(get_config('growth_settings', '{}'))
            except ValueError:
                settings = {}
            path = filename(*args, **kwargs)
            content = apply_promotions(content, settings, page_url=_page_abs_url(path))
            arguments = signature.bind(*args, **kwargs)
            arguments.apply_defaults()
            if arguments.arguments.get('page') == 'preview':
                content = _preview_static_links(content, path,
                    arguments.arguments.get('site_name', 'My Export Site'),
                    arguments.arguments.get('template_id', 'business'))
            return content
        return wrapped
    return decorate


build_site_html = _promotion_page(lambda *a, **kw: 'index.html')(build_site_html)
build_contact_page_html = _promotion_page(lambda *a, **kw: 'contact.html')(build_contact_page_html)
build_faq_page_html = _promotion_page(lambda *a, **kw: 'faq.html')(build_faq_page_html)
build_product_page_html = _promotion_page(lambda *a, **kw: 'product_%s.html' % (a[0] if a else kw['product'])['id'])(build_product_page_html)
build_page_html = _promotion_page(lambda *a, **kw: 'page_%s.html' % (a[0] if a else kw['pg'])['slug'])(build_page_html)


def generate_site_files(site_name='My Export Site', template_id='business'):
    """清空并重建 output_site，生成首页 + 产品详情页 + 联系页 + 自定义页面 + sitemap/robots"""
    tpl = get_template(template_id)
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(os.path.join(OUTPUT_DIR, 'static', 'uploads'), exist_ok=True)

    with open(os.path.join(OUTPUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_site_html(site_name, 'static/uploads/', 'index', template_id))
    with open(os.path.join(OUTPUT_DIR, 'contact.html'), 'w', encoding='utf-8') as f:
        f.write(build_contact_page_html(site_name, 'static/uploads/', 'index', template_id))
    with open(os.path.join(OUTPUT_DIR, 'style.css'), 'w', encoding='utf-8') as f:
        f.write(build_css(template_id))

    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY sort_order ASC, id DESC').fetchall()
    conn.close()

    products = [catalog_product(p) for p in products]

    detail_count = 0
    for p in products:
        with open(os.path.join(OUTPUT_DIR, 'product_%d.html' % p['id']),
                  'w', encoding='utf-8') as f:
            f.write(build_product_page_html(p, site_name, 'static/uploads/', 'index', template_id))
        detail_count += 1

    # 自定义页面
    page_count = 0
    for pg in get_pages(enabled_only=True):
        with open(os.path.join(OUTPUT_DIR, 'page_%s.html' % pg['slug']),
                  'w', encoding='utf-8') as f:
            f.write(build_page_html(pg, site_name, 'static/uploads/', 'index', template_id))
        page_count += 1

    # FAQ 独立页：板块化 FAQ 启用或 AI GEO geo_faq 非空时生成（两者都无则不写 faq.html，
    # 并清理输出目录中可能残留的旧 faq.html，保证停用后前台不存在 FAQ 页）
    if _faq_section() or _geo_faq_pairs():
        with open(os.path.join(OUTPUT_DIR, 'faq.html'), 'w', encoding='utf-8') as f:
            f.write(build_faq_page_html(site_name, 'static/uploads/', 'index', template_id))
    else:
        _faq_out = os.path.join(OUTPUT_DIR, 'faq.html')
        if os.path.exists(_faq_out):
            try:
                os.remove(_faq_out)
            except OSError:
                pass

    # SEO / AI GEO 文件
    with open(os.path.join(OUTPUT_DIR, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write(_build_sitemap(site_name, products))
    with open(os.path.join(OUTPUT_DIR, 'robots.txt'), 'w', encoding='utf-8') as f:
        f.write(_build_robots())
    with open(os.path.join(OUTPUT_DIR, 'llms.txt'), 'w', encoding='utf-8') as f:
        f.write(_build_llms_txt(site_name, products))

    # 复制图片
    copied = 0
    seen = set()
    for p in _collect_image_paths():
        if not p:
            continue
        fname = os.path.basename(p)
        if fname in seen:
            continue
        seen.add(fname)
        src = os.path.join(UPLOAD_DIR, fname)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(OUTPUT_DIR, 'static', 'uploads', fname))
            copied += 1

    # 复制内置真实品牌 logo SVG（static/pay_icons/）随站点输出
    pay_src_dir = PAY_ICON_DIR
    if os.path.isdir(pay_src_dir):
        pay_dst_dir = os.path.join(OUTPUT_DIR, 'static', 'pay_icons')
        shutil.rmtree(pay_dst_dir, ignore_errors=True)
        shutil.copytree(pay_src_dir, pay_dst_dir)

    write_manifest(OUTPUT_DIR)
    return copied, detail_count, tpl['id'], tpl['name'], page_count


def _build_sitemap(site_name, products):
    """生成 sitemap.xml（含首页/联系页/产品页/自定义页）

    - 配置了 site_url 时输出绝对 loc + hreflang(self/x-default) + image:image（产品图）
    - 未配置 site_url 时退化为相对 URL（不含 image/hreflang），保证本地预览可用
    """
    now = datetime.now().strftime('%Y-%m-%d')
    base = _site_url_base()
    lang = get_config('language', 'en') or 'en'
    html_lang = I18N.get(lang, I18N['en']).get('html_lang', lang)
    pages = [('index.html', None), ('contact.html', None)]
    if _faq_section() or _geo_faq_pairs():
        pages.append(('faq.html', None))
    pages += [('page_%s.html' % pg['slug'], None) for pg in get_pages(enabled_only=True)]
    pages += [('product_%d.html' % p['id'], p) for p in products]

    ns = ('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
          'xmlns:xhtml="http://www.w3.org/1999/xhtml" '
          'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"')
    items = []
    for u, p in pages:
        if not base: continue
        loc = _page_abs_url(u)
        seg = ['<url><loc>%s</loc>' % esc(loc)]
        if base:
            for hl in [html_lang, 'x-default']:
                seg.append('<xhtml:link rel="alternate" hreflang="%s" href="%s"/>'
                           % (esc(hl), esc(_page_abs_url(u))))
        if base and p is not None:
            imgs = product_images(p)
            if imgs:
                src = _site_img_url(imgs[0], 'static/uploads/')
                img_abs = urljoin(base + '/', src)
                seg.append('<image:image><image:loc>%s</image:loc>'
                           '<image:title>%s</image:title></image:image>'
                           % (esc(img_abs), esc(p['name'] or site_name)))
        seg.append('</url>')
        items.append(''.join(seg))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset %s>%s</urlset>\n' % (ns, ''.join(items)))


def _build_robots():
    # Search discovery and model training are independent choices.
    base = _site_url_base()
    search = 'Allow: /' if _geo_ai_enabled() else 'Disallow: /'
    training = 'Allow: /' if get_config('geo_training_enabled', '0') == '1' else 'Disallow: /'
    result = 'User-agent: *\nAllow: /\nDisallow: /admin\n\n'
    result += 'User-agent: OAI-SearchBot\n' + search + '\n\n'
    result += 'User-agent: GPTBot\n' + training + '\n\n'
    if base: result += 'Sitemap: ' + base + '/sitemap.xml\n'
    return result

def _build_llms_txt(site_name='My Export Site', products=None):
    """生成 llms.txt：LLM/AI 引擎友好站点说明（站点名/简介/卖点/页面与产品链接）

    按站点默认语言输出；site_url 未配置时使用相对文件名并在注释中提醒。
    由 generate_site_files 每次"一键生成"同步刷新。
    """
    lang = get_config('language', 'en') or 'en'
    L = I18N.get(lang, I18N['en'])
    seo = seo_site()
    comp = company_info()
    brand = comp.get('name') or site_name
    base = _site_url_base()
    def abs_url(u):
        return _page_abs_url(u) if base else u

    # P6：llms.txt 小节标题/注释按当前语言输出（默认保留既有中英文案，zh-Hant 输出繁体）
    _LT = {
        'intro': {'zh-Hant': '> llms.txt 供大語言模型與 AI 搜索讀取。'},
        'rel': {'zh-Hant': '> 提示：尚未配置「站點正式網址 (site_url)」，以下連結為相對路徑；配置後將自動升級為完整網址。'},
        'brand': {'zh-Hant': '## 站點簡介 (Brand Summary)'},
        'points': {'zh-Hant': '## 核心賣點 (Selling Points)'},
        'mkts': {'zh-Hant': '## 目標市場 (Target Markets)'},
        'certs': {'zh-Hant': '## 認證資質 (Certifications)'},
        'caps': {'zh-Hant': '## 服務能力 (Service Capabilities)'},
        'faq': {'zh-Hant': '## 常見問題 (FAQ)'},
        'pages': {'zh-Hant': '## 主要頁面'},
        'prodlist': {'zh-Hant': '## 產品列表 (%d)'},
        'multilang': {'zh-Hant': '## 多語言 (Multi-language)'},
    }
    def _lt(key, default):
        return _LT.get(key, {}).get(lang, default)

    summary = (seo.get('brand_summary') or '').strip() or (seo.get('description') or '').strip()
    if not summary:
        summary = '%s - %s' % (brand, L.get('site_suffix', 'export site'))

    points = _selling_points_list()
    if not points:
        points = [t(lang, 'trust_factory'), t(lang, 'trust_fast'),
                  t(lang, 'trust_quality'), t(lang, 'trust_24h')]
    # P2：AI GEO 精致化小节数据（目标市场 / 认证 / 服务能力 / FAQ 问题清单）
    geo_mkts = seo.get('target_markets') or []
    geo_certs = seo.get('certifications') or []
    geo_caps = seo.get('service_capabilities') or []
    geo_faqs = seo.get('faq') or []

    lines = []
    lines.append('# %s' % brand)
    lines.append('')
    lines.append(_lt('intro', '> llms.txt 供大语言模型与 AI 搜索读取。'))
    if not base:
        lines.append(_lt('rel', '> 提示：尚未配置"站点正式网址(site_url)"，以下链接为相对路径；'
                     '配置后将自动升级为完整网址。'))
    lines.append('')
    lines.append(_lt('brand', '## 站点简介 (Brand Summary)'))
    lines.append(summary)
    lines.append('')
    lines.append(_lt('points', '## 核心卖点 (Selling Points)'))
    lines.append('')
    for pt in points:
        lines.append('- %s' % pt)
    lines.append('')
    # P2：AI GEO 精致化（D4 语义：geo_faq 的 FAQ 问题列入 FAQ 小节，不重复板块内容）
    if geo_mkts:
        lines.append(_lt('mkts', '## 目标市场 (Target Markets)'))
        lines.append('')
        for m in geo_mkts:
            lines.append('- %s' % m)
        lines.append('')
    if geo_certs:
        lines.append(_lt('certs', '## 认证资质 (Certifications)'))
        lines.append('')
        for c in geo_certs:
            lines.append('- %s' % c)
        lines.append('')
    if geo_caps:
        lines.append(_lt('caps', '## 服务能力 (Service Capabilities)'))
        lines.append('')
        for c in geo_caps:
            lines.append('- %s' % c)
        lines.append('')
    if geo_faqs:
        # llms.txt 只列问题（FAQPage JSON-LD 携带完整问答），控制文件长度
        lines.append(_lt('faq', '## 常见问题 (FAQ)'))
        lines.append('')
        for q, _a in geo_faqs:
            lines.append('- Q: %s' % q)
        lines.append('')
    lines.append(_lt('pages', '## 主要页面'))
    lines.append('')
    lines.append('- Home: %s' % abs_url('index.html'))
    lines.append('- Contact: %s' % abs_url('contact.html'))
    faq_sec = _faq_section()
    if faq_sec or geo_faqs:
        lines.append('- %s: %s' % (((faq_sec or {}).get('title') or '').strip() or L.get('sec_faq', 'FAQ'),
                                   abs_url('faq.html')))
    for pg in get_pages(enabled_only=True):
        lines.append('- %s: %s' % (pg['title'], abs_url('page_%s.html' % pg['slug'])))
    lines.append('')
    lines.append(_lt('prodlist', '## 产品列表 (%d)') % (len(products or []),))
    lines.append('')
    for p in (products or []):
        lines.append('- %s: %s' % (p['name'], abs_url('product_%d.html' % p['id'])))
    lines.append('')
    lines.append(_lt('multilang', '## 多语言 (Multi-language)'))
    lines.append('')
    lines.append('- Default language: %s (%s)' % (I18N.get(lang, I18N['en']).get('html_lang', lang), lang))
    # 本站以「当前默认语言」单语言静态发布，仅声明实际存在的语言版本；
    # 后台切换语言后此文件随"一键生成"同步刷新，hreflang 才会跟着更新
    lines.append('- Published language versions: %s' % I18N.get(lang, I18N['en']).get('html_lang', lang))
    return '\n'.join(lines) + '\n'


def base_js(lang='zh'):
    """站点基础 JS：轮播 / 询盘提交等。纯静态站无后端时提交失败，直接展示联系方式。
    文案按当前站点语言输出（zh=简体 / zh-Hant=繁体 / 其它=en），避免繁体站出现简体提示。"""
    if lang == 'zh-Hant':
        _js_fail_prefix = '提交失敗，請直接聯繫我們：'
        _js_fail_retry = '提交失敗，請稍後重試，或透過頁面底部的聯絡方式聯絡我們。'
    elif lang == 'zh':
        _js_fail_prefix = '提交失败，请直接联系我们：'
        _js_fail_retry = '提交失败，请稍后重试，或通过页面底部的联系方式联系我们。'
    else:
        _js_fail_prefix = 'Submission failed. Please contact us directly:'
        _js_fail_retry = 'Submission failed. Please try again later or contact us via the contact info at the bottom of the page.'
    _conn = get_db()
    _rows = _conn.execute('SELECT contact_type, contact_value FROM contacts ORDER BY id ASC').fetchall()
    _conn.close()
    _info = {}
    for _r in _rows:
        _info.setdefault(str(_r['contact_type']), str(_r['contact_value'] or ''))
    contact_js = 'var CONTACT_INFO = %s;\n' % json.dumps(_info, ensure_ascii=False)
    return '<script>\n' + contact_js + '''
var idx = 0;
var slides = document.querySelectorAll('.banner-slider .slide');
function nextSlide() {
  if (!slides.length) return;
  slides[idx].classList.remove('active');
  idx = (idx + 1) % slides.length;
  slides[idx].classList.add('active');
}
if (slides.length > 1) setInterval(nextSlide, 3500);
function copyText(t) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(t).then(function() { alert('Copied: ' + t); });
  } else {
    prompt('Please copy manually:', t);
  }
}
function setMainImg(src, el) {
  var main = document.getElementById('mainImg');
  if (main) main.src = src;
  var thumbs = document.querySelectorAll('.thumb-item');
  for (var i = 0; i < thumbs.length; i++) thumbs[i].classList.remove('active');
  if (el) el.classList.add('active');
}
/* 产品卡片 hover 多图切换（有第二张图时显示第二张，移出恢复主图） */
document.querySelectorAll('.product-img').forEach(function(a) {
  var imgs = a.querySelectorAll('.p-img');
  if (imgs.length < 2) return;
  a.addEventListener('mouseenter', function() {
    imgs[0].style.display = 'none';
    imgs[1].style.display = 'block';
  });
  a.addEventListener('mouseleave', function() {
    imgs[1].style.display = 'none';
    imgs[0].style.display = 'block';
  });
});
/* 京东式详情页 Tab 切换 */
document.querySelectorAll('.jd-tab').forEach(function(btn) {
  btn.addEventListener('click', function() {
    var tab = btn.dataset.tab;
    document.querySelectorAll('.jd-tab').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    document.querySelectorAll('.jd-tab-pane').forEach(function(pn) {
      pn.classList.toggle('active', pn.dataset.pane === tab);
    });
  });
});
/* FAQ 手风琴 */
document.querySelectorAll('.faq-q').forEach(function(q) {
  q.addEventListener('click', function() {
    var item = q.parentElement;
    var open = item.classList.contains('open');
    document.querySelectorAll('.faq-item').forEach(function(i) { i.classList.remove('open'); });
    if (!open) item.classList.add('open');
  });
});
/* 主图点击放大灯箱 */
var lightbox = null;
document.addEventListener('click', function(e) {
  if (e.target && e.target.id === 'mainImg') {
    if (!lightbox) {
      lightbox = document.createElement('div');
      lightbox.className = 'lightbox';
      lightbox.innerHTML = '<img src="" alt="product image zoom">';
      lightbox.addEventListener('click', function() { lightbox.classList.remove('show'); });
      document.body.appendChild(lightbox);
    }
    lightbox.querySelector('img').src = e.target.src;
    lightbox.classList.add('show');
  }
});
/* GDPR/CCPA Cookie 同意横幅：同意后本地存储不再显示 */
function cookieConsent() { return localStorage.getItem('cookie_consent'); }
function showCookieBanner() {
  var b = document.getElementById('cookieBanner');
  if (b && !cookieConsent()) b.classList.add('show');
}
function acceptCookies() {
  localStorage.setItem('cookie_consent', 'accepted');
  var b = document.getElementById('cookieBanner');
  if (b) b.classList.remove('show');
}
function declineCookies() {
  localStorage.setItem('cookie_consent', 'declined');
  var b = document.getElementById('cookieBanner');
  if (b) b.classList.remove('show');
}
document.addEventListener('DOMContentLoaded', showCookieBanner);
/* 回到顶部浮动按钮（出现在左下角） */
(function () {
  var bt = document.getElementById('backTop');
  if (!bt) return;
  function update() {
    if (window.scrollY > 300) {
      bt.style.display = 'block';
      bt.style.opacity = '1';
    } else {
      bt.style.display = 'none';
      bt.style.opacity = '0';
    }
  }
  window.addEventListener('scroll', update, { passive: true });
  bt.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
  update();
})();
/* 无询盘表单（已改为直接联系方式），保留联系方式兜底函数 */
function contactVal(keys) {
  for (var i = 0; i < keys.length; i++) { if (CONTACT_INFO[keys[i]]) return CONTACT_INFO[keys[i]]; }
  return '';
}
function showContactFallback(msg) {
  var lines = [];
  var ph = contactVal(['电话', 'phone', 'tel', 'Phone']);
  var wa = contactVal(['WhatsApp', 'whatsapp', 'WhatsApp 号码', 'WhatsApp号码']);
  var wx = contactVal(['微信', 'wechat', 'WeChat']);
  var em = contactVal(['Email', 'email', '邮箱', 'E-mail', 'E-Mail']);
  if (ph) lines.push('📞 ' + ph);
  if (wa) lines.push('WhatsApp: ' + wa);
  if (wx) lines.push('微信: ' + wx);
  if (em) lines.push('✉️ ' + em);
  if (msg) {
    if (lines.length) {
      msg.innerHTML = '⚠️ ' + _js_fail_prefix + '<br>' + lines.join('<br>');
    } else {
      msg.textContent = '⚠️ ' + _js_fail_retry;
    }
    msg.classList.add('err');
  }
}
/* WhatsApp 浮动按钮：从联系方式读取号码，无号码隐藏；点击拉起 wa.me */
(function () {
  var num = contactVal(['WhatsApp', 'whatsapp', 'WhatsApp 号码', 'WhatsApp号码']);
  var waFloat = document.getElementById('waFloat');
  var waBtn = document.getElementById('waFloatBtn');
  if (!num || !waFloat || !waBtn) return;
  var clean = String(num).replace(/[^0-9]/g, '');
  if (!clean) return;
  waFloat.style.display = '';
  waBtn.href = 'https://wa.me/' + clean + '?text=' + encodeURIComponent('Hello, I am interested in your products.');
  /* 延迟显示气泡，模拟未读式在线咨询提示 */
  setTimeout(function () {
    var b = waFloat.querySelector('.wa-bubble');
    if (b) b.classList.add('show');
  }, 2500);
  waBtn.addEventListener('click', function () {
    var b = waFloat.querySelector('.wa-bubble');
    if (b) b.classList.remove('show');
  });
})();
</script>'''
