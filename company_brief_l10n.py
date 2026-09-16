# -*- coding: utf-8 -*-
"""公司简介多语言文案（支持 en/zh/ja/ko/de/es/ru/fr/pt/ar）。
纯本地模板文案；按站点所选语言输出纯对应语言内容，禁止混用英文兜底。
结构：
- name_fb / industry_fb: 公司名称 / 行业字段缺失时的本地语言兜底
- {模板}_p1: 定位句（{name}/{industry}）
- {模板}_main: 主体能力句
- factory_founded: 工厂模板在有成立年份时追加的句子（{year} 为提取的 4 位年份）
- products_sentence: 主营产品列举句（{prods} 为按本语言连接词生成的列表）
- {模板}_p3: 合作承诺句
- size_suffix: 团队规模补充句（{size}）
- origin_since / origin_in: 成立时间 / 所在地片段
- punct: 段落句号（中文/日文句号，其余句点）
"""

BRIEF_L10N = {
    # ---------------- English ----------------
    'en': {
        'name_fb': 'our company',
        'industry_fb': 'our industry',
        'factory_p1': '{name} is a professional manufacturer with years of experience in {industry}.',
        'factory_main': 'We run our own production lines with strict quality control from raw materials to finished goods.',
        'factory_founded': 'Since {year}, we have been improving our manufacturing capabilities continuously.',
        'factory_p3': 'We support OEM / ODM, custom specifications, and stable volume supply for importers and brand owners.',
        'trading_p1': '{name} is an export-focused trading company specializing in {industry}.',
        'trading_main': 'With a professional sourcing and supply chain team, we connect overseas buyers with reliable partner factories to deliver competitive pricing, consistent quality, and on-time shipment.',
        'trading_p3': 'We are committed to offering responsive service, flexible order quantities, and stable long-term cooperation for distributors, retailers, and e-commerce sellers worldwide.',
        'startup_p1': '{name} is a young, fast-growing company focused on {industry}.',
        'startup_main': 'We combine fresh ideas with an agile operation model to bring you innovative products and fast, attentive support from first inquiry to after-sales.',
        'startup_p3': 'As a growing team, we warmly welcome small-batch trial orders, sample customization, and partner programs, so we can grow with your business step by step.',
        'products_sentence': 'Our product range includes {prods}.',
        'size_suffix': 'With a team of {size}, we are well positioned to serve clients of all sizes.',
        'origin_since': 'since {founded}',
        'origin_in': 'based in {address}',
        'punct': '.',
    },
    # ---------------- 简体中文 ----------------
    'zh': {
        'name_fb': '本公司',
        'industry_fb': '本行业',
        'factory_p1': '{name}是深耕{industry}多年的专业制造商，拥有丰富的生产经验。',
        'factory_main': '我们运营自有生产线，从原材料到成品层层把关，严格进行品质控制。',
        'factory_founded': '自{year}年以来，我们持续提升制造能力，不断优化工艺与产能。',
        'factory_p3': '我们支持OEM/ODM定制、非标规格开发，可为进口商与品牌商提供稳定的大货供应。',
        'trading_p1': '{name}是一家专注{industry}的出口贸易公司。',
        'trading_main': '依托专业的采购与供应链团队，我们帮助海外买家对接可靠的合作工厂，在具备竞争力的价格下保障品质稳定与按时交货。',
        'trading_p3': '我们致力于为全球分销商、零售商和电商卖家提供快速响应、灵活起订量与长期稳定的合作。',
        'startup_p1': '{name}是一家专注{industry}的年轻成长型企业。',
        'startup_main': '我们以新鲜创意结合敏捷的运营模式，从首次询盘到售后服务都为您带来创新产品与快速细致的支持。',
        'startup_p3': '作为成长中的团队，我们真诚欢迎小批量试单、样品定制与合作伙伴计划，愿与您的业务一同成长。',
        'products_sentence': '我们的产品范围包括{prods}。',
        'size_suffix': '团队规模{size}人，具备服务各类客户的能力。',
        'origin_since': '自{founded}起',
        'origin_in': '总部位于{address}',
        'punct': '。',
    },
    # ---------------- 繁體中文（香港/澳門） ----------------
    'zh-Hant': {
        'name_fb': '本公司',
        'industry_fb': '本行業',
        'factory_p1': '{name}是深耕{industry}多年的專業製造商，擁有豐富的生產經驗。',
        'factory_main': '我們營運自有生產線，從原材料到成品層層把關，嚴格進行品質控制。',
        'factory_founded': '自{year}年以來，我們持續提升製造能力，不斷優化工藝與產能。',
        'factory_p3': '我們支援OEM/ODM訂製、非標規格開發，可為進口商與品牌商提供穩定的大貨供應。',
        'trading_p1': '{name}是一家專注{industry}的出口貿易公司。',
        'trading_main': '依託專業的採購與供應鏈團隊，我們協助海外買家對接可靠的合作工廠，在具競爭力的價格下保障品質穩定與按時交貨。',
        'trading_p3': '我們致力於為全球經銷商、零售商和電商賣家提供快速回應、靈活起訂量與長期穩定的合作。',
        'startup_p1': '{name}是一家專注{industry}的年輕成長型企業。',
        'startup_main': '我們以新穎創意結合敏捷的營運模式，從首次詢盤到售後服務都為您帶來創新產品與快速細緻的支援。',
        'startup_p3': '作為成長中的團隊，我們真誠歡迎小批量試單、樣品訂製與合作夥伴計劃，願與您的業務一同成長。',
        'products_sentence': '我們的產品範圍包括{prods}。',
        'size_suffix': '團隊規模{size}人，具備服務各類客戶的能力。',
        'origin_since': '自{founded}起',
        'origin_in': '總部位於{address}',
        'punct': '。',
    },
    # ---------------- 日本語 ----------------
    'ja': {
        'name_fb': '当社',
        'industry_fb': '当社の業界',
        'factory_p1': '{name}は{industry}に長年携わる専門メーカーです。',
        'factory_main': '自社工場で生産ラインを運営し、原材料から完成品まで各工程で厳格な品質管理を行っています。',
        'factory_founded': '{year}年から製造能力の向上に継続的に取り組んでおります。',
        'factory_p3': 'OEM/ODM、カスタム仕様、輸入業者・ブランドオーナー向けの安定した量産供給に対応しております。',
        'trading_p1': '{name}は{industry}に特化した輸出専門の貿易会社です。',
        'trading_main': '専門の調達・サプライチェーンチームにより、海外バイヤーと信頼できる提携工場をつなぎ、競争力のある価格・安定した品質・納期通りの出荷を実現します。',
        'trading_p3': '世界中の卸売業者・小売業者・EC販売者に対し、迅速な対応、柔軟な注文数量、長期的で安定した協力体制を提供いたします。',
        'startup_p1': '{name}は{industry}に注力する若く成長著しい企業です。',
        'startup_main': '斬新なアイデアと機敏な運営体制を組み合わせ、初回のお問い合わせからアフターサポートまで、革新的な製品ときめ細かな迅速対応をご提供します。',
        'startup_p3': '成長を続けるチームとして、少ロット試験注文・サンプルカスタマイズ・パートナープログラムを歓迎し、お客様のビジネスとともに歩んでまいります。',
        'products_sentence': '当社の製品ラインナップには{prods}などがあります。',
        'size_suffix': 'チーム{size}名体制で、あらゆる規模のお客様にご対応できます。',
        'origin_since': '{founded}年より',
        'origin_in': '{address}に拠点を置く',
        'punct': '。',
    },
    # ---------------- 한국어 ----------------
    'ko': {
        'name_fb': '저희 회사',
        'industry_fb': '당사 업계',
        'factory_p1': '{name}는(은) {industry} 분야에서 다년간 경험을 쌓아온 전문 제조업체입니다.',
        'factory_main': '자체 생산라인을 운영하며 원자재부터 완제품까지 모든 공정에서 엄격한 품질 관리를 수행합니다.',
        'factory_founded': '{year}년부터 지속적으로 제조 역량을 향상해 왔습니다.',
        'factory_p3': 'OEM/ODM, 맞춤 사양, 수입업체 및 브랜드 오너를 위한 안정적인 대량 공급을 지원합니다.',
        'trading_p1': '{name}는(은) {industry} 분야에 특화된 수출 전문 무역회사입니다.',
        'trading_main': '전문 소싱 및 공급망 팀을 통해 해외 바이어와 신뢰할 수 있는 협력 공장을 연결하여 경쟁력 있는 가격, 안정적인 품질, 정시 출하를 제공합니다.',
        'trading_p3': '전 세계 유통업체, 소매업체, 이커머스 판매자에게 신속한 응대, 유연한 주문 수량, 안정적인 장기 협력을 약속드립니다.',
        'startup_p1': '{name}는(은) {industry}에 집중하는 젊고 빠르게 성장하는 기업입니다.',
        'startup_main': '새로운 아이디어와 민첩한 운영 방식을 결합하여 첫 문의부터 애프터서비스까지 혁신적인 제품과 신속하고 세심한 지원을 제공합니다.',
        'startup_p3': '성장하는 팀으로서 소량 시험 주문, 샘플 커스터마이징, 파트너 프로그램을 환영하며 고객의 비즈니스와 함께 성장하겠습니다.',
        'products_sentence': '당사의 제품군에는 {prods} 등이 포함됩니다.',
        'size_suffix': '{size}명 규모의 팀으로 다양한 규모의 고객을 지원할 수 있습니다.',
        'origin_since': '{founded}년부터',
        'origin_in': '{address}에 본사를 두고 있으며',
        'punct': '.',
    },
    # ---------------- Deutsch ----------------
    'de': {
        'name_fb': 'unser Unternehmen',
        'industry_fb': 'unsere Branche',
        'factory_p1': '{name} ist ein professioneller Hersteller mit langjähriger Erfahrung in {industry}.',
        'factory_main': 'Wir betreiben eigene Produktionslinien und unterziehen jede Stufe – vom Rohmaterial bis zum Fertigprodukt – einer strengen Qualitätskontrolle.',
        'factory_founded': 'Seit {year} verbessern wir kontinuierlich unsere Fertigungskapazitäten.',
        'factory_p3': 'Wir unterstützen OEM/ODM, kundenspezifische Spezifikationen und stabile Mengenlieferungen für Importeure und Markeninhaber.',
        'trading_p1': '{name} ist ein auf {industry} spezialisiertes Export-Handelsunternehmen.',
        'trading_main': 'Mit einem professionellen Sourcing- und Supply-Chain-Team verbinden wir internationale Käufer mit zuverlässigen Partnerfabriken und sichern wettbewerbsfähige Preise, gleichbleibende Qualität und pünktliche Lieferung.',
        'trading_p3': 'Wir bieten Distributoren, Einzelhändlern und E-Commerce-Verkäufern weltweit schnellen Service, flexible Bestellmengen und stabile langfristige Zusammenarbeit.',
        'startup_p1': '{name} ist ein junges, schnell wachsendes Unternehmen mit Fokus auf {industry}.',
        'startup_main': 'Wir verbinden frische Ideen mit einem agilen Geschäftsmodell und bieten von der ersten Anfrage bis zum After-Sales-Service innovative Produkte sowie schnelle, aufmerksame Unterstützung.',
        'startup_p3': 'Als wachsendes Team heißen wir Kleinserien-Testaufträge, Musteranfertigungen und Partnerprogramme herzlich willkommen – lassen Sie uns gemeinsam mit Ihrem Geschäft wachsen.',
        'products_sentence': 'Unser Produktsortiment umfasst {prods}.',
        'size_suffix': 'Mit einem Team von {size} sind wir bestens aufgestellt, um Kunden jeder Größe zu bedienen.',
        'origin_since': 'seit {founded}',
        'origin_in': 'mit Sitz in {address}',
        'punct': '.',
    },
    # ---------------- Español ----------------
    'es': {
        'name_fb': 'nuestra empresa',
        'industry_fb': 'nuestro sector',
        'factory_p1': '{name} es un fabricante profesional con años de experiencia en {industry}.',
        'factory_main': 'Operamos nuestras propias líneas de producción con un estricto control de calidad en cada etapa, desde las materias primas hasta los productos terminados.',
        'factory_founded': 'Desde {year}, hemos mejorado continuamente nuestras capacidades de fabricación.',
        'factory_p3': 'Apoyamos OEM/ODM, especificaciones personalizadas y suministro estable a granel para importadores y propietarios de marcas.',
        'trading_p1': '{name} es una empresa comercializadora de exportación especializada en {industry}.',
        'trading_main': 'Con un equipo profesional de sourcing y cadena de suministro, conectamos a compradores internacionales con fábricas asociadas fiables para ofrecer precios competitivos, calidad constante y envíos puntuales.',
        'trading_p3': 'Estamos comprometidos a ofrecer un servicio ágil, cantidades de pedido flexibles y una cooperación estable a largo plazo para distribuidores, minoristas y vendedores de comercio electrónico de todo el mundo.',
        'startup_p1': '{name} es una empresa joven y de rápido crecimiento centrada en {industry}.',
        'startup_main': 'Combinamos ideas frescas con un modelo operativo ágil para ofrecerle productos innovadores y un soporte rápido y atento desde la primera consulta hasta el servicio posventa.',
        'startup_p3': 'Como equipo en crecimiento, damos la bienvenida a pedidos de prueba en pequeñas cantidades, personalización de muestras y programas de colaboración: crezcamos junto a su negocio paso a paso.',
        'products_sentence': 'Nuestra gama de productos incluye {prods}.',
        'size_suffix': 'Con un equipo de {size}, estamos en condiciones de atender a clientes de todos los tamaños.',
        'origin_since': 'desde {founded}',
        'origin_in': 'con sede en {address}',
        'punct': '.',
    },
    # ---------------- Русский ----------------
    'ru': {
        'name_fb': 'наша компания',
        'industry_fb': 'наша отрасль',
        'factory_p1': '{name} — профессиональный производитель с многолетним опытом в сфере {industry}.',
        'factory_main': 'Мы управляем собственными производственными линиями и проводим строгий контроль качества на каждом этапе — от сырья до готовой продукции.',
        'factory_founded': 'С {year} года мы постоянно совершенствуем наши производственные возможности.',
        'factory_p3': 'Мы поддерживаем OEM/ODM, нестандартные спецификации и стабильные объёмные поставки для импортёров и владельцев брендов.',
        'trading_p1': '{name} — экспортно-ориентированная торговая компания, специализирующаяся на {industry}.',
        'trading_main': 'Профессиональная команда по закупкам и цепочке поставок связывает зарубежных покупателей с надёжными фабриками-партнёрами, обеспечивая конкурентоспособные цены, стабильное качество и своевременную отгрузку.',
        'trading_p3': 'Мы предлагаем дистрибьюторам, розничным продавцам и продавцам электронной коммерции по всему миру оперативный сервис, гибкие объёмы заказов и стабильное долгосрочное сотрудничество.',
        'startup_p1': '{name} — молодая, быстрорастущая компания, сфокусированная на {industry}.',
        'startup_main': 'Мы сочетаем свежие идеи с гибкой моделью работы, предлагая вам инновационные продукты и быстрое, внимательное обслуживание от первого запроса до послепродажной поддержки.',
        'startup_p3': 'Будучи растущей командой, мы приветствуем небольшие пробные заказы, индивидуальные образцы и партнёрские программы — давайте расти вместе с вашим бизнесом.',
        'products_sentence': 'В наш ассортимент входят: {prods}.',
        'size_suffix': 'Команда из {size} человек позволяет нам обслуживать клиентов любого масштаба.',
        'origin_since': 'с {founded}',
        'origin_in': 'базируется в {address}',
        'punct': '.',
    },
    # ---------------- Français ----------------
    'fr': {
        'name_fb': 'notre entreprise',
        'industry_fb': 'notre secteur',
        'factory_p1': '{name} est un fabricant professionnel fort de plusieurs années d’expérience dans {industry}.',
        'factory_main': 'Nous exploitons nos propres lignes de production avec un contrôle qualité strict à chaque étape, des matières premières aux produits finis.',
        'factory_founded': 'Depuis {year}, nous améliorons en continu nos capacités de fabrication.',
        'factory_p3': 'Nous proposons des services OEM/ODM, des spécifications personnalisées et un approvisionnement stable en volume pour les importateurs et les marques.',
        'trading_p1': '{name} est une société de négoce spécialisée dans l’export de {industry}.',
        'trading_main': 'Grâce à une équipe professionnelle dédiée à l’approvisionnement et à la chaîne d’approvisionnement, nous mettons en relation les acheteurs étrangers avec des usines partenaires fiables pour garantir des prix compétitifs, une qualité constante et des expéditions à temps.',
        'trading_p3': 'Nous nous engageons à offrir un service réactif, des quantités de commande flexibles et une coopération stable à long terme aux distributeurs, détaillants et vendeurs en ligne du monde entier.',
        'startup_p1': '{name} est une jeune entreprise en pleine croissance spécialisée dans {industry}.',
        'startup_main': 'Nous combinons des idées novatrices avec un modèle opérationnel agile pour vous proposer des produits innovants et un support rapide et attentionné, de la première demande au service après-vente.',
        'startup_p3': 'En tant qu’équipe en pleine croissance, nous accueillons volontiers les commandes d’essai en petite quantité, la personnalisation d’échantillons et les programmes de partenariat : grandissons ensemble, étape par étape.',
        'products_sentence': 'Notre gamme de produits comprend {prods}.',
        'size_suffix': 'Avec une équipe de {size}, nous sommes bien placés pour servir des clients de toutes tailles.',
        'origin_since': 'depuis {founded}',
        'origin_in': 'basée à {address}',
        'punct': '.',
    },
    # ---------------- Português ----------------
    'pt': {
        'name_fb': 'nossa empresa',
        'industry_fb': 'nosso setor',
        'factory_p1': '{name} é um fabricante profissional com anos de experiência em {industry}.',
        'factory_main': 'Operamos nossas próprias linhas de produção com rígido controle de qualidade em cada etapa, da matéria-prima ao produto acabado.',
        'factory_founded': 'Desde {year}, aprimoramos continuamente nossas capacidades de fabricação.',
        'factory_p3': 'Apoiamos OEM/ODM, especificações personalizadas e fornecimento estável em volume para importadores e proprietários de marcas.',
        'trading_p1': '{name} é uma empresa comercial de exportação especializada em {industry}.',
        'trading_main': 'Com uma equipe profissional de sourcing e cadeia de suprimentos, conectamos compradores no exterior a fábricas parceiras confiáveis para entregar preços competitivos, qualidade consistente e embarque pontual.',
        'trading_p3': 'Estamos comprometidos em oferecer serviço ágil, quantidades de pedido flexíveis e cooperação estável de longo prazo para distribuidores, varejistas e vendedores de e-commerce em todo o mundo.',
        'startup_p1': '{name} é uma empresa jovem e de rápido crescimento focada em {industry}.',
        'startup_main': 'Combinamos ideias novas com um modelo operacional ágil para trazer a você produtos inovadores e suporte rápido e atencioso, do primeiro contato ao pós-venda.',
        'startup_p3': 'Como equipe em crescimento, recebemos com satisfação pedidos de teste em pequenos lotes, personalização de amostras e programas de parceria — vamos crescer juntos com o seu negócio, passo a passo.',
        'products_sentence': 'Nossa linha de produtos inclui {prods}.',
        'size_suffix': 'Com uma equipe de {size}, estamos bem posicionados para atender clientes de todos os portes.',
        'origin_since': 'desde {founded}',
        'origin_in': 'com sede em {address}',
        'punct': '.',
    },
    # ---------------- العربية ----------------
    'ar': {
        'name_fb': 'شركتنا',
        'industry_fb': 'مجالنا',
        'factory_p1': '{name} مصنّع محترف يتمتع بخبرة سنوات طويلة في مجال {industry}.',
        'factory_main': 'ندير خطوط إنتاج خاصة بنا مع رقابة صارمة على الجودة في كل مرحلة، من المواد الخام حتى المنتجات النهائية.',
        'factory_founded': 'منذ {year} ونحن نعمل باستمرار على تحسين قدراتنا التصنيعية.',
        'factory_p3': 'ندعم التصنيع التعاقدي OEM/ODM والمواصفات المخصصة وتوريد الكميات الثابتة للمستوردين وأصحاب العلامات التجارية.',
        'trading_p1': '{name} شركة تجارية متخصصة في التصدير في مجال {industry}.',
        'trading_main': 'بفضل فريقنا المحترف في التوريد وسلسلة الإمداد، نربط المشترين في الخارج بمصانع شريكة موثوقة لنقدم أسعاراً تنافسية وجودة ثابتة وشحناً في الوقت المحدد.',
        'trading_p3': 'نلتزم بتقديم خدمة سريعة الاستجابة وكميات طلبات مرنة وتعاون مستقر طويل الأمد للموزعين وتجار التجزئة وبائعي التجارة الإلكترونية حول العالم.',
        'startup_p1': '{name} شركة شابة سريعة النمو تركز على مجال {industry}.',
        'startup_main': 'نجمع بين الأفكار الجديدة ونموذج تشغيلي مرن لنقدم لك منتجات مبتكرة ودعماً سريعاً ودقيقاً من أول استفسار حتى ما بعد البيع.',
        'startup_p3': 'كفريق في طور النمو، نرحب بطلبات التجربة بكميات صغيرة وتخصيص العينات وبرامج الشراكة — فلننمُ مع أعمالكم خطوة بخطوة.',
        'products_sentence': 'تشمل مجموعتنا من المنتجات {prods}.',
        'size_suffix': 'بفريق يضم {size}، نحن قادرون على خدمة العملاء بمختلف أحجامهم.',
        'origin_since': 'منذ {founded}',
        'origin_in': 'ومقرها في {address}',
        'punct': '.',
    },
}

SUPPORTED_LANGS = tuple(BRIEF_L10N.keys())


def normalize_lang(lang):
    """语言归一：支持完整键；空值回退 en；未知回退 en"""
    if not lang:
        return 'en'
    key = str(lang).strip().lower()
    # P5：繁体中文精确别名（必须在 head 截断前匹配，防止 zh-Hant 被 head=zh 截胡落简体）
    if key in ('zh-hant', 'zh-hk', 'zh-mo'):
        return 'zh-Hant'
    if key in BRIEF_L10N:
        return key
    # 兼容 zh_CN / pt_BR 等写法
    head = key.split('_')[0].split('-')[0]
    if head in BRIEF_L10N:
        return head
    return 'en'


def join_list(items, lang='en'):
    """按目标语言列举规则连接产品名列表（保留原词，仅用本语言连接词/标点）。"""
    lang = normalize_lang(lang)
    items = [str(x).strip() for x in items if str(x).strip()]
    if len(items) <= 1:
        return items[0] if items else ''
    if lang in ('zh', 'zh-Hant'):
        return '、'.join(items)
    if lang == 'ja':
        return '、'.join(items)
    if lang == 'ko':
        return '·'.join(items)
    if lang == 'ar':
        return ' و '.join(items)
    if lang == 'ru':
        if len(items) == 2:
            return items[0] + ' и ' + items[1]
        return ', '.join(items[:-1]) + ' и ' + items[-1]
    conj = {'de': ' und ', 'es': ' y ', 'fr': ' et ', 'pt': ' e '}.get(lang, ' and ')
    if len(items) == 2:
        return items[0] + ' ' + conj.strip() + ' ' + items[1]
    return ', '.join(items[:-1]) + conj + items[-1]
