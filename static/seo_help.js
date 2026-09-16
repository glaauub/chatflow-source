/* SEO 帮助文案数据（P3 "SEO 看得懂改造"消费）
 *
 * 用法：admin.html 中目标输入框的 <label> 上标注 data-help-key="<key>"；
 * admin.js initSeoHelp() 扫描后自动在 label 右侧注入 "ⓘ 这是什么" 按钮，
 * 点击展开三段：这是什么 / 为什么重要 / 怎么写（示例）。
 *
 * 覆盖字段：方案评审文档 §3.2.1 的 14 个 SEO/GEO 输入字段。
 * 后台面向中文操作者，首版帮助文案为简体中文；示例文案按站点语言 en/zh。
 * how 字段中的换行使用 JS \n 转义，渲染时会自动转为 <br> 显示多行。
 */
window.SEO_FIELD_HELP = {
  /* ===== 经典 SEO ② 区 ===== */
  seoSiteTitle: {
    what: '网站首页在搜索引擎 / AI 结果里显示的大标题，也是浏览器标签页上的名字。',
    why: '标题是用户和 AI 第一眼看到的内容，直接影响点击与"你这站是卖什么的"判断。建议 30-60 字符，别超过 80。',
    how: '合格：LED Lighting Manufacturer & Supplier - Acme\n不合格：首页 / Welcome / Acme Company（没说清卖什么）',
  },
  seoSiteDescription: {
    what: '搜索结果标题下方那段小字，用来概括网站；没填时系统会自动用公司简介兜底。',
    why: '好的描述让用户和 AI 快速理解"你是谁、做什么、为什么选你"。建议 50-160 字符，过长会被截断。',
    how: '合格：We are a China-based LED factory with 15 years of experience, offering OEM/ODM and fast delivery.\n不合格：空 / 只有一句"我们是好公司"（太泛，说不清主营）',
  },
  seoSiteKeywords: {
    what: '与网站相关的关键词，用英文逗号分隔。',
    why: '仅供整理选题；Google 不用 meta keywords 作为网页排名信号。点"补充关键词"按钮可参考产品与分类自动生成。',
    how: 'LED lighting, LED bulb, LED strip, OEM lighting supplier',
  },
  seoAuthor: {
    what: '网站内容的作者署名（品牌 / 公司名），一般填公司名即可。',
    why: '告诉搜索引擎内容归属，增强站点可信度；不填也不影响正常收录。',
    how: 'Acme Lighting Co., Ltd. 或你的品牌名；不确定可留空。',
  },
  seoRobots: {
    what: '告诉搜索引擎 / AI 爬虫哪些内容可以收录（高级设置）。',
    why: '默认保持空即可，系统会按"允许收录"输出；noindex 会要求搜索引擎不要收录；noai 不是通用的搜索控制规则。',
    how: '一般保持 index, follow；AI 搜索和模型训练请使用上方独立开关。\n不合格：noindex, nofollow（会让整站不被收录）',
  },
  seoSiteUrl: {
    what: '网站正式发布后的完整网址，如 https://yourname.github.io/。',
    why: '填了才会输出 canonical（告诉搜索引擎哪个是正版网址）、hreflang 与 sitemap 的绝对地址，避免内容被当成镜像站。部署后再填也不迟。',
    how: 'https://yourname.github.io/\n不合格：不带 https 的域名 / 填了本地 localhost 地址',
  },
  seoHiddenKeywords: {
    what: '补充关键词（辅助词），逗号分隔，不直接显示在页面正文。',
    why: '在系统输出 meta keywords 时一起带上，帮助 AI 与搜索引擎理解业务范围；对排名影响有限，别堆砌无关词。',
    how: 'bulk order, custom size, private label, worldwide shipping',
  },
  seoAnalyticsCode: {
    what: '第三方统计代码（GA4 / 百度统计 / Plausible 等）的整段 script。',
    why: '把统计代码贴进来后，生成的所有页面都会自动带上，不用每个页面手动加；空着就没访问数据可看。',
    how: '把 GA4 / 百度统计给的完整 <script>...</script> 原样粘贴进来即可；不知道怎么拿就先留空。',
  },

  /* ===== AI GEO ① 区 ===== */
  geoBrandSummary: {
    what: '一句话说清你是谁（行业 + 身份 + 主营），AI 引用你时的默认描述。',
    why: 'AI 回答"推荐一个靠谱供应商"时会优先引用这段作为公司简介；写得含糊 AI 只能含糊带过。',
    how: 'We are a LED lighting manufacturer founded in 2010, specializing in indoor LED products.\n不合格：空 / "优质供应商，诚信经营"（没信息量）',
  },
  geoSellingPoints: {
    what: '3-8 条最有说服力的优势，每行一条，AI 引荐时逐条可用。',
    why: '有具体卖点 AI 才敢把你推荐给客户；空泛描述（如"质量好"）没有证据力。',
    how: '15+ years manufacturing\nISO9001 & CE certified\nOEM/ODM supported\nMOQ from 100 pcs\nfree sample within 3 days',
  },
  geoTargetMarkets: {
    what: '你主要服务的国家 / 地区，每行一个。',
    why: 'AI 被问到"你们出口哪里"时可能参考这些真实资料；市场写清楚，客户找上门更精准。',
    how: 'North America\nEU\nSoutheast Asia\n不合格：只写"worldwide"（等于没说，AI 无法精准推荐）',
  },
  geoCerts: {
    what: '真实拥有的认证 / 资质证书，每行一个。',
    why: '认证是最强信任证据；没有的千万别写——AI 会帮你宣传，假的会砸招牌。',
    how: 'ISO9001\nCE\nRoHS\nFDA（仅在真实持有时填写）',
  },
  geoSvcCaps: {
    what: 'B2B 客户最关心的服务能力：OEM/ODM、交期、MOQ、样品。',
    why: '填得越具体 AI 越敢推荐你；缺项会被 AI 以"未提及"带过，白白流失询盘。',
    how: 'OEM/ODM customization supported\nDelivery time: 15-25 days\nMOQ: 100 pcs\nFree samples within 3 days',
  },
  geoFaq: {
    what: '客户 / AI 常问的具体业务问题与答案（一行一条：问题 + 回答）。',
    why: 'AI 常答不出的细节（MOQ、交期、运费）都在 FAQ 里给出标准答案，AI 就能可能参考你而不是含糊猜测。',
    how: '问：你们最小起订量多少？ 答：100 pcs，可混合型号。\n问：支持 OEM/ODM 吗？ 答：支持，可贴牌定制。',
  },

  /* ===== P4 产品级 SEO（产品编辑表单折叠区） ===== */
  productMetaTitle: {
    what: '这个产品页面在搜索结果 / 分享卡片里显示的大标题。不填默认用「产品名 - 站点名」。',
    why: '每个产品都值得单独一句吸引人的标题——搜你这款产品的客户看到的就是这行字，写得准点击率更高。',
    how: '合格：LED 100W 工厂直供 - XX 照明（产品词 + 卖点词）\n建议 30-60 字，别超过 80\n不合格：空白（只能显示默认标题）',
  },
  productMetaDesc: {
    what: '搜索结果里标题下面那段小字，相当于产品的一句话简介。不填就用网站整体描述。',
    why: '写清「这是什么产品 + 为什么选你」，客户还没点进来就先被说服；AI 总结产品时也会优先读它。',
    how: '合格（50-160 字）：100W LED 工矿灯，整灯 5 年质保，支持 OEM/ODM，工厂直供 15 天交货。\n不合格：空白，或照抄产品名（信息量不足）',
  },
};
