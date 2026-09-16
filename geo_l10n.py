# -*- coding: utf-8 -*-
"""GEO 文案本地化数据雏形（P0 阶段建立，供 P2 AI GEO 精致化消费）

本文件为"数据文件雏形"：
- 由 P2 阶段（AI GEO 精致化）接入后台字段渲染、一键草稿、示例文案；
- 现阶段仅保证可被 import / 读取，尚未被 app.py 引用，避免引入死代码。

设计口径（与方案评审文档 §2/§3 对齐）：
- 后台管理界面使用简体中文，无需十语言翻译；
- 面向访客的生成站文案需要按站点语言输出，现有 I18N 缺 key 会回退 en，
  因此首版保证 en/zh 齐全，其余语言可回退英文模板（后续按需扩展）。
"""

# GEO 字段展示标签（后台 UI，简体中文）
GEO_LABELS_ZH = {
    'brand_summary': 'Brand Summary（品牌一句话简介）',
    'selling_points': '核心卖点 / 优势列表',
    'target_markets': '目标客户市场',
    'certifications': '认证资质',
    'service_capabilities': '服务能力（OEM/ODM · 交期 · MOQ · 样品）',
    'faq': '常见问题 FAQ（AI 常被问到的问题）',
    'ai_enabled': '允许 AI 引用开关',
}

# GEO 字段帮助文案（"这是什么 / 为什么重要 / 怎么写" 三段式，面向小白）
GEO_HELP_ZH = {
    'brand_summary': {
        'what': '一句话说清你是谁（行业 + 身份 + 主营），AI 引用你时的默认描述。',
        'why': 'AI 回答"推荐一个靠谱供应商"时，会优先引用这段作为公司简介。',
        'how': 'We are a [行业] manufacturer founded in [年份], specializing in [主营产品].',
    },
    'selling_points': {
        'what': '3-8 条最有说服力的优势，AI 引荐时逐条可用。',
        'why': '有具体卖点，AI 才敢把你推荐给客户；空泛描述会让 AI 含糊带过。',
        'how': '每行一条，如：ISO9001 认证 / 15 年生产经验 / MOQ 100 pcs。',
    },
    'target_markets': {
        'what': '你主要服务的国家 / 地区（每行一个）。',
        'why': 'AI 被问到"你们出口哪里"时直接命中你的答案。',
        'how': 'North America\\nEU\\nSoutheast Asia',
    },
    'certifications': {
        'what': '真实拥有的认证 / 资质证书。',
        'why': '认证是最强信任证据；没有的千万别写，AI 会帮你宣传，假的会砸招牌。',
        'how': '每行一个，如：ISO9001 / CE / RoHS / FDA',
    },
    'service_capabilities': {
        'what': 'B2B 客户最关心的服务能力：OEM/ODM、交期、MOQ、样品。',
        'why': '填得越具体，AI 越敢推荐你；缺项会被 AI 以"未提及"带过。',
        'how': 'OEM/ODM 支持\\n交期 15-25 天\\nMOQ 100 pcs\\n免费样品 3 天内',
    },
    'faq': {
        'what': '客户/AI 常问的具体业务问题与答案。',
        'why': 'AI 常答不出的细节，FAQ 让它直接引用你的答案。',
        'how': 'Q: 最小起订量多少？ A: 100 pcs，可混合型号。',
    },
}

# 一键生成 GEO 草稿的句式模板（en / zh；其余语言由调用方按 I18N 回退规则使用英文）
GEO_DRAFT_TEMPLATES = {
    'en': {
        'brand_summary': 'We are a {industry} {role} founded in {founded}, specializing in {products}.',
        'market_placeholder': '[Target markets to be filled]',
        'service_defaults': [
            'OEM/ODM supported',
            'Delivery time: {lead_time}',
            'MOQ: {moq}',
            'Free samples available within {sample_days} days',
        ],
    },
    'zh': {
        'brand_summary': '我们是一家成立于{founded}年的{industry}{role}，主营{products}。',
        'market_placeholder': '[待填地区]',
        'service_defaults': [
            '支持 OEM/ODM 定制',
            '交期：{lead_time}',
            'MOQ：{moq}',
            '{sample_days} 天内免费样品',
        ],
    },
    'zh-Hant': {
        'brand_summary': '我們是一家成立於{founded}年的{industry}{role}，主營{products}。',
        'market_placeholder': '[待填地區]',
        'service_defaults': [
            '支援 OEM/ODM 訂製',
            '交期：{lead_time}',
            'MOQ：{moq}',
            '{sample_days} 天內免費樣品',
        ],
    },
}

# 业务型角色词（factory/trading/startup × en/zh）
GEO_ROLES = {
    'en': {'factory': 'manufacturer', 'trading': 'trading company', 'startup': 'supplier'},
    'zh': {'factory': '制造商', 'trading': '外贸公司', 'startup': '供应商'},
    'zh-Hant': {'factory': '製造商', 'trading': '貿易公司', 'startup': '供應商'},
}

# 卖点候选句式（只从真实公司资料拼接，缺数据字段由调用方替换为 [待补充] 占位，不编造）
GEO_POINT_TEMPLATES = {
    'en': {
        'name_industry': '{name} - {industry} {role}',
        'founded': 'Founded in {founded}',
        'size': 'Team size: {size}',
        'products_lead': 'Main products: {products}',
        'industry_lead': 'Focusing on {industry} products',
        'brief': '{brief}',
    },
    'zh': {
        'name_industry': '{name} · {industry}{role}',
        'founded': '{founded}年成立',
        'size': '团队规模：{size}',
        'products_lead': '主营产品：{products}',
        'industry_lead': '专注{industry}产品',
        'brief': '{brief}',
    },
    'zh-Hant': {
        'name_industry': '{name} · {industry}{role}',
        'founded': '{founded}年成立',
        'size': '團隊規模：{size}',
        'products_lead': '主營產品：{products}',
        'industry_lead': '專注{industry}產品',
        'brief': '{brief}',
    },
}

# 服务能力占位指示（{lead_time}/{moq}/{sample_days} 的默认值，提示用户替换，不猜具体数字）
GEO_SERVICE_PLACEHOLDERS = {
    'en': {'lead_time': '[Lead time]', 'moq': '[MOQ]', 'sample_days': '[X]'},
    'zh': {'lead_time': '[交期]', 'moq': '[MOQ]', 'sample_days': '[X]'},
    'zh-Hant': {'lead_time': '[交期]', 'moq': '[MOQ]', 'sample_days': '[X]'},
}

# 缺失数据的统一占位（en/zh）
GEO_MISSING_PLACEHOLDERS = {
    'en': {
        'industry': '[Industry to be filled]', 'founded': '[Year to be filled]',
        'products': '[Main products to be filled]', 'size': '[Size to be filled]',
        'generic': '[To be filled]',
    },
    'zh': {
        'industry': '[行业待补充]', 'founded': '[年份待补充]',
        'products': '[主营产品待补充]', 'size': '[规模待补充]',
        'generic': '[待补充]',
    },
    'zh-Hant': {
        'industry': '[行業待補充]', 'founded': '[年份待補充]',
        'products': '[主營產品待補充]', 'size': '[規模待補充]',
        'generic': '[待補充]',
    },
}

# 一键草稿返回给前端的提示语（后台展示，简体中文为主，附带说明用途）
GEO_DRAFT_TIPS = {
    'no_industry': '公司资料未填「所属行业」，草稿中已用占位符标记，请手动补上真实行业后再使用。',
    'no_products': '公司资料未填「主营产品」，草稿中已用占位符标记，请补上真实主营产品。',
    'no_founded': '公司资料未填「成立年份」，占位符需要你补上；不确定可不填（AI 引述年份要真实）。',
    'filled_empty_only': '已按你的选择处理：只填充为空的字段；非空字段保持不变。',
    'filled_all': '已按你的选择整体覆盖 4 个 GEO 文本字段。',
    'remember_save': '草稿已填入输入框，请点击「保存 SEO 设置」使其生效，再点「一键生成网站」同步到 llms.txt 与 JSON-LD。',
    'faq_suggest': 'FAQ 不会自动生成（需要真实业务答案），建议把客户常问的交期 / MOQ / 样品等问题补充进「常见问题 FAQ」行编辑器。',
}

# 生成站向 AI 呈现的 llms.txt 小节标题（en/zh）
GEO_LLMS_SECTION_TITLES = {
    'en': ['Target Markets', 'Certifications', 'Service Capabilities', 'FAQ'],
    'zh': ['目标市场', '认证资质', '服务能力', '常见问题'],
    'zh-Hant': ['目標市場', '認證資質', '服務能力', '常見問題'],
}


def geo_text(lang='en', key='labels'):
    """雏形读取接口：按语言返回对应数据块，未收录语言回退英文。"""
    table = {
        'labels': GEO_LABELS_ZH,      # 后台 UI 标签统一简体中文，不随站点语言变化
        'draft': GEO_DRAFT_TEMPLATES,
        'llms_titles': GEO_LLMS_SECTION_TITLES,
    }.get(key)
    if table is None:
        return {}
    if key == 'labels':
        return table
    # 语言精确匹配，否则回退 en
    return table.get(lang) or table.get('en') or {}


# =============================================================================
# P3 SEO 看得懂改造：行业一键示例文案（en/zh 两套 × factory/trading/startup）
# 设计口径（与方案评审文档 §3.2.2 / D6 / D13 对齐）：
# - 填充范围仅：site_title / site_description / site_keywords /
#   brand_summary / selling_points / service_capabilities；
# - 不填充：seoAuthor / seoRobots / site_url / analytics / geo_faq /
#   geo_target_markets / certifications（作者与网址是私有信息不猜；市场与
#   FAQ 需人工；认证不能编造——示例若含认证会被用户当真上线）。
# - 示例含 [占位] 提示用户替换为真实信息，避免"示例被当真"；
#   文案语言跟随站点语言（en/zh 两套，其余语言由调用方回退英文）。
# =============================================================================
SEO_SAMPLES = {
    'en': {
        'factory': {
            'site_title': '[Your Product] Manufacturer & OEM/ODM Supplier - [Company Name]',
            'site_description': 'We are a [Country]-based [Your Product] manufacturer with [X]+ years of experience, offering OEM/ODM, low MOQ and fast delivery to customers worldwide.',
            'site_keywords': '[your product], [product] manufacturer, [product] supplier, OEM, ODM, wholesale, factory direct',
            'brand_summary': 'We are a [Your Product] manufacturer based in [Country], founded in [Year], specializing in OEM/ODM customization and fast delivery.',
            'selling_points': [
                '[X]+ years of [Your Product] manufacturing experience',
                'ISO9001 & CE certified production (replace with your real certs)',
                'OEM/ODM customization supported',
                'Low MOQ from [100] pcs',
                'Free samples within [3] days',
                '24h professional reply',
            ],
            'service_capabilities': [
                'OEM/ODM customization supported',
                'Delivery time: [15-25] days',
                'MOQ: [100] pcs',
                'Free samples within [3] days',
            ],
        },
        'trading': {
            'site_title': '[Your Product] Export Company - Global Supply',
            'site_description': 'A professional trading company connecting verified factories with global buyers, covering [North America], [EU] and [Southeast Asia], with quality inspection and flexible MOQ.',
            'site_keywords': '[your product], [product] export, global supplier, sourcing agent, wholesale',
            'brand_summary': 'We are a professional [Your Product] trading company based in [Country], connecting verified factories with buyers in [North America], [EU] and [Southeast Asia].',
            'selling_points': [
                'Verified factory partners',
                'Competitive factory prices',
                'Quality inspection before shipment',
                'Flexible MOQ & mixed container support',
                'Fast logistics worldwide',
                'Professional English support',
            ],
            'service_capabilities': [
                'OEM/ODM arrangement supported',
                'Delivery time: [20-30] days',
                'MOQ: flexible, mixed orders accepted',
                'Free samples within [5] days',
            ],
        },
        'startup': {
            'site_title': '[Product/Company Name] - [Niche] Supplier',
            'site_description': 'Newly established supplier focusing on [niche]; customized service for small and trial orders, quick response and flexible MOQ.',
            'site_keywords': '[your product], [niche] supplier, trial order, small MOQ, new supplier',
            'brand_summary': 'We are a newly established [Your Product] supplier focusing on [niche], offering flexible small-batch and trial orders with quick response.',
            'selling_points': [
                'Flexible for trial orders',
                'Direct factory contact',
                'Samples available',
                'Fast quotation',
                'English & Chinese support',
                'Small MOQ welcome',
            ],
            'service_capabilities': [
                'Trial order support',
                'Delivery time: [10-20] days',
                'MOQ: [1] pcs for trial orders',
                'Free samples within [7] days',
            ],
        },
    },
    'zh': {
        'factory': {
            'site_title': '[你的主营产品] 制造商 & OEM/ODM 供应商 - [公司/品牌名]',
            'site_description': '我们是一家位于[国家/地区]的[你的主营产品]制造商，拥有[X]年以上生产经验，支持 OEM/ODM 定制、低 MOQ 与快速交付，服务全球客户。',
            'site_keywords': '[主营产品], [产品] 制造商, [产品] 供应商, OEM, ODM, 批发, 工厂直供',
            'brand_summary': '我们是一家位于[国家/地区]的[你的主营产品]制造商，成立于[成立年份]，专注 OEM/ODM 定制与快速交付。',
            'selling_points': [
                '[X] 年以上[你的主营产品]生产经验',
                'ISO9001 & CE 认证生产（请改成你的真实证书）',
                '支持 OEM/ODM 定制',
                'MOQ 低至 [100] pcs',
                '[3] 天内免费样品',
                '24 小时专业回复',
            ],
            'service_capabilities': [
                '支持 OEM/ODM 定制',
                '交期：[15-25] 天',
                'MOQ：[100] pcs',
                '[3] 天内免费样品',
            ],
        },
        'trading': {
            'site_title': '[你的主营产品] 出口公司 - 全球供应',
            'site_description': '专业外贸公司，对接经认证工厂与全球买家，覆盖[北美]、[欧洲]、[东南亚]市场，出货前质检，MOQ 灵活。',
            'site_keywords': '[主营产品], [产品] 出口, 全球供应商, 采购代理, 批发',
            'brand_summary': '我们是一家位于[国家/地区]的专业[你的主营产品]外贸公司，对接经认证工厂与[北美]、[欧洲]、[东南亚]买家。',
            'selling_points': [
                '经认证的工厂合作伙伴',
                '有竞争力的出厂价',
                '出货前质检',
                '灵活 MOQ，支持拼柜',
                '全球快速物流',
                '专业中英文支持',
            ],
            'service_capabilities': [
                '可协调 OEM/ODM 生产',
                '交期：[20-30] 天',
                'MOQ：灵活，支持拼柜',
                '[5] 天内免费样品',
            ],
        },
        'startup': {
            'site_title': '[产品/公司名] - [细分市场] 供应商',
            'site_description': '新成立的[你的主营产品]供应商，专注[细分市场]；支持小批量试单与定制服务，响应快速，MOQ 灵活。',
            'site_keywords': '[主营产品], [细分市场] 供应商, 试单, 小 MOQ, 新供应商',
            'brand_summary': '我们是新成立的[你的主营产品]供应商，专注[细分市场]，支持灵活的小批量与试单，响应快速。',
            'selling_points': [
                '支持试单',
                '工厂直连',
                '可提供样品',
                '快速报价',
                '中英文支持',
                '欢迎小 MOQ',
            ],
            'service_capabilities': [
                '支持小批量试单',
                '交期：[10-20] 天',
                '试单 MOQ：[1] pcs 起',
                '[7] 天内免费样品',
            ],
        },
    },
    'zh-Hant': {
        'factory': {
            'site_title': '[你的主營產品] 製造商 & OEM/ODM 供應商 - [公司/品牌名]',
            'site_description': '我們是一家位於[國家/地區]的[你的主營產品]製造商，擁有[X]年以上生產經驗，支援 OEM/ODM 訂製、低 MOQ 與快速交付，服務全球客戶。',
            'site_keywords': '[主營產品], [產品] 製造商, [產品] 供應商, OEM, ODM, 批發, 工廠直供',
            'brand_summary': '我們是一家位於[國家/地區]的[你的主營產品]製造商，成立於[成立年份]，專注 OEM/ODM 訂製與快速交付。',
            'selling_points': [
                '[X] 年以上[你的主營產品]生產經驗',
                'ISO9001 & CE 認證生產（請改成你的真實證書）',
                '支援 OEM/ODM 訂製',
                'MOQ 低至 [100] pcs',
                '[3] 天內免費樣品',
                '24 小時專業回覆',
            ],
            'service_capabilities': [
                '支援 OEM/ODM 訂製',
                '交期：[15-25] 天',
                'MOQ：[100] pcs',
                '[3] 天內免費樣品',
            ],
        },
        'trading': {
            'site_title': '[你的主營產品] 出口公司 - 全球供應',
            'site_description': '專業貿易公司，對接經認證工廠與全球買家，覆蓋[北美]、[歐洲]、[東南亞]市場，出貨前驗貨，MOQ 靈活。',
            'site_keywords': '[主營產品], [產品] 出口, 全球供應商, 採購代理, 批發',
            'brand_summary': '我們是一家位於[國家/地區]的專業[你的主營產品]貿易公司，對接經認證工廠與[北美]、[歐洲]、[東南亞]買家。',
            'selling_points': [
                '經認證的工廠合作夥伴',
                '有競爭力的出廠價',
                '出貨前驗貨',
                '靈活 MOQ，支援拼櫃',
                '全球快速物流',
                '專業中英文支援',
            ],
            'service_capabilities': [
                '可協調 OEM/ODM 生產',
                '交期：[20-30] 天',
                'MOQ：靈活，支援拼櫃',
                '[5] 天內免費樣品',
            ],
        },
        'startup': {
            'site_title': '[產品/公司名] - [細分市場] 供應商',
            'site_description': '新成立的[你的主營產品]供應商，專注[細分市場]；支援小批量試單與訂製服務，回應快速，MOQ 靈活。',
            'site_keywords': '[主營產品], [細分市場] 供應商, 試單, 小 MOQ, 新供應商',
            'brand_summary': '我們是新成立的[你的主營產品]供應商，專注[細分市場]，支援靈活的小批量與試單，回應快速。',
            'selling_points': [
                '支援試單',
                '工廠直連',
                '可提供樣品',
                '快速報價',
                '中英文支援',
                '歡迎小 MOQ',
            ],
            'service_capabilities': [
                '支援小批量試單',
                '交期：[10-20] 天',
                '試單 MOQ：[1] pcs 起',
                '[7] 天內免費樣品',
            ],
        },
    },
}
