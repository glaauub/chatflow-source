# -*- coding: utf-8 -*-
"""ChatFLOW 内置「原始模板 / 示例内容包」—— HLURU 真实演示站。

本模板开箱即还原 https://www.chatflow2026.top 这个真实的 HLURU 站：
- 真实品牌：HLURU（深圳工厂，2010 起）
- 真实 logo：hluru-logo-real.png（取自 cn.hluru.com 官网）
- 真实底部：四列 footer（Brand / Shop / Wholesale / Visit），含成立年份、厂房面积、认证、保修
- 真实产品/分类/材质/系列、真实联系方式、真实横幅轮播图
- 推广工具箱（灰帽隐藏关键词/链接）与黑帽隐藏链接池（spider_pool）

- 新装软件首次运行（init_db）会自动加载本模板，让客户打开即见完整 HLURU 站点。
- 后台「模板与示例」提供：加载示例模板 / 一键清空示例内容。
- 图片资源在 data/preset_assets/，加载时拷贝到 static/uploads/。
- 客户随时可「一键清空」回到空白框架，再填入自己的内容。
"""
import json
import os
import shutil
import sqlite3

from runtime_paths import bundle_path, data_path

PRESET_VERSION = "2.0"

# ---- 内置图片资源文件名（data/preset_assets/ 下）----
LOGO_FILE = "hluru-logo-real.png"
BANNER_FILES = [
    "hluru-banner-1.png",
    "hluru-banner-2.png",
    "hluru-banner-3.png",
    "hluru-banner-4.png",
    "hluru-banner-5.png",
]
PRODUCT_FILES = [
    "hluru-real-01.jpg",
    "hluru-real-02.jpg",
    "hluru-real-03.jpg",
    "hluru-real-04.jpg",
    "hluru-real-05.jpg",
    "hluru-real-06.jpg",
    "hluru-real-07.jpg",
    "hluru-real-08.jpg",
    "hluru-real-09.jpg",
    "hluru-real-10.jpg",
    "hluru-real-11.jpg",
    "hluru-real-12.jpg",
    "hluru-real-13.jpg",
    "hluru-real-14.jpg",
    "hluru-real-15.jpg",
    "hluru-real-16.jpg",
    "hluru-real-17.jpg",
    "hluru-real-18.jpg",
    "hluru-real-19.jpg",
    "hluru-real-20.jpg",
    "hluru-real-21.jpg",
    "hluru-real-22.jpg",
    "hluru-real-23.jpg",
    "hluru-real-24.jpg",
    "hluru-real-25.jpg",
    "hluru-real-26.jpg",
    "hluru-real-27.jpg",
    "hluru-real-28.jpg",
    "hluru-real-29.jpg",
    "hluru-real-30.jpg",
    "hluru-real-31.jpg",
    "hluru-real-32.jpg",
    "hluru-real-33.jpg",
    "hluru-real-34.jpg",
    "hluru-real-35.jpg",
    "hluru-real-36.jpg",
    "hluru-real-37.jpg",
    "hluru-real-38.jpg",
    "hluru-real-39.jpg",
    "hluru-real-40.jpg",
    "hluru-real-41.jpg",
    "hluru-real-42.jpg",
    "hluru-real-43.jpg",
    "hluru-real-44.jpg",
    "hluru-real-45.jpg",
    "hluru-real-46.jpg",
    "hluru-real-47.jpg",
    "hluru-real-48.jpg",
]
CERT_FILES = [
    "starter-cert-1.png",
    "starter-cert-2.png",
    "starter-cert-3.png",
    "starter-cert-4.png",
]

SITE_URL = "https://www.chatflow2026.top"
EMAIL = "pupastrhynerogn@hotmail.com"
WHATSAPP = "+852 4659 3583"


# ===================== 站点配置（所有 SEO / GEO / 公司 / 支付 / 域名）=====================
STARTER_SITE_CONFIG = {
    "site_name": "HLURU",
    "site_url": SITE_URL,
    "language": "en",
    "site_template": "modern",
    "site_layout": "classic",
    "cookie_enabled": "1",
    "analytics_code": "",
    "seo_experiments_enabled": "1",
    # SEO
    "seo_site_title": "HLURU - Professional Manufacturer & Supplier",
    "seo_site_description": "Healing Instruments from a Single Workshop Since 2010 \u2014 Steel Tongue Drums, Handpans, Kalimbas, Harps, Cajons and Wind Chimes, hand-tuned in our Shenzhen factory and shipped wholesale to 60+ countries.",
    "seo_site_keywords": "steel tongue drum, handpan, kalimba, lyre harp, cajon, wind chime, OEM instruments, wholesale instruments, musical instrument manufacturer",
    "seo_author": "HLURU",
    "seo_robots": "index,follow",
    "seo_hidden_keywords": "",
    # GEO / AI 搜索可见性
    "geo_ai_enabled": "1",
    "geo_brand_summary": "HLURU is a direct-from-factory maker of hand-tuned healing instruments in Shenzhen, China since 2010 \u2014 steel tongue drums, handpans, kalimbas, lyre harps, cajons and wind chimes, shipped wholesale to 60+ countries.",
    "geo_selling_points": "Direct from factory since 2010\nHand-tuned by master craftsmen\nOEM / ODM custom builds with your logo\nShips wholesale to 60+ countries\nCE / RoHS / REACH certified",
    "geo_service_capabilities": "OEM / ODM with custom logo, scale and finish\nSample and small trial orders accepted\nLead time 15 to 30 days depending on model and quantity\nFull documentation and after-sales support",
    "geo_target_markets": "Europe\nNorth America\nJapan and South Korea\nSoutheast Asia\nAustralia and New Zealand\nMiddle East",
    "geo_certifications": "CE marking for the EU market\nRoHS compliance\nREACH compliance\n12-month warranty on all products",
    "geo_address": "Shenzhen, Guangdong, China",
    "geo_region": "Global",
    "geo_faq": json.dumps([
        {"q": "Are you the manufacturer or a trading company?",
         "a": "We are the direct manufacturer. HLURU runs its own workshop in Shenzhen and every instrument is hand-tuned and quality-checked in-house \u2014 no agents, no middlemen."},
        {"q": "Can you customize products?",
         "a": "Yes. OEM and ODM services are available. Send us your logo, scale or specification and our engineers will reply within 24 hours."},
        {"q": "What is your minimum order quantity?",
         "a": "Our MOQ is flexible. Samples and small trial orders are welcome; final details are confirmed per enquiry."},
        {"q": "What about delivery time?",
         "a": "Stock items ship in 3 to 7 days. Custom production normally takes 15 to 30 days after confirmation."},
        {"q": "Do you provide after-sales service?",
         "a": "Yes. Our team offers technical support and timely after-sales service; any issue is handled promptly."},
    ], ensure_ascii=False),
    # 公司信息（驱动 header / footer / 联系页）
    "company_name": "HLURU",
    "site_logo": "/uploads/" + LOGO_FILE,
    "company_logo": "/uploads/" + LOGO_FILE,
    "company_brief": "Hand-tuned steel tongue drums, handpans, kalimbas, lyre harps, cajons and aluminium wind chimes. Direct from our Shenzhen workshop since 2010.",
    "company_address": "Shenzhen, China",
    "company_phone": "",
    "company_email": EMAIL,
    "company_whatsapp": WHATSAPP,
    "company_founded": "2010",
    "company_size": "50-200 employees",
    "company_industry": "Musical Instrument Manufacturing",
    "company_products": "Steel Tongue Drums, Handpans, Kalimbas, Lyre Harps, Cajons, Wind Chimes",
    "company_workshop_area": "4,200 m\u00b2",
    "company_certifications": "CE / RoHS / REACH",
    "company_warranty": "12-month warranty",
    "footer_copyright": "\u00a9 2026 HLURU Wholesale Instruments. All Rights Reserved.",
    "footer_icp": "",
    # 导航 mega-menu 数据（By material / By series）
    "product_materials": "304 stainless steel|Copper-steel alloy|Carbon steel|Aluminium alloy|Acrylic|Solid wood",
    "product_series": "Triangle series|Lotus series|Travel drum|Mini series|Flagship model|Butterfly drum",
    # 支付
    "pay_methods_json": json.dumps([
        {"type": "paypal", "value": EMAIL, "name": "", "icon": ""},
        {"type": "stripe", "value": "https://buy.stripe.com/", "name": "", "icon": ""},
        {"type": "custom", "value": "", "name": "", "icon": ""},
    ], ensure_ascii=False),
    "paypal_email": EMAIL,
    "stripe_link": "https://buy.stripe.com/",
    "custom_link": "",
    "custom_label": "Buy Now",
}


# ===================== 推广工具箱（灰帽填满示例）=====================
STARTER_GROWTH_SETTINGS = {
    "hidden_keywords_enabled": True,
    "hidden_keywords": [
        "hluru", "hluru steel tongue drum", "hluru handpan", "hluru kalimba",
        "steel tongue drum", "handpan", "kalimba", "lyre harp", "cajon", "wind chime",
        "wholesale instruments", "custom logo instruments", "musical instrument manufacturer",
        "instrument manufacturer", "private label instruments", "buy musical instruments",
        "instrument wholesale", "factory price instruments", "handmade instruments",
        "sound healing instrument", "meditation instrument", "music therapy instrument",
        "OEM kalimba", "OEM handpan", "OEM tongue drum", "432 hz drum", "528 hz drum",
        "China instrument factory", "dropship musical instrument", "hand-tuned drum",
        "tongue drum factory", "handpan manufacturer", "kalimba supplier",
    ],
    "hidden_links_enabled": True,
    "hidden_links": [
        {"name": "Visit Our Site", "url": SITE_URL + "/", "rel": "nofollow"},
        {"name": "Shop Products", "url": SITE_URL + "/products/", "rel": "nofollow"},
        {"name": "About the Workshop", "url": SITE_URL + "/page_about.html", "rel": "nofollow"},
        {"name": "Wholesale Inquiry", "url": SITE_URL + "/contact/", "rel": "nofollow"},
        {"name": "OEM / ODM Service", "url": SITE_URL + "/page_about.html", "rel": "nofollow"},
    ],
    "internal_links_enabled": True,
    "internal_links": [
        {"keyword": "steel tongue drum", "url": "/products/"},
        {"keyword": "handpan", "url": "/products/"},
        {"keyword": "OEM service", "url": "/page_about.html"},
        {"keyword": "sound healing", "url": "/"},
        {"keyword": "contact us", "url": "/contact/"},
        {"keyword": "warranty", "url": "/faq/"},
    ],
    "max_links_per_page": 3,
}


# ===================== 板块框架 + 填充内容（9 大板块）=====================
STARTER_SECTIONS = [
    {"section_type": "hero", "title": "Hero Banner", "enabled": 1, "sort_order": 10, "content": {}},
    {"section_type": "products", "title": "Our Products", "enabled": 1, "sort_order": 20,
     "content": {"limit": 0, "subtitle": "Hand-tuned steel tongue drums, handpans, kalimbas, lyre harps, cajons and wind chimes \u2014 crafted in our Shenzhen workshop since 2010."}},
    {"section_type": "why_us", "title": "Why Choose HLURU", "enabled": 1, "sort_order": 30,
     "content": {"items": [
         {"icon": "🏬", "title": "Direct from factory", "text": "Workshop-direct pricing on every instrument \u2014 no agents, no middlemen, no export markup."},
         {"icon": "🎵", "title": "Hand-tuned quality", "text": "Each piece is tuned and inspected by hand in our Shenzhen workshop before it leaves the factory."},
         {"icon": "🤝", "title": "OEM / ODM", "text": "Custom logo, scale, material and packaging with full documentation and support."},
         {"icon": "🌍", "title": "Global shipping", "text": "Shipped wholesale to 60+ countries with flexible sample and small trial orders."},
     ]}},
    {"section_type": "stats", "title": "HLURU by the Numbers", "enabled": 1, "sort_order": 40,
     "content": {"items": [
         {"value": "15+", "label": "Years in business (since 2010)"},
         {"value": "60+", "label": "Countries we ship to"},
         {"value": "500+", "label": "Product models in current line-up"},
         {"value": "24h", "label": "Average inquiry response"},
     ]}},
    {"section_type": "certificates", "title": "Certifications & Quality Standards", "enabled": 1, "sort_order": 50,
     "content": {"items": [
         {"title": "CE Marking", "text": "Compliance with EU safety, health and environmental requirements.", "image": "/uploads/" + CERT_FILES[0]},
         {"title": "RoHS Compliance", "text": "Restriction of hazardous substances in all our products.", "image": "/uploads/" + CERT_FILES[1]},
         {"title": "REACH Compliance", "text": "Registered, evaluated and authorised chemicals for the EU market.", "image": "/uploads/" + CERT_FILES[2]},
         {"title": "12-Month Warranty", "text": "Every shipment includes a 12-month warranty and after-sales support.", "image": "/uploads/" + CERT_FILES[3]},
     ]}},
    {"section_type": "news", "title": "News & Industry Updates", "enabled": 1, "sort_order": 60,
     "content": {"items": [
         {"title": "432 Hz Tuning: Why More Studios Choose It", "date": "2026-03-12",
          "text": "A look at how 432 Hz tuning has gained traction in sound-bath and yoga settings, and how we support custom scales."},
         {"title": "Behind the Workshop: How a Tongue Drum Is Made", "date": "2026-02-20",
          "text": "From sheet metal to hand tuning \u2014 a short walkthrough of our in-house production process."},
         {"title": "New EU Shipment Line Opens for Wholesale Buyers", "date": "2026-01-15",
          "text": "Faster lead times and consolidated pallets for distributors across Europe and the UK."},
     ]}},
    {"section_type": "faq", "title": "FAQ", "enabled": 1, "sort_order": 70,
     "content": {"items": [
         {"q": "Are you the manufacturer or a trading company?",
          "a": "We are the direct manufacturer. HLURU runs its own workshop in Shenzhen and every instrument is hand-tuned and quality-checked in-house."},
         {"q": "Can you customize products?",
          "a": "Yes. OEM and ODM services are available. Send us your logo, scale or specification and our engineers will reply within 24 hours."},
         {"q": "What is your minimum order quantity?",
          "a": "Our MOQ is flexible. Samples and small trial orders are welcome; final details are confirmed per enquiry."},
         {"q": "What about delivery time?",
          "a": "Stock items ship in 3 to 7 days. Custom production normally takes 15 to 30 days after confirmation."},
         {"q": "How do you control quality?",
          "a": "We run a complete QC system from raw materials to finished products, with inspection reports available on request."},
         {"q": "Do you provide after-sales service?",
          "a": "Yes. Our team offers technical support and timely after-sales service for every order."},
     ]}},
    {"section_type": "cta", "title": "Get a Wholesale Quote in 24 Hours", "enabled": 1, "sort_order": 80,
     "content": {"title": "Ready to Source From the Maker?",
                 "subtitle": "Send your store link or wholesale requirements to " + EMAIL + " \u2014 we reply with a tiered price list.",
                 "btn_text": "Get a Quote", "btn_url": "mailto:" + EMAIL}},
    {"section_type": "contacts", "title": "Contact Us", "enabled": 1, "sort_order": 90, "content": {}},
    # 黑帽示例：隐藏链接池（display:none 的蜘蛛池）。仅在 seo_experiments_enabled=1 时输出，
    # 一键清空会清空其内容与开关，回到空白框架。
    {"section_type": "spider_pool", "title": "高级试验：隐藏链接（黑帽示例）", "enabled": 1, "sort_order": 95,
     "content": {"links": [
         {"name": "Steel Tongue Drum Manufacturer", "url": SITE_URL + "/"},
         {"name": "Wholesale Instruments Factory", "url": SITE_URL + "/products/"},
         {"name": "OEM / ODM Instrument Supplier", "url": SITE_URL + "/page_about.html"},
         {"name": "Handpan Factory Price", "url": SITE_URL + "/products/"},
         {"name": "Kalimba Wholesale", "url": SITE_URL + "/products/"},
     ]}},
]


# ===================== 横幅轮播（真实 HLURU 横幅）=====================
STARTER_BANNERS = [{"image_path": "/uploads/" + fn, "sort_order": i}
                   for i, fn in enumerate(BANNER_FILES)]


# ===================== 产品（真实 HLURU 产品名 + 占位图）=====================
def _p(name, price, spec, sku, model, stock, category, description, img_idx):
    img = "/uploads/" + PRODUCT_FILES[img_idx % len(PRODUCT_FILES)]
    return {
        "name": name, "price": price, "spec": spec, "img": img,
        "sku": sku, "model": model, "stock": stock, "category": category,
        "description": description,
        "meta_title": name, "meta_description": description[:140],
    }


# ===================== 产品（真实 HLURU 产品 + 真实产品图）=====================
STARTER_PRODUCTS = [
    _p(
        'Hluru 11 Notes 10 inch 304 Stainless Steel D Major Tongue Drum - Triangle Series',
        'USD $29.99',
        '11 notes / 10 inch / D Major',
        'HL-TD-001',
        'TD01',
        97,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 11 notes / 10 inch / D Major. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        0,
    ),
    _p(
        'Hluru 13 Notes 12 inch 304 Stainless Steel C Major Tongue Drum - Triangle Series',
        'USD $39.99',
        '13 notes / 12 inch / C Major',
        'HL-TD-002',
        'TD02',
        134,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 13 notes / 12 inch / C Major. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        1,
    ),
    _p(
        'Hluru 15 Notes 14 inch 304 Stainless Steel D Major Tongue Drum - Triangle Series',
        'USD $49.99',
        '15 notes / 14 inch / D Major',
        'HL-TD-003',
        'TD03',
        171,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 15 notes / 14 inch / D Major. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        2,
    ),
    _p(
        'Hluru 15 Strings Ostry Japonica Harp for Music Therapy',
        'USD $79.99',
        'Lyre harps',
        'HL-LH-004',
        'LH01',
        208,
        'Lyre harps',
        'Hluru 15-String Ostry Japonica Harp: Ideal for Music Therapy, Meditation & Yoga. Handcrafted from premium wood, it delivers rich, gentle tones to soothe emotions. Beginner-friendly, portable, and elegant—perfect for wellness routines & thoughtful gifting.',
        3,
    ),
    _p(
        'Hluru 19 Strings Large Harp instruments with Bag and Tuning Wrench - Paulownia wood',
        'USD $89.99',
        'paulownia',
        'HL-LH-005',
        'LH02',
        245,
        'Lyre harps',
        'Hluru 19-String Large Harp: Crafted from Paulownia Wood, with Included Bag & Tuning Wrench. Rich, resonant tones ideal for music practice & relaxation. Sturdy, portable design—beginner-friendly for versatile musical exploration & easy gifting.',
        4,
    ),
    _p(
        'Hluru 21 Keys C Major Kalimba for Early Childhood Education - Double Layer of Wah-Wah',
        'USD $24.99',
        'Kalimbas',
        'HL-KB-006',
        'KB01',
        82,
        'Kalimbas',
        "Hluru 21-Key C Major Kalimba: Perfect for Early Childhood Education with Double-Layer Wah-Wah. Bright tones spark kids' musical interest—easy to play, child-friendly, and ideal for music classes or parent-child time. Durable, lightweight, and great for gifting young learners.",
        5,
    ),
    _p(
        'Hluru 49CN Black & White Ebony White Tiger Cajon',
        'USD $79.99',
        'Cajons',
        'HL-CJ-007',
        'CJ01',
        119,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — Cajons. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        6,
    ),
    _p(
        'Hluru 49CN Spotted Maple White Tiger Cajon',
        'USD $89.99',
        'Cajons',
        'HL-CJ-008',
        'CJ02',
        156,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — Cajons. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        7,
    ),
    _p(
        'Hluru 49CN Zebrawood White Tiger Cajon',
        'USD $99.99',
        'Cajons',
        'HL-CJ-009',
        'CJ03',
        193,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — Cajons. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        8,
    ),
    _p(
        'Hluru 7 Strings Sapele Harp For Meditation',
        'USD $99.99',
        'sapele',
        'HL-LH-010',
        'LH03',
        230,
        'Lyre harps',
        'Hluru 7-String Sapele Harp for Meditation & Relaxation. Handcrafted from premium sapele wood, it delivers warm, resonant tones to calm mind and soul. Perfect for beginners—portable, easy to play, ideal for yoga, sound therapy, and deep mindfulness sessions. Elevate your wellness with authentic acoustic tranquility.',
        9,
    ),
    _p(
        'Hluru 8-Notes 4" Mini Steel Tongue Drum',
        'USD $58.99',
        '4 inch',
        'HL-TD-011',
        'TD04',
        67,
        'Steel tongue drums',
        'Compact Carbon Steel Design. Portable, easy to play with clear tones ideal for beginners, travel casual music fun. Perfect for gifting on-the-go musical exploration.',
        10,
    ),
    _p(
        'Hluru 8 Notes 5 inch 304 Stainless Steel Flower of Life Tongue Drum',
        'USD $72.99',
        '8 notes / 5 inch',
        'HL-TD-012',
        'TD05',
        104,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 8 notes / 5 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        11,
    ),
    _p(
        'HLURU Black Walnut Chromatic Kalimba 38 Keys C Major Kalimba - A Grade Tree of Life',
        'USD $29.99',
        '38 keys / C Major',
        'HL-KB-013',
        'KB02',
        141,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 38 keys / C Major. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        12,
    ),
    _p(
        'Hluru Cherry Wood 5 keys Mini Kalimba For MusicTherapy - Perfection Season Series',
        'USD $39.99',
        'cherry wood / cherry',
        'HL-KB-014',
        'KB03',
        178,
        'Kalimbas',
        '5-Key Cherry Wood Mini Kalimba for Music Therapy. Gentle, soothing tones enhance therapeutic sessions & relaxation. Compact, easy to play with natural wood texture—ideal for healers & mindful gifting.',
        13,
    ),
    _p(
        'Hluru Cherry Wood 9 keys Kalimba For Meditation - Perfection Season Series',
        'USD $45.99',
        'cherry wood / cherry',
        'HL-KB-015',
        'KB04',
        215,
        'Kalimbas',
        '9-Key Cherry Wood Kalimba for Meditation. Warm, serene tones enhance mindful sessions & relaxation. Easy to play, portable design with natural cherry wood texture—ideal for meditators & thoughtful gifting.',
        14,
    ),
    _p(
        'Hluru ChineseAsh Cajón, 48CN Beginner Model - Vermilion Bird',
        'USD $109.99',
        'Cajons',
        'HL-CJ-016',
        'CJ04',
        252,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — Cajons. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        15,
    ),
    _p(
        'Hluru ChineseAsh Cajón 42CN Teen Series - Vermilion Bird',
        'USD $119.99',
        'Cajons',
        'HL-CJ-017',
        'CJ05',
        89,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — Cajons. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        16,
    ),
    _p(
        'Hluru Micro-alloy Steel and Premium Wood Tongue Drum 12 inch 10 Notes - EQ Healing',
        'USD $89.99',
        '10 notes / 12 inch',
        'HL-TD-018',
        'TD06',
        126,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 10 notes / 12 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        17,
    ),
    _p(
        'Huashu Crystal Kalimba 17/21 Keys Feather Series Acrylic Kalimba KAF21',
        'USD $52.99',
        '21 keys',
        'HL-KB-019',
        'KB05',
        163,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 21 keys. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        18,
    ),
    _p(
        'Hluru Goat Skin 9 keys kalimba For Spiritual Practices - Perfection Series',
        'USD $59.99',
        'goat skin',
        'HL-KB-020',
        'KB06',
        200,
        'Kalimbas',
        '9-Key Goat Skin Kalimba for Spiritual Practices. Warm resonant tones enhance meditation, mindfulness & energy healing. Easy to play, portable design with natural texture—ideal for spiritual seekers & mindful gifting.',
        19,
    ),
    _p(
        'Hluru Handpan - 10 Notes 22 inch DC04 Brown Handpan | Rich Harmonious Tones',
        'USD $299.99',
        '10 notes / 22 inch',
        'HL-HP-021',
        'HP01',
        237,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 10 notes / 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        20,
    ),
    _p(
        'Hluru Handpan - 9 Notes 22 inch DC04 Brown Handpan | Rich Harmonious Tones',
        'USD $329.99',
        '9 notes / 22 inch',
        'HL-HP-022',
        'HP02',
        74,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 9 notes / 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        21,
    ),
    _p(
        'Hluru Handpan - 10 Notes 22 inch DC04 Golden Edge Brown Handpan | Rich Harmonious Tones',
        'USD $359.99',
        '10 notes / 22 inch',
        'HL-HP-023',
        'HP03',
        111,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 10 notes / 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        22,
    ),
    _p(
        'Hluru Handpan - 9 Notes 22 inch STL Copper Handpan | Rich Harmonious Tones',
        'USD $389.99',
        '9 notes / 22 inch',
        'HL-HP-024',
        'HP04',
        148,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 9 notes / 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        23,
    ),
    _p(
        'Hluru Micro-alloy Steel and Premium Wood Tongue Drum 14-inch 15 Notes - EQ Healing',
        'USD $99.99',
        '15 notes / 14 inch',
        'HL-TD-025',
        'TD07',
        185,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 15 notes / 14 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        24,
    ),
    _p(
        'Hluru Oil Skin 9 keys kalimba For Sound Healing - Perfection Series',
        'USD $69.99',
        'oil skin',
        'HL-KB-026',
        'KB07',
        222,
        'Kalimbas',
        'This kalimba is born for healing music.The goat skin/ oil skin(cow skin) is a common material used in traditional African instruments, as it is durable and has a warm, natural tone. Material : Ostrya Japonica Cherry WoodFeatures : wah-wah effect, with warm and natural tone, A-miner:Upper E5 B4 C5 A5, Lower E4 A3 E3 C4 A4; C-major: Upper E5 G4 C5 G5, Lower E4 G3 E3 C4 F4',
        25,
    ),
    _p(
        'HLURU STL Handpan 10 Keys 22 inch, Golden Edge and Bronze',
        'USD $399.99',
        '10 keys / 22 inch',
        'HL-HP-027',
        'HP05',
        259,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 10 keys / 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        26,
    ),
    _p(
        'HLURU STL Handpan 10 Notes 22 inch, Bronze Finish',
        'USD $419.99',
        '22 inch',
        'HL-HP-028',
        'HP06',
        96,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        27,
    ),
    _p(
        'HLURU STL Handpan 9 Notes 22 inch, Bronze',
        'USD $429.99',
        '22 inch',
        'HL-HP-029',
        'HP07',
        133,
        'Handpans',
        "A hand-tuned handpan from HLURU's Shenzhen workshop — 22 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        28,
    ),
    _p(
        'Hluru Universal Pickup For Handpan & Tongue Drum & Kalimba & Cajon',
        'USD $449.99',
        'Handpans',
        'HL-HP-030',
        'HP08',
        170,
        'Handpans',
        'Compatible with Handpan, Tongue Drum, Kalimba Cajon. Clear sound amplification for acoustic instruments easy to install, reliable performance, ideal for live shows recording.',
        29,
    ),
    _p(
        'Hluru Vermilion Bird Cajon - Kids Version',
        'USD $129.99',
        'Cajons',
        'HL-CJ-031',
        'CJ06',
        207,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — Cajons. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        30,
    ),
    _p(
        'Hluru Wind Chime 8 tubes, Wave Series Double Swing',
        'USD $19.99',
        'Wind chimes',
        'HL-WC-032',
        'WC01',
        244,
        'Wind chimes',
        "A hand-tuned wind chime from HLURU's Shenzhen workshop — Wind chimes. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        31,
    ),
    _p(
        'Hluru Wind Chime 8 Notes, Octagon 8 tubes Meditation Series Single Swing',
        'USD $24.99',
        '8 notes',
        'HL-WC-033',
        'WC02',
        81,
        'Wind chimes',
        "A hand-tuned wind chime from HLURU's Shenzhen workshop — 8 notes. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        32,
    ),
    _p(
        'Hluru Wind Chime Carbon Fiber Series 8 tubes Single Swing',
        'USD $29.99',
        'Wind chimes',
        'HL-WC-034',
        'WC03',
        118,
        'Wind chimes',
        "A hand-tuned wind chime from HLURU's Shenzhen workshop — Wind chimes. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        33,
    ),
    _p(
        'Hluru Wind Chime - Winter Series 8 Notes | Soothing Pleasant Tones',
        'USD $39.99',
        '8 notes',
        'HL-WC-035',
        'WC04',
        155,
        'Wind chimes',
        "A hand-tuned wind chime from HLURU's Shenzhen workshop — 8 notes. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        34,
    ),
    _p(
        'Hluru Ziricote Cajón Multi-function Portable - Black Tortoise-shell Finish',
        'USD $139.99',
        'ziricote',
        'HL-CJ-036',
        'CJ07',
        192,
        'Cajons',
        "A hand-tuned cajon from HLURU's Shenzhen workshop — ziricote. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        35,
    ),
    _p(
        'Huashu 11 notes 6" C5 Major Carbon Steel Tongue Drum For Yoga -Golden Ginkgobiloba',
        'USD $109.99',
        '6 inch / carbon steel',
        'HL-TD-037',
        'TD08',
        229,
        'Steel tongue drums',
        'Ideal for Yoga with Golden Ginkgo Design. Warm, resonant tones enhance meditation & relaxation. Compact, easy to play, durable carbon steel build—perfect for yoga sessions & mindful gifting.',
        36,
    ),
    _p(
        'Huashu 11 notes 6" D5 Major Carbon Steel Tongue Drum For Sound Healing - Harmonic Disc',
        'USD $119.99',
        '6 inch / carbon steel',
        'HL-TD-038',
        'TD09',
        66,
        'Steel tongue drums',
        'Ideal for Sound Healing with Harmonic Disc Design. Rich, soothing tones enhance therapeutic sessions. Compact, easy to play, durable build perfect for healers mindful gifting.',
        37,
    ),
    _p(
        'Huashu 17/21 Keys Acrylic C Major Kalimba - Starry Sky',
        'USD $79.99',
        '21 keys / C Major',
        'HL-KB-039',
        'KB08',
        103,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 21 keys / C Major. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        38,
    ),
    _p(
        'Huashu 17/21 Keys Acrylic C Major Kalimba - Starry Sky Sakura',
        'USD $89.99',
        '21 keys / C Major',
        'HL-KB-040',
        'KB09',
        140,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 21 keys / C Major. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        39,
    ),
    _p(
        'Huashu Kalimba - 17 Keys Rabbit Wood Kalimba, with Palm Rest | Clear Crisp Tone',
        'USD $99.99',
        '17 keys',
        'HL-KB-041',
        'KB10',
        177,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 17 keys. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        40,
    ),
    _p(
        'Huashu Kalimba - 21 Keys Hollow Rabbit Mahogany Kalimba, with Palm Rest (Pink) | Clear Bright Tone',
        'USD $109.99',
        '21 keys',
        'HL-KB-042',
        'KB11',
        214,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 21 keys. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        41,
    ),
    _p(
        'Huashu Kalimba - 21 Keys Rainbow Bear Mahogany Kalimba, with Palm Rest | Clear Bright Tone',
        'USD $119.99',
        '21 keys',
        'HL-KB-043',
        'KB12',
        251,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 21 keys. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        42,
    ),
    _p(
        'Huashu Kalimba - 21 Keys Lotus Leaf Palm Rest Hollow Mahogany (Blue) | Rich Bright Tone',
        'USD $129.99',
        '21 keys',
        'HL-KB-044',
        'KB13',
        88,
        'Kalimbas',
        "A hand-tuned kalimba from HLURU's Shenzhen workshop — 21 keys. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        43,
    ),
    _p(
        'Huashu Steel Tongue Drum - 13 notes 12 inch Carbon Steel Lotus Tongue Drum | Deep Resonant Tone',
        'USD $129.99',
        '12 inch',
        'HL-TD-045',
        'TD10',
        125,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 12 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        44,
    ),
    _p(
        'Huashu Steel Tongue Drum - 15 notes 12 inch Carbon Steel Lotus Tongue Drum | Deep Resonant Tone',
        'USD $139.99',
        '12 inch',
        'HL-TD-046',
        'TD11',
        162,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 12 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        45,
    ),
    _p(
        'Huashu Steel Tongue Drum - 13 notes 12 inch Carbon Steel Lotus Tongue Drum | Deep Resonant Tone',
        'USD $149.99',
        '12 inch',
        'HL-TD-047',
        'TD12',
        199,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 12 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        46,
    ),
    _p(
        'Huashu Steel Tongue Drum - 15 notes 12 inch Carbon Steel Lotus Tongue Drum | Deep Resonant Tone',
        'USD $159.99',
        '12 inch',
        'HL-TD-048',
        'TD13',
        236,
        'Steel tongue drums',
        "A hand-tuned steel tongue drum from HLURU's Shenzhen workshop — 12 inch. Delivers warm, sustained resonance for music therapy, performance, education and wholesale retail.",
        47,
    ),
]


# ===================== 分类 / 联系方式 / 页面 / 友链 =====================
STARTER_CATEGORIES = [
    {"name": "Steel tongue drums", "sort_order": 0},
    {"name": "Handpans", "sort_order": 1},
    {"name": "Kalimbas", "sort_order": 2},
    {"name": "Lyre harps", "sort_order": 3},
    {"name": "Cajons", "sort_order": 4},
    {"name": "Wind chimes", "sort_order": 5},
]

STARTER_CONTACTS = [
    {"contact_type": "Email", "contact_value": EMAIL},
    {"contact_type": "WhatsApp", "contact_value": WHATSAPP},
    {"contact_type": "Website", "contact_value": SITE_URL},
]

ABOUT_HTML = (
    "<p>Welcome to HLURU. We are a professional manufacturer and exporter of healing instruments, "
    "dedicated to providing hand-tuned steel tongue drums, handpans, kalimbas, lyre harps, cajons and "
    "wind chimes to customers worldwide since 2010.</p>"
    "<h3>Our Mission</h3>"
    "<p>To deliver instruments that meet international quality standards while building long-term trust with every client.</p>"
    "<h3>Why Choose Us</h3>"
    "<ul><li>Direct-from-factory pricing and strict quality control</li>"
    "<li>Fast response and reliable worldwide delivery</li>"
    "<li>Flexible customization and OEM/ODM support</li></ul>"
)

STARTER_PAGES = [
    {"title": "About Us", "slug": "about", "content": ABOUT_HTML, "enabled": 1, "sort_order": 10,
     "seo_title": "About HLURU", "seo_description": "HLURU is a direct manufacturer of healing instruments since 2010.",
     "seo_keywords": "about hluru, instrument manufacturer"},
]

STARTER_FRIEND_LINKS = [
    {"name": "Music Therapy Association", "url": "https://www.musictherapy.org/", "nofollow": 1, "sort_order": 0},
    {"name": "Sound Healers Association", "url": "https://www.soundhealers.org/", "nofollow": 1, "sort_order": 1},
]


# ===================== 资源拷贝 =====================
def _copy_assets():
    src = bundle_path("data", "preset_assets")
    dst = data_path("static", "uploads")
    if not os.path.isdir(src):
        return
    os.makedirs(dst, exist_ok=True)
    for fn in os.listdir(src):
        if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
            try:
                shutil.copy2(os.path.join(src, fn), os.path.join(dst, fn))
            except OSError:
                pass


def _db_path():
    return data_path("instance", "app.db")


def is_starter_loaded(conn=None):
    own = conn is None
    if own:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
    try:
        r = conn.execute("SELECT value FROM site_config WHERE key='starter_loaded'").fetchone()
        return r is not None and r["value"] == "1"
    finally:
        if own:
            conn.close()


def load_starter_preset(conn=None):
    """加载内置「HLURU 示例模板」：填充全部示例内容（文字/图片/SEO/灰帽/域名等）。

    这是一个显式动作（首次运行自动触发，或后台「加载示例模板」手动触发），
    会覆盖当前的产品/横幅/联系方式/板块内容等客户数据，请先备份。
    """
    own = conn is None
    if own:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
    try:
        _copy_assets()

        # 站点配置
        for k, v in STARTER_SITE_CONFIG.items():
            conn.execute(
                "INSERT INTO site_config(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (k, "" if v is None else str(v)))
        conn.execute(
            "INSERT INTO site_config(key, value) VALUES('growth_settings', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (json.dumps(STARTER_GROWTH_SETTINGS, ensure_ascii=False),))

        # 板块：按 section_type upsert（保留已有板块行，补齐缺失板块）
        for s in STARTER_SECTIONS:
            row = conn.execute("SELECT id FROM sections WHERE section_type=?", (s["section_type"],)).fetchone()
            content_json = json.dumps(s["content"], ensure_ascii=False)
            if row:
                conn.execute(
                    "UPDATE sections SET title=?, content=?, enabled=?, sort_order=? WHERE section_type=?",
                    (s["title"], content_json, s["enabled"], s["sort_order"], s["section_type"]))
            else:
                conn.execute(
                    "INSERT INTO sections(section_type, title, content, enabled, sort_order) VALUES(?, ?, ?, ?, ?)",
                    (s["section_type"], s["title"], content_json, s["enabled"], s["sort_order"]))

        # 横幅 / 产品 / 分类 / 联系方式 / 友链 / 页面：先清后填（模板即覆盖式）
        conn.execute("DELETE FROM banner")
        for b in STARTER_BANNERS:
            conn.execute("INSERT INTO banner(image_path, sort_order) VALUES(?, ?)", (b["image_path"], b["sort_order"]))

        conn.execute("DELETE FROM products")
        for p in STARTER_PRODUCTS:
            conn.execute(
                "INSERT INTO products(name, price, spec, img, sku, model, stock, category, images, "
                "description, detail_layout, product_video, meta_title, meta_description) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'classic', '', ?, ?)",
                (p["name"], p["price"], p["spec"], p["img"], p["sku"], p["model"], p["stock"],
                 p["category"], json.dumps([p["img"]]), p["description"], p["meta_title"], p["meta_description"]))

        conn.execute("DELETE FROM categories")
        for c in STARTER_CATEGORIES:
            conn.execute("INSERT INTO categories(name, sort_order) VALUES(?, ?)", (c["name"], c["sort_order"]))

        conn.execute("DELETE FROM contacts")
        for c in STARTER_CONTACTS:
            conn.execute("INSERT INTO contacts(contact_type, contact_value) VALUES(?, ?)", (c["contact_type"], c["contact_value"]))

        conn.execute("DELETE FROM friend_links")
        for f in STARTER_FRIEND_LINKS:
            conn.execute("INSERT INTO friend_links(name, url, nofollow, sort_order) VALUES(?, ?, ?, ?)",
                         (f["name"], f["url"], f["nofollow"], f["sort_order"]))

        conn.execute("DELETE FROM pages")
        for pg in STARTER_PAGES:
            conn.execute(
                "INSERT INTO pages(title, slug, content, enabled, sort_order, seo_title, seo_description, seo_keywords) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (pg["title"], pg["slug"], pg["content"], pg["enabled"], pg["sort_order"],
                 pg["seo_title"], pg["seo_description"], pg["seo_keywords"]))

        conn.execute(
            "INSERT INTO site_config(key, value) VALUES('starter_loaded', '1') "
            "ON CONFLICT(key) DO UPDATE SET value='1'")
        if own:
            conn.commit()
        return True
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()


def clear_site_content(conn=None):
    """一键清空：删除所有客户填写的内容，但保留 9 大板块「框架骨架」与模板/语言等结构性配置。

    清空对象：产品、横幅、联系方式、询盘、页面、分类、友链、板块内容、推广工具箱配置、
    以及全部 SEO/GEO/公司/支付/域名等站点配置内容（含公司名 company_name / 品牌等，
    仅保留 language/site_template/site_layout/cookie_enabled/analytics_code/starter_loaded 等结构键）。
    """
    own = conn is None
    if own:
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
    try:
        for t in ("products", "banner", "contacts", "inquiries", "pages", "categories", "friend_links", "collection_drafts"):
            conn.execute("DELETE FROM %s" % t)

        # 保留板块行（骨架），仅清空其内容
        conn.execute("UPDATE sections SET content=''")
        conn.execute("DELETE FROM site_config WHERE key='growth_settings'")

        # 清空内容型配置，保留结构性配置（公司名等全部内容一并清空）
        structural = ("language", "site_template", "site_layout", "onboarding_done",
                     "deploy_count", "cookie_enabled", "analytics_code", "starter_loaded")
        placeholders = ",".join("?" * len(structural))
        conn.execute("DELETE FROM site_config WHERE key NOT IN (%s)" % placeholders, structural)
        conn.execute("UPDATE site_config SET value='' WHERE key='onboarding_done'")

        if own:
            conn.commit()
        return True
    except Exception:
        if own:
            conn.rollback()
        raise
    finally:
        if own:
            conn.close()
