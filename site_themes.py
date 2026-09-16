# -*- coding: utf-8 -*-
"""外贸一键建站 - 站点模板主题系统（参数化生成 36 套不同 UI/排版风格）

每套模板由一组可组合的设计参数驱动，统一生成完整 CSS：
  - palette : 主色/辅色/背景/卡片/文字/弱化文字/页脚色
  - font    : sans / serif / display / tech（字体栈）
  - nav     : classic(左Logo右导航) / center(居中Logo+下导航) / minimal(细顶条+白底导航)
  - title   : line(渐变下划线) / block(左侧色块) / serif(衬线大字距) / badge(胶囊徽章)
  - card    : rounded(圆角投影) / sharp(直角工业) / minimal(无边框悬浮) / big(大图卡片)
  - btn     : round(圆角) / pill(胶囊) / sharp(直角)
  - tone    : light / dark / tint(浅渐变) / deep(深渐变)

后台选择/预览读取 TEMPLATES 元数据；build_css(tid) 生成全站样式。
"""
import html

# ---------------- 主题参数 ----------------

_THEMES = {
    # ---- 经典三套（id 保持不变，兼容已保存配置）----
    'business': dict(name='简约商务', desc='蓝白配色、现代简洁，适合通用外贸/贸易公司',
                     primary='#1a2a3a', primary2='#243b52', accent='#2f6fed', accent2='#4d8dff',
                     bg='#f5f7fb', card='#ffffff', text='#2b3442', muted='#7c8798', footer='#0e1622',
                     font='sans', nav='classic', title='line', card_style='rounded', btn='round', tone='light',
                     thumb='linear-gradient(135deg,#1a2a3a 0%,#2f6fed 100%)'),
    'industrial': dict(name='工业制造', desc='深灰+橙色工业风，适合机械、五金、设备制造商',
                       primary='#22272e', primary2='#313a44', accent='#f26522', accent2='#ff8a3d',
                       bg='#f1f2f4', card='#ffffff', text='#2a2f36', muted='#7d8690', footer='#14181d',
                       font='sans', nav='classic', title='block', card_style='sharp', btn='sharp', tone='light',
                       thumb='linear-gradient(135deg,#22272e 0%,#f26522 100%)'),
    'luxury': dict(name='时尚轻奢', desc='黑白+金色衬线排版，适合时尚、珠宝、高端消费品',
                   primary='#111111', primary2='#1f1f1f', accent='#b98a2f', accent2='#d9b45c',
                   bg='#faf9f7', card='#ffffff', text='#222222', muted='#8a857c', footer='#0b0b0b',
                   font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                   thumb='linear-gradient(135deg,#111111 0%,#b98a2f 100%)'),

    # ---- 新增 33 套 ----
    'Modern-blue': dict(name='现代科技蓝', desc='亮蓝渐变、轻盈科技感，适合电子、智能硬件、IT 产品',
                        primary='#0b3d91', primary2='#1462ff', accent='#00b4ff', accent2='#3ddcff',
                        bg='#f4f8ff', card='#ffffff', text='#1c2b3a', muted='#74859b', footer='#071a3a',
                        font='sans', nav='classic', title='line', card_style='rounded', btn='round', tone='light',
                        thumb='linear-gradient(135deg,#0b3d91 0%,#00b4ff 100%)'),
    'clean-white': dict(name='极简纯白', desc='大留白纯白风、黑字细线，适合设计、摄影、轻奢小物',
                        primary='#111111', primary2='#333333', accent='#111111', accent2='#444444',
                        bg='#ffffff', card='#ffffff', text='#111111', muted='#999999', footer='#111111',
                        font='sans', nav='minimal', title='line', card_style='minimal', btn='pill', tone='light',
                        thumb='linear-gradient(135deg,#ffffff 0%,#e5e5e5 100%)'),
    'tech-dark': dict(name='深色科技', desc='深蓝黑+青色霓虹，适合智能硬件、安防、机器人',
                      primary='#0b0f1a', primary2='#121a2b', accent='#00e5ff', accent2='#7b61ff',
                      bg='#0b0f1a', card='#151d30', text='#e8eefc', muted='#8fa0bf', footer='#070a12',
                      font='tech', nav='classic', title='line', card_style='rounded', btn='round', tone='dark',
                      thumb='linear-gradient(135deg,#0b0f1a 0%,#00e5ff 100%)'),
    'ocean': dict(name='海洋清新', desc='青蓝水色、清爽透气，适合户外、水处理、渔具',
                  primary='#05526b', primary2='#0a7a96', accent='#17c3b2', accent2='#7ee8d2',
                  bg='#f0fafb', card='#ffffff', text='#1e3a44', muted='#6f8b94', footer='#032f3d',
                  font='sans', nav='center', title='block', card_style='rounded', btn='round', tone='light',
                  thumb='linear-gradient(135deg,#05526b 0%,#17c3b2 100%)'),
    'forest': dict(name='森林绿意', desc='深绿+翠绿自然风，适合家居、木制品、园艺',
                   primary='#123d2a', primary2='#1d5c3f', accent='#2e9e5b', accent2='#7ac96f',
                   bg='#f3f8f2', card='#ffffff', text='#23352b', muted='#71847a', footer='#0a2317',
                   font='sans', nav='classic', title='line', card_style='rounded', btn='round', tone='light',
                   thumb='linear-gradient(135deg,#123d2a 0%,#2e9e5b 100%)'),
    'wine': dict(name='酒红典雅', desc='酒红+金色复古奢华，适合红酒、食品、礼品',
                 primary='#4a1020', primary2='#6b1a30', accent='#c9a227', accent2='#e3c765',
                 bg='#faf6f3', card='#ffffff', text='#33222a', muted='#99817f', footer='#2b0710',
                 font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                 thumb='linear-gradient(135deg,#4a1020 0%,#c9a227 100%)'),
    'gold-black': dict(name='黑金尊贵', desc='深邃黑+金属金，适合手表、眼镜、高端箱包',
                       primary='#0d0d0d', primary2='#1c1a17', accent='#d4af37', accent2='#f0d488',
                       bg='#f6f4ef', card='#ffffff', text='#1e1c18', muted='#8d8778', footer='#080808',
                       font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                       thumb='linear-gradient(135deg,#0d0d0d 0%,#d4af37 100%)'),
    'neon': dict(name='霓虹潮流', desc='深紫+霓虹粉青，适合潮牌、数码配件、电竞周边',
                 primary='#160b2e', primary2='#241248', accent='#ff2fa0', accent2='#00e5ff',
                 bg='#160b2e', card='#221442', text='#f2e9ff', muted='#a88fc9', footer='#0d0520',
                 font='tech', nav='classic', title='line', card_style='rounded', btn='sharp', tone='dark',
                 thumb='linear-gradient(135deg,#160b2e 0%,#ff2fa0 100%)'),
    'pastel': dict(name='马卡龙甜心', desc='浅粉浅蓝马卡龙色，适合饰品、美妆、礼品',
                   primary='#5b6db8', primary2='#7f8fd4', accent='#ff8fb8', accent2='#ffc3d6',
                   bg='#fdf6fb', card='#ffffff', text='#4a4a6a', muted='#a29bb8', footer='#3f4a86',
                   font='sans', nav='center', title='line', card_style='rounded', btn='pill', tone='light',
                   thumb='linear-gradient(135deg,#ffc3d6 0%,#7f8fd4 100%)'),
    'corporate': dict(name='商务稳重', desc='深蓝+灰色商务感，适合 B2B、物流、咨询',
                      primary='#16324f', primary2='#1f4468', accent='#2d7dd2', accent2='#5ba3e8',
                      bg='#f4f6f9', card='#ffffff', text='#22303e', muted='#7b8896', footer='#0c1d30',
                      font='sans', nav='classic', title='block', card_style='rounded', btn='round', tone='light',
                      thumb='linear-gradient(135deg,#16324f 0%,#2d7dd2 100%)'),
    'startup': dict(name='初创活力', desc='紫橙渐变、明快张扬，适合 SaaS、创新消费电子',
                    primary='#3f1d78', primary2='#6b2fa0', accent='#ff6b35', accent2='#ffa24d',
                    bg='#f8f5ff', card='#ffffff', text='#2c2340', muted='#8a80a3', footer='#1d0d3f',
                    font='sans', nav='classic', title='line', card_style='rounded', btn='pill', tone='light',
                    thumb='linear-gradient(135deg,#3f1d78 0%,#ff6b35 100%)'),
    'vintage': dict(name='复古怀旧', desc='米黄+棕褐复古质感，适合手工艺品、古董、茶叶',
                    primary='#4a3423', primary2='#6b4c31', accent='#a9713b', accent2='#c99a5b',
                    bg='#faf4e8', card='#fffaf0', text='#3d2f22', muted='#98866c', footer='#2c1d12',
                    font='serif', nav='center', title='serif', card_style='minimal', btn='sharp', tone='light',
                    thumb='linear-gradient(135deg,#4a3423 0%,#a9713b 100%)'),
    'metro': dict(name='地铁扁平', desc='扁平撞色 UI 风，适合大众消费品、杂货、办公用品',
                  primary='#005eb8', primary2='#1d7fd6', accent='#ffb400', accent2='#ffd23f',
                  bg='#f0f4f8', card='#ffffff', text='#1c2b36', muted='#7c8a96', footer='#003a70',
                  font='sans', nav='minimal', title='block', card_style='sharp', btn='sharp', tone='light',
                  thumb='linear-gradient(135deg,#005eb8 0%,#ffb400 100%)'),
    'material': dict(name='材质设计', desc='Google Material 风格，悬浮阴影+蓝白，适合科技配件',
                     primary='#0f4c81', primary2='#1565c0', accent='#2196f3', accent2='#64b5f6',
                     bg='#f5f7fa', card='#ffffff', text='#21252b', muted='#7d8792', footer='#0b3a63',
                     font='sans', nav='classic', title='line', card_style='rounded', btn='round', tone='light',
                     thumb='linear-gradient(135deg,#0f4c81 0%,#2196f3 100%)'),
    'bold': dict(name='大胆撞色', desc='黑+黄高对比醒目，适合工具、汽配、工业耗材',
                 primary='#141414', primary2='#2a2a2a', accent='#ffd400', accent2='#ffe24d',
                 bg='#f7f7f5', card='#ffffff', text='#1f1f1f', muted='#8a8a8a', footer='#0a0a0a',
                 font='sans', nav='classic', title='block', card_style='sharp', btn='sharp', tone='light',
                 thumb='linear-gradient(135deg,#141414 0%,#ffd400 100%)'),
    'elegant': dict(name='法式优雅', desc='灰白+香槟金低调优雅，适合香水、瓷器、家居饰品',
                    primary='#3d3a36', primary2='#56504a', accent='#b8a077', accent2='#d6c3a0',
                    bg='#f8f7f4', card='#ffffff', text='#35322e', muted='#98928a', footer='#201d1a',
                    font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                    thumb='linear-gradient(135deg,#3d3a36 0%,#b8a077 100%)'),
    'fresh': dict(name='新鲜果蔬', desc='绿橙清新风，适合食品、农产品、健康食材',
                  primary='#2e7d32', primary2='#43a047', accent='#ff8f00', accent2='#ffb300',
                  bg='#f6faf3', card='#ffffff', text='#26432c', muted='#7e9683', footer='#1b4d1f',
                  font='sans', nav='minimal', title='line', card_style='rounded', btn='round', tone='light',
                  thumb='linear-gradient(135deg,#2e7d32 0%,#ff8f00 100%)'),
    'sunset': dict(name='日落暖橙', desc='暖橙渐变落日感，适合运动户外、旅行用品',
                   primary='#b3391f', primary2='#d95b2b', accent='#ff7e3d', accent2='#ffab6b',
                   bg='#fdf6f1', card='#ffffff', text='#3b2a24', muted='#9c857a', footer='#6e1d0c',
                   font='sans', nav='classic', title='line', card_style='rounded', btn='pill', tone='light',
                   thumb='linear-gradient(135deg,#b3391f 0%,#ff7e3d 100%)'),
    'midnight': dict(name='午夜藏青', desc='藏青+金色夜间质感，适合灯具、五金、安防',
                     primary='#101b33', primary2='#1a2a4f', accent='#c9a227', accent2='#e3c765',
                     bg='#f5f6fa', card='#ffffff', text='#222b3d', muted='#7f8aa0', footer='#080f20',
                     font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                     thumb='linear-gradient(135deg,#101b33 0%,#c9a227 100%)'),
    'sand': dict(name='沙漠大地', desc='沙色+棕褐大地感，适合建材、家具、户外工具',
                 primary='#5d4a36', primary2='#7a6245', accent='#c87f3d', accent2='#e0a569',
                 bg='#f8f3ea', card='#fffcf6', text='#3c3228', muted='#998873', footer='#33261a',
                 font='sans', nav='center', title='block', card_style='sharp', btn='sharp', tone='light',
                 thumb='linear-gradient(135deg,#5d4a36 0%,#c87f3d 100%)'),
    'royal': dict(name='皇家宝蓝', desc='宝蓝+金色皇家气质，适合珠宝、钟表、高端礼盒',
                  primary='#0a2a6b', primary2='#12409f', accent='#d4af37', accent2='#f0d488',
                  bg='#f7f8fc', card='#ffffff', text='#1d2742', muted='#7c86a3', footer='#051a4a',
                  font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                  thumb='linear-gradient(135deg,#0a2a6b 0%,#d4af37 100%)'),
    'steel': dict(name='钢铁灰蓝', desc='冷灰+钢蓝工业理性，适合机械零件、模具、装备',
                  primary='#2f3b4a', primary2='#40546b', accent='#4a90d9', accent2='#7bb3ee',
                  bg='#f2f4f7', card='#ffffff', text='#2b3340', muted='#7e8894', footer='#1b232e',
                  font='sans', nav='classic', title='block', card_style='sharp', btn='sharp', tone='light',
                  thumb='linear-gradient(135deg,#2f3b4a 0%,#4a90d9 100%)'),
    'berry': dict(name='莓果紫红', desc='紫红+粉色甜酷风，适合美妆、服饰、礼品',
                  primary='#6d1f44', primary2='#932a5e', accent='#e0408c', accent2='#f78fb3',
                  bg='#fdf4f8', card='#ffffff', text='#43243a', muted='#a08193', footer='#3f0f26',
                  font='sans', nav='minimal', title='line', card_style='rounded', btn='pill', tone='light',
                  thumb='linear-gradient(135deg,#6d1f44 0%,#e0408c 100%)'),
    'slate': dict(name='板岩深青', desc='深灰+青绿克制冷静，适合环保、水处理、节能设备',
                  primary='#26333b', primary2='#35484f', accent='#2a9d8f', accent2='#5bc0b0',
                  bg='#f3f6f6', card='#ffffff', text='#253238', muted='#7b8a8f', footer='#131c20',
                  font='sans', nav='classic', title='line', card_style='rounded', btn='round', tone='light',
                  thumb='linear-gradient(135deg,#26333b 0%,#2a9d8f 100%)'),
    'amber': dict(name='琥珀暖棕', desc='深棕+琥珀光感，适合咖啡、茶叶、木艺、香薰',
                  primary='#3c2313', primary2='#5a3719', accent='#d08a2e', accent2='#eab25c',
                  bg='#faf5ec', card='#fffdf7', text='#38291c', muted='#98806a', footer='#20120a',
                  font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                  thumb='linear-gradient(135deg,#3c2313 0%,#d08a2e 100%)'),
    'rose': dict(name='玫瑰金', desc='白+玫瑰金柔美质感，适合美妆、珠宝、时尚配饰',
                 primary='#4a2536', primary2='#6d3a50', accent='#d8a0a8', accent2='#eec0c6',
                 bg='#fdf9f9', card='#ffffff', text='#412d35', muted='#a1888f', footer='#2c131d',
                 font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                 thumb='linear-gradient(135deg,#4a2536 0%,#d8a0a8 100%)'),
    'ivory': dict(name='象牙白', desc='米白+墨绿复古书卷气，适合茶叶、书籍、文创',
                  primary='#274d3e', primary2='#386b58', accent='#a8b88f', accent2='#c9d6b3',
                  bg='#fbfaf5', card='#ffffff', text='#2d3a33', muted='#8d9a8e', footer='#142c22',
                  font='serif', nav='center', title='serif', card_style='minimal', btn='pill', tone='light',
                  thumb='linear-gradient(135deg,#274d3e 0%,#a8b88f 100%)'),
    'graphite': dict(name='石墨绿调', desc='石墨灰+荧光绿，适合能源、新能源、工业科技',
                     primary='#1f232b', primary2='#2e3540', accent='#7ee081', accent2='#a9f2ab',
                     bg='#f3f4f6', card='#ffffff', text='#262b33', muted='#7d8692', footer='#11141a',
                     font='sans', nav='classic', title='block', card_style='sharp', btn='round', tone='light',
                     thumb='linear-gradient(135deg,#1f232b 0%,#7ee081 100%)'),
    'azure': dict(name='晴空天蓝', desc='浅天蓝+深蓝清透，适合日用百货、母婴、家居',
                  primary='#1663a8', primary2='#2b82d4', accent='#38b6ff', accent2='#7ed2ff',
                  bg='#f4f9fe', card='#ffffff', text='#20364a', muted='#7e93a8', footer='#0c3a63',
                  font='sans', nav='minimal', title='line', card_style='rounded', btn='round', tone='light',
                  thumb='linear-gradient(135deg,#1663a8 0%,#38b6ff 100%)'),
    'terra': dict(name='陶土红棕', desc='陶土红+米色手工感，适合陶瓷、手工艺、家居装饰',
                  primary='#8a3d24', primary2='#a85032', accent='#d27a4e', accent2='#e8a37e',
                  bg='#f9f4ee', card='#fffdfa', text='#3c2c25', muted='#9a857a', footer='#4d1f10',
                  font='sans', nav='center', title='block', card_style='sharp', btn='sharp', tone='light',
                  thumb='linear-gradient(135deg,#8a3d24 0%,#d27a4e 100%)'),
    'denim': dict(name='牛仔蓝调', desc='牛仔蓝+橙扣粗犷风，适合箱包、服饰、户外装备',
                  primary='#1d4e89', primary2='#2a67ab', accent='#f5a623', accent2='#ffc25e',
                  bg='#f4f7fb', card='#ffffff', text='#223348', muted='#7c8ca0', footer='#0e2b4f',
                  font='sans', nav='classic', title='line', card_style='rounded', btn='round', tone='light',
                  thumb='linear-gradient(135deg,#1d4e89 0%,#f5a623 100%)'),
    'crimson': dict(name='绯红力量', desc='暗红+白高气场，适合运动、服饰、品牌周边',
                    primary='#5e1424', primary2='#7d1f33', accent='#d02c3f', accent2='#f06a75',
                    bg='#faf4f4', card='#ffffff', text='#36232a', muted='#9a7f85', footer='#330a12',
                    font='sans', nav='classic', title='block', card_style='sharp', btn='sharp', tone='light',
                    thumb='linear-gradient(135deg,#5e1424 0%,#d02c3f 100%)'),
    'mint': dict(name='薄荷清新', desc='白+薄荷绿清爽护理感，适合美妆、日化、保健品',
                 primary='#1f5c4d', primary2='#2f7d6b', accent='#3ec9a7', accent2='#7fe3c8',
                 bg='#f4fbf9', card='#ffffff', text='#234038', muted='#7d9a92', footer='#0e3329',
                 font='sans', nav='minimal', title='line', card_style='rounded', btn='pill', tone='light',
                 thumb='linear-gradient(135deg,#1f5c4d 0%,#3ec9a7 100%)'),

    # ---- HLURU 工厂批发模板（仿 cn.Modern/Modern.com 官方站）----
    # 配色：深蓝主色（信任）+ 蓝紫渐变 + 橙金 accent（温暖）
    # nav='mega'：5 项顶级 + Products hover 下拉 3 列分类 + CTA 列
    # 含 brand-hero 大字 / trust-strip 资质横条 / bf-summary 侧栏 + bf-grid 卡片 / 4 列全宽 footer
    'modern': dict(name='Modern Business 现代商务', desc='深蓝+橙金厂家批发站。mega menu 分类、brand-hero 大字、bf-summary 卡片、4 列全宽 footer。适合乐器/乐器/批发/工厂出口',
                  primary='#0e1622', primary2='#1a2a3a', accent='#2f6fed', accent2='#5b8def',
                  bg='#f7f9fc', card='#ffffff', text='#1a2a3a', muted='#5b6573', footer='#0e1622',
                  font='sans', nav='mega', title='line', card_style='rounded', btn='round', tone='light',
                  thumb='linear-gradient(135deg,#0e1622 0%,#2f6fed 50%,#f0a63c 100%)'),
}


# ---------------- 模板元数据（后台渲染用） ----------------

TEMPLATES = []
for _tid, _t in _THEMES.items():
    TEMPLATES.append({
        'id': _tid,
        'name': _t['name'],
        'desc': _t['desc'],
        'primary': _t['primary'],
        'accent': _t['accent'],
        'thumb': _t['thumb'],
    })


def get_template(tid):
    for t in TEMPLATES:
        if t['id'] == tid:
            return t
    return TEMPLATES[0]


def _font_stack(font):
    if font == 'serif':
        return ('Georgia, "Times New Roman", "Songti SC", "SimSun", serif')
    if font == 'tech':
        return ('-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", '
                '"Helvetica Neue", Arial, sans-serif')
    return ('-apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", Arial, sans-serif')


def _nav_css(t, radius):
    """导航变体样式（classic 左Logo右导航 / center 居中Logo+下导航 / minimal 细顶条白底导航）"""
    base = 'position: sticky; top: 0; z-index: 50;'
    nav = t['nav']
    R = lambda s: s.replace('P1', t['primary']).replace('P2', t['primary2']).replace('AC', t['accent']).replace('TX', t['text']).replace('MU', t['muted']).replace('RD', radius).replace('CD', t['card'])
    if nav == 'center':
        s = []
        s.append(R('.site-header{background:CD;border-bottom:2px solid AC;box-shadow:0 2px 10px rgba(0,0,0,.05);' + base + '}'))
        s.append('.site-header .container{display:flex;flex-direction:column;align-items:center;padding-top:14px;padding-bottom:0;}')
        s.append(R('.logo{color:TX;font-size:24px;font-weight:800;letter-spacing:2px;display:flex;align-items:center;gap:10px;padding-bottom:12px;}'))
        s.append(R('.logo-badge{width:32px;height:32px;border-radius:50%;background:AC;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:16px;}'))
        s.append('.logo-img{max-height:52px;width:auto;display:block;}')
        s.append('.main-nav{display:flex;gap:2px;margin-bottom:-2px;}')
        s.append(R('.main-nav a{color:MU;padding:12px 22px;font-size:14px;font-weight:700;letter-spacing:1px;border-bottom:3px solid transparent;transition:all .2s;}'))
        s.append(R('.main-nav a:hover,.main-nav a.active{color:AC;border-bottom-color:AC;background:transparent;}'))
        return '\n'.join(s)
    if nav == 'minimal':
        s = []
        s.append(R('.site-header{background:CD;border-bottom:1px solid rgba(0,0,0,.06);' + base + '}'))
        s.append('.site-header .container{display:flex;align-items:center;justify-content:space-between;height:68px;}')
        s.append(R('.logo{color:TX;font-size:20px;font-weight:800;letter-spacing:1px;display:flex;align-items:center;gap:10px;}'))
        s.append(R('.logo-badge{width:30px;height:30px;border-radius:RD;background:AC;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:16px;}'))
        s.append('.logo-img{max-height:46px;width:auto;display:block;}')
        s.append('.main-nav{display:flex;gap:4px;}')
        s.append(R('.main-nav a{color:MU;padding:8px 16px;border-radius:RD;font-size:14px;font-weight:600;transition:all .2s;}'))
        s.append(R('.main-nav a:hover,.main-nav a.active{color:AC;background:rgba(0,0,0,.04);}'))
        return '\n'.join(s)
    if nav == 'mega':
        # HLURU 风格：深蓝头部 + 5 项顶级 + Products hover mega menu（仿 cn.Modern/Modern.com）
        s = []
        s.append(R('.site-header{background:linear-gradient(135deg,P1,P2);' + base + '}'))
        s.append('.site-header .container{display:flex;align-items:center;justify-content:space-between;height:74px;}')
        s.append('.logo{color:#fff;font-size:26px;font-weight:800;letter-spacing:.5px;display:flex;align-items:center;gap:12px;font-family:Georgia,serif;background:linear-gradient(135deg,#ffffff 0%,#c9d6e4 60%,#5b8def 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}')
        s.append('.logo-img{height:40px;width:auto;display:block;filter:drop-shadow(0 1px 2px rgba(0,0,0,.25));}')
        s.append('.site-header .logo{background:none;-webkit-text-fill-color:initial;}')
        s.append('.main-nav-list{list-style:none;display:flex;align-items:center;gap:4px;margin:0;padding:0;}')
        s.append('.main-nav-list > li{position:relative;}')
        s.append('.main-nav-list > li > a{display:block;padding:10px 16px;font-size:14px;font-weight:600;color:rgba(255,255,255,.85);text-decoration:none;border-radius:6px;transition:color .15s,background .15s;}')
        s.append('.main-nav-list > li > a:hover{color:#fff;background:rgba(255,255,255,.08);}')
        s.append('.main-nav-list > li > a.active{color:#fff;background:rgba(255,255,255,.1);}')
        s.append('.nav-caret{font-size:9px;opacity:.7;margin-left:3px;}')
        # hover 桥接：父元素扩展 hover 区填补 menu 上方 14px 间隙（关键！避免菜单闪烁）
        s.append('.has-mega{padding-bottom:14px;margin-bottom:-14px;}')
        s.append('.has-mega > .mega-menu{position:absolute;top:100%;left:50%;transform:translateX(-58%) translateY(-6px);min-width:720px;background:#fff;border:1px solid #e6ecf5;border-radius:12px;box-shadow:0 18px 50px rgba(15,30,60,.15);padding:22px 24px;display:none;grid-template-columns:1fr 1fr 1fr 1.1fr;gap:24px;z-index:99;}')
        s.append('.has-mega:hover > .mega-menu{display:grid;animation:megaIn .15s ease-out;}')
        s.append('@keyframes megaIn{from{opacity:0;transform:translateX(-58%) translateY(-12px);}to{opacity:1;transform:translateX(-58%) translateY(0);}}')
        s.append('.mega-col h5{font-size:11.5px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:AC;margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid #eef2f8;}'.replace('AC', t['accent']))
        s.append('.mega-col ul{list-style:none;margin:0;padding:0;}.mega-col li{margin:0 0 7px;}.mega-col a{font-size:13px;color:#33404f;text-decoration:none;display:block;padding:4px 0;transition:color .15s,padding-left .15s;}.mega-col a:hover{color:AC;padding-left:4px;}'.replace('AC', t['accent']))
        s.append('.mega-cta{background:linear-gradient(135deg,#f7f9fc 0%,#eef4ff 100%);border-radius:10px;padding:18px 18px 16px;}')
        s.append('.mega-cta-title{font-size:13.5px;font-weight:700;color:#1a2a3a;margin:0 0 6px;line-height:1.4;}.mega-cta-sub{font-size:12px;color:#5b6573;margin:0 0 12px;line-height:1.5;}')
        s.append('.mega-cta-btn{display:inline-block;background:AC;color:#fff;border-radius:6px;padding:8px 14px;font-size:12.5px;font-weight:700;text-decoration:none;}.mega-cta-btn:hover{background:P2;}'.replace('AC', t['accent']).replace('P2', t['primary2']))
        s.append('@media (max-width:920px){.main-nav-list{gap:0;}.main-nav-list > li > a{padding:10px 12px;font-size:13px;}.has-mega > .mega-menu{min-width:auto;left:0;transform:none;grid-template-columns:1fr 1fr;padding:18px 16px;}.has-mega:hover > .mega-menu{transform:none;}.mega-col.mega-cta{grid-column:1/-1;}}')
        s.append('@media (max-width:640px){.main-nav-list{flex-wrap:wrap;gap:2px;}.main-nav-list > li > a{padding:8px;font-size:12px;}.has-mega > .mega-menu{position:static;transform:none;display:none;}.has-mega.open > .mega-menu{display:grid;}}')
        return '\n'.join(s)
    # classic
    s = []
    s.append(R('.site-header{background:linear-gradient(135deg,P1,P2);' + base + '}'))
    s.append('.site-header .container{display:flex;align-items:center;justify-content:space-between;height:64px;}')
    s.append('.logo{color:#fff;font-size:21px;font-weight:800;letter-spacing:1px;display:flex;align-items:center;gap:10px;}')
    s.append(R('.logo-badge{width:30px;height:30px;border-radius:RD;background:AC;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:16px;}'))
    s.append('.logo-img{max-height:44px;width:auto;display:block;border-radius:4px;}')
    s.append('.main-nav{display:flex;gap:6px;}')
    s.append(R('.main-nav a{color:rgba(255,255,255,.82);padding:8px 16px;border-radius:RD;font-size:14px;font-weight:600;transition:all .2s;}'))
    s.append('.main-nav a:hover,.main-nav a.active{color:#fff;background:rgba(255,255,255,.14);}')
    return '\n'.join(s)




def _title_css(t):
    """区块标题装饰变体"""
    style = t['title']
    common = '.section-title{font-size:30px;font-weight:800;margin-bottom:8px;color:%s;}\n.section-title .accent{color:%s;}\n' % (t['primary'] if t['tone'] != 'dark' else '#ffffff', t['accent'])
    sub = '.section-sub{color:%s;margin-bottom:40px;font-size:15px;}\n' % t['muted']
    if style == 'block':
        return common + sub + (
            '.section-title{display:inline-flex;align-items:center;gap:12px;}\n'
            '.section-title:before{content:"";display:inline-block;width:6px;height:26px;background:%(accent)s;border-radius:3px;}\n'
            '.section{text-align:center;}\n'
        ) % t
    if style == 'serif':
        return common + sub + (
            '.section-title{font-family:%(font)s;font-weight:600;letter-spacing:4px;text-transform:uppercase;font-size:26px;}\n'
            '.section-title:after{content:"";display:block;width:56px;height:2px;background:%(accent)s;margin:10px auto 0;}\n'
            '.section{text-align:center;}\n'
        ) % dict(font=_font_stack(t['font']), accent=t['accent'])
    if style == 'badge':
        return common + sub + (
            '.section-title{display:inline-flex;align-items:center;gap:10px;padding:8px 22px;border-radius:40px;background:rgba(0,0,0,.05);border:1px solid rgba(0,0,0,.06);}\n'
            '.section{text-align:center;}\n'
        )
    # line
    return common + sub + (
        '.section-title{display:inline-block;}\n'
        '.section-title:after{content:"";display:block;width:64px;height:4px;border-radius:2px;background:linear-gradient(90deg,%(accent)s,%(accent2)s);margin:10px auto 0;}\n'
        '.section{text-align:center;}\n'
    ) % t


def _card_css(t, radius):
    """产品卡片变体"""
    style = t.get('card_style', 'rounded')
    accent, accent2 = t['accent'], t['accent2']
    if style == 'sharp':
        return (
            '.product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:24px;}\n'
            '.product-card{background:%(card)s;border:1px solid #e3e6ea;border-radius:2px;overflow:hidden;transition:box-shadow .25s,transform .25s;display:flex;flex-direction:column;}\n'
            '.product-card:hover{box-shadow:0 10px 26px rgba(0,0,0,.14);transform:translateY(-4px);}\n'
            '.product-img{height:230px;background:#edf0f3;overflow:hidden;position:relative;}\n'
            '.product-img img{width:100%%;height:100%%;object-fit:cover;display:block;transition:transform .4s;}\n'
            '.product-card:hover .product-img img{transform:scale(1.05);}\n'
            '.product-body{padding:16px;display:flex;flex-direction:column;flex:1;}\n'
            '.product-name{font-size:16px;font-weight:700;margin-bottom:6px;color:%(text)s;}\n'
            '.product-name:hover{color:%(accent)s;}\n'
            '.product-price{color:%(accent)s;font-size:21px;font-weight:800;margin-top:2px;}\n'
            '.product-spec{color:%(muted)s;font-size:13px;margin-top:4px;flex:1;}\n'
            '.product-actions{display:flex;gap:8px;margin-top:14px;}\n'
        ) % dict(card=t['card'], accent=accent, text=t['text'], muted=t['muted'])
    if style == 'minimal':
        return (
            '.product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:34px;}\n'
            '.product-card{background:transparent;overflow:hidden;transition:opacity .25s;display:flex;flex-direction:column;}\n'
            '.product-card:hover{opacity:.88;}\n'
            '.product-img{height:280px;background:#f0eee9;overflow:hidden;position:relative;}\n'
            '.product-img img{width:100%%;height:100%%;object-fit:cover;display:block;}\n'
            '.product-body{padding:16px 4px 0;display:flex;flex-direction:column;flex:1;}\n'
            '.product-name{font-family:%(font)s;font-size:16px;font-weight:600;letter-spacing:1px;margin-bottom:6px;color:%(text)s;text-transform:uppercase;}\n'
            '.product-name:hover{color:%(accent)s;}\n'
            '.product-price{color:%(accent)s;font-size:20px;font-weight:700;margin-top:2px;}\n'
            '.product-spec{color:%(muted)s;font-size:13px;margin-top:4px;flex:1;}\n'
            '.product-actions{display:flex;gap:8px;margin-top:14px;}\n'
        ) % dict(font=_font_stack(t['font']), accent=accent, text=t['text'], muted=t['muted'])
    return (
        '.product-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:26px;}\n'
        '.product-card{background:%(card)s;border-radius:%(radius)s;overflow:hidden;box-shadow:0 6px 20px rgba(20,40,80,.08);transition:transform .25s,box-shadow .25s;display:flex;flex-direction:column;}\n'
        '.product-card:hover{transform:translateY(-6px);box-shadow:0 14px 34px rgba(20,40,80,.16);}\n'
        '.product-img{height:230px;background:#eef1f6;overflow:hidden;position:relative;}\n'
        '.product-img img{width:100%%;height:100%%;object-fit:cover;display:block;transition:transform .4s;}\n'
        '.product-card:hover .product-img img{transform:scale(1.05);}\n'
        '.product-body{padding:18px;display:flex;flex-direction:column;flex:1;}\n'
        '.product-name{font-size:17px;font-weight:700;margin-bottom:6px;color:%(text)s;}\n'
        '.product-name:hover{color:%(accent)s;}\n'
        '.product-price{color:%(accent)s;font-size:22px;font-weight:800;margin-top:2px;}\n'
        '.product-spec{color:%(muted)s;font-size:13px;margin-top:4px;flex:1;}\n'
        '.product-actions{display:flex;gap:8px;margin-top:14px;}\n'
    ) % dict(card=t['card'], radius=radius, accent=accent, text=t['text'], muted=t['muted'])


def _btn_css(t, radius):
    style = t['btn']
    r = radius if style == 'round' else ('40px' if style == 'pill' else '3px')
    accent, accent2 = t['accent'], t['accent2']
    on_accent = '#ffffff' if t['tone'] != 'dark' else '#111111'
    R = lambda s: s.replace('AC', accent).replace('AC2', accent2).replace('ON', on_accent).replace('RD', r)
    s = []
    s.append(R('.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:RD;font-weight:700;font-size:14px;padding:10px 18px;border:none;cursor:pointer;transition:all .2s;}'))
    s.append(R('.btn-primary{background:AC;color:ON;}'))
    s.append(R('.btn-primary:hover{background:AC2;}'))
    s.append(R('.btn-outline{background:transparent;color:AC;border:1.5px solid AC;}'))
    s.append(R('.btn-outline:hover{background:AC;color:ON;}'))
    s.append(R('.btn-pay{background:#ffb400;color:#1a1a1a;width:100%;margin-top:14px;font-size:15px;padding:12px;border-radius:RD;}'))
    s.append('.btn-pay:hover{background:#f0a800;}')
    return '\n'.join(s)


def build_css(tid):
    """生成指定模板的完整站点 CSS（首页+详情页+联系页）"""
    t = _THEMES.get(tid) or _THEMES['business']
    tid = tid or 'business'
    radius = '14px' if t.get('card_style') == 'rounded' else ('2px' if t.get('card_style') == 'sharp' else '0')
    tone = t['tone']
    bg = t['bg']
    text = t['text']
    muted = t['muted']
    card = t['card']
    accent = t['accent']
    primary = t['primary']
    primary2 = t.get('primary2') or accent
    font = _font_stack(t['font'])
    body_bg = bg
    css = []
    css.append('/* ===== Template: %s ===== */' % t['name'])
    css.append(''':root {
  --primary: %(primary)s; --accent: %(accent)s; --accent2: %(accent2)s;
  --bg: %(bg)s; --card: %(card)s; --text: %(text)s; --muted: %(muted)s;
  --font: %(font)s;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { font-family: var(--font); background: %(bg)s; color: %(text)s; line-height: 1.65; }
.container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
a { text-decoration: none; }
img { max-width: 100%%; }
.text-muted { color: %(muted)s; }
''' % dict(primary=primary, accent=accent, accent2=t['accent2'], bg=body_bg, card=card, text=text, muted=muted, font=font))
    css.append(_nav_css(t, radius))
    css.append('''
.banner-slider { position: relative; width: 100%%; overflow: hidden; height: 560px; }
.slide { position: absolute; top: 0; left: 0; width: 100%%; height: 100%%; opacity: 0; transition: opacity .8s ease; z-index: 1; }
.slide.active { opacity: 1; z-index: 2; }
.slide img { width: 100%%; height: 100%%; object-fit: cover; display: block; }
.banner-placeholder { height: 560px; display: flex; align-items: center; justify-content: center; color: #9fb3c8; font-size: 20px; background: linear-gradient(135deg, %(primary)s, %(primary2)s); }
@media (max-width: 768px) { .banner-slider { height: 320px; } .slide img, .banner-placeholder { height: 320px; } }
''' % t)
    css.append('.section { padding: 64px 0; }')
    css.append(_title_css(t))
    css.append(_card_css(t, radius))
    css.append(_btn_css(t, radius))
    css.append('''
.badge-cat { display: inline-block; background: %(accent)s; color: #fff; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.stock-tag { display: inline-block; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
.stock-tag.in-stock { background: #e6f6ec; color: #1e9e5a; }
.stock-tag.out-stock { background: #fdeaea; color: #d64545; }
.product-meta { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
''' % t)
    css.append('''
/* 支付方式纯展示徽章（不可点击） */
.pay-badges { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0; }
.pay-badges-title { font-size: 12px; font-weight: 700; color: %(muted)s; margin-right: 2px; letter-spacing: .3px; }
.pm { display: inline-flex; align-items: center; gap: 5px; height: 24px; padding: 0 9px; border-radius: 6px; background: #fff; border: 1px solid #e2e7ee; box-sizing: border-box; font-size: 12px; line-height: 1; white-space: nowrap; box-shadow: 0 1px 2px rgba(16,24,40,.04); }
.pm .pm-name { font-weight: 700; color: var(--pmc, #3a4556); letter-spacing: .1px; }
.pm.pm-img { height: 26px; padding: 3px 8px 3px 5px; }
.pm img.pm-ico { height: 18px; width: auto; max-width: 70px; object-fit: contain; display: inline-block; }
.pm.pm-more { background: #f4f6f9; border-style: dashed; border-color: #cdd5df; color: #5a6577; font-weight: 700; }
/* 产品卡内紧凑支付区：独立小区域，不参与按钮布局，不撑大 View Detail */
.pay-mini { margin-top: 12px; padding-top: 10px; border-top: 1px dashed rgba(127,136,151,.22); }
.pay-mini .pay-badges { gap: 5px; }
.pay-mini .pm { height: 22px; padding: 0 7px; font-size: 11px; border-radius: 5px; }
.pay-mini .pm .pm-name { font-weight: 700; }
/* 系统内置官方品牌 logo 图标：去除白底 pill 外框，让品牌 logo 自身完整展示（真实 SVG 文件资源） */
.pm.pm-svg { height: 26px; background: transparent; border: none; box-shadow: none; padding: 0 2px; }
.pm.pm-svg img.pm-logo { height: 22px; width: auto; max-width: 96px; object-fit: contain; display: block; filter: none; }
.pay-mini .pm.pm-svg { height: 22px; padding: 0; }
.pay-mini .pm.pm-svg img.pm-logo { height: 18px; max-width: 80px; }
.pay-panel .pay-badges { margin-top: 2px; }
''' % t)
    # Gallery section (作品画廊板块)
    css.append('''
.gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
.gallery-item { position: relative; border-radius: 10px; overflow: hidden; box-shadow: 0 6px 18px rgba(0,0,0,.08); background: %(card)s; }
.gallery-link { display: block; }
.gallery-item img { width: 100%%; height: 200px; object-fit: cover; display: block; transition: transform .3s ease; }
.gallery-item:hover img { transform: scale(1.04); }
.gallery-cap { position: absolute; left: 0; right: 0; bottom: 0; padding: 8px 10px; font-size: 12px; background: rgba(0,0,0,.5); color: #fff; text-align: center; }
@media (max-width: 640px) { .gallery-grid { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; } .gallery-item img { height: 140px; } }
''' % t)
    # Contact section
    css.append('''
.contact-section { background: linear-gradient(135deg, %(primary)s, %(primary2)s); padding: 64px 0; }
.contact-section .section-title { color: #fff; }
.contact-section .section-sub { color: rgba(255,255,255,.65); }
.contact-list { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.contact-btn { display: inline-flex; align-items: center; gap: 8px; background: #fff; color: %(primary)s; padding: 13px 26px; border-radius: 40px; font-size: 15px; font-weight: 700; box-shadow: 0 4px 14px rgba(0,0,0,.2); transition: all .2s; cursor: pointer; }
.contact-btn:hover { background: %(accent)s; color: #fff; transform: translateY(-2px); }
.contact-icon { font-size: 18px; }
''' % t)

    # 统一联系方式直达区（深色 contact-section 内用浅色透明 pill）
    css.append('''
/* ---------- 统一联系方式渠道（首页/详情/联系页共用） ---------- */
.cc-badge { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; min-width: 30px; border-radius: 50%%; background: var(--ccb, #5b6572); color: #fff; font-size: 11px; font-weight: 800; letter-spacing: -.2px; line-height: 1; box-shadow: inset 0 -1px 0 rgba(0,0,0,.18); }
.cc-badge svg { display: block; }
.cc-pills { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; align-items: center; margin-top: 6px; }
.cc-pill { display: inline-flex; align-items: center; gap: 8px; border: none; background: rgba(255,255,255,.13); color: #fff; padding: 8px 18px 8px 8px; border-radius: 40px; font-size: 14px; font-weight: 700; text-decoration: none; box-shadow: 0 3px 10px rgba(0,0,0,.16); cursor: pointer; transition: all .18s; font-family: inherit; }
.cc-pill .cc-badge { width: 26px; height: 26px; min-width: 26px; font-size: 10px; }
.cc-pill:hover { transform: translateY(-2px); background: var(--ccb, #5b6572); color: #fff; }
.cc-pill-copy:hover, .cc-pill-text:hover { background: rgba(255,255,255,.22); transform: none; cursor: default; }
.cc-pill-copy:hover { cursor: pointer; background: var(--ccb, #5b6572); }
/* 卡片式（联系页/详情页浅色背景用） */
.cc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(248px, 1fr)); gap: 14px; }
.cc-grid-compact { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.cc-item { display: flex; align-items: center; gap: 12px; background: %(card)s; border: 1px solid rgba(0,0,0,.06); border-radius: 14px; padding: 13px 14px; box-shadow: 0 3px 12px rgba(0,0,0,.05); transition: transform .18s, box-shadow .18s; }
.cc-item:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,.08); }
.cc-item .cc-badge { width: 42px; height: 42px; min-width: 42px; font-size: 14px; flex-shrink: 0; }
.cc-meta { display: flex; flex-direction: column; min-width: 0; flex: 1; }
.cc-name { font-size: 14px; font-weight: 800; color: %(primary)s; }
.cc-val { font-size: 12px; color: %(muted)s; word-break: break-all; margin-top: 2px; line-height: 1.35; }
.cc-go { display: inline-flex; align-items: center; gap: 5px; background: var(--ccb, %(primary)s); color: #fff; border: none; border-radius: 8px; padding: 7px 12px; font-size: 12px; font-weight: 700; text-decoration: none; cursor: pointer; font-family: inherit; flex-shrink: 0; transition: filter .15s, transform .15s; }
.cc-go:hover { filter: brightness(1.08); transform: translateY(-1px); color: #fff; }
.cc-go .cc-go-ic { font-size: 11px; }
.cc-go-copy { background: #5b6572; }
.cc-text { font-size: 12px; color: %(muted)s; word-break: break-all; max-width: 110px; text-align: right; }
@media (max-width: 560px) {
  .cc-grid { grid-template-columns: 1fr; }
  .cc-grid-compact { grid-template-columns: 1fr; }
  .cc-item { padding: 11px 12px; }
  .cc-go { padding: 6px 10px; }
}
/* 联系页浅色卡片内 cc-grid 适配 */
.contact-page .cc-grid { margin-top: 8px; }
.cc-go[href^="http"] { text-decoration: none; }
''' % dict(card=card, primary=primary, muted=muted, bg=bg))

    # Footer
    css.append('''
.site-footer { background: %(footer)s; color: #8ba0b8; text-align: center; padding: 22px 0; font-size: 13px; }
.site-footer a { color: #c9d6e4; }
''' % t)

    # ============ 产品详情页 ============
    css.append('''
/* ---------- Product Detail ---------- */
.detail-wrap { padding: 36px 20px 70px; }
.detail-breadcrumb { font-size: 13px; color: %(muted)s; margin-bottom: 24px; }
.detail-breadcrumb a { color: %(accent)s; }
.detail-grid { display: grid; grid-template-columns: 1.05fr 1fr; gap: 42px; align-items: start; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } }
.detail-img { position: relative; background: %(card)s; border-radius: 18px; overflow: hidden; box-shadow: 0 8px 30px rgba(0,0,0,.08); }
.detail-img .main { width: 100%%; aspect-ratio: 1/1; object-fit: cover; display: block; cursor: zoom-in; }
.thumb-row { display: flex; gap: 10px; padding: 12px; background: rgba(0,0,0,.03); overflow-x: auto; }
.thumb-item { width: 74px; height: 74px; object-fit: cover; border-radius: 10px; cursor: pointer; border: 2px solid transparent; opacity: .72; transition: all .2s; flex-shrink: 0; }
.thumb-item.active, .thumb-item:hover { border-color: %(accent)s; opacity: 1; }
.detail-info h1 { font-size: 30px; font-weight: 800; margin-bottom: 10px; color: %(primary)s; }
.detail-price { font-size: 34px; font-weight: 800; color: %(accent)s; margin-bottom: 6px; }
.detail-price small { font-size: 15px; color: %(muted)s; font-weight: 600; }
.detail-short { color: %(muted)s; margin-bottom: 20px; font-size: 15px; }
.detail-attr { width: 100%%; border-collapse: collapse; margin: 18px 0; font-size: 14px; background: %(card)s; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.05); }
.detail-attr td { padding: 11px 16px; border-bottom: 1px solid rgba(0,0,0,.05); }
.detail-attr tr:last-child td { border-bottom: none; }
.detail-attr .lbl { width: 42%%; color: %(muted)s; font-weight: 600; background: rgba(0,0,0,.025); }
.detail-attr .val { font-weight: 600; color: %(text)s; }
.detail-desc { margin: 20px 0; }
.detail-desc h3, .desc-heading { font-size: 19px; font-weight: 800; color: %(primary)s; margin: 26px 0 12px; padding-left: 12px; border-left: 4px solid %(accent)s; }
.detail-desc .desc-body { color: #3c4654; font-size: 15px; white-space: pre-line; }
.detail-desc .desc-body ul { padding-left: 20px; margin: 8px 0; }
.detail-desc .desc-body li { margin: 5px 0; }
.inquire-box { margin-top: 18px; padding: 20px; border-radius: 16px; background: linear-gradient(135deg, %(primary)s, %(primary2)s); color: #fff; }
.inquire-box h4 { font-size: 18px; margin-bottom: 6px; }
.inquire-box p { font-size: 13px; opacity: .85; margin-bottom: 14px; }
.inquire-box .btn { background: %(accent)s; color: #fff; }
.inquire-actions { display: flex; flex-wrap: wrap; gap: 10px; }
.inquire-actions .contact-btn { background: rgba(255,255,255,.14); color: #fff; box-shadow: none; padding: 9px 16px; font-size: 13px; }
.inquire-actions .contact-btn:hover { background: %(accent)s; }
.related-title { margin: 54px 0 20px; font-size: 22px; font-weight: 800; color: %(primary)s; text-align: center; }
.related-title:after { content: ""; display: block; width: 50px; height: 3px; background: %(accent)s; margin: 8px auto 0; border-radius: 2px; }
/* Lightbox */
.lightbox { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.92); z-index: 999; align-items: center; justify-content: center; cursor: zoom-out; }
.lightbox.show { display: flex; }
.lightbox img { max-width: 92vw; max-height: 88vh; border-radius: 8px; }
''' % t)

    # ============ 联系页 ============
    css.append('''
/* ---------- Contact Page ---------- */
.contact-page { padding: 50px 20px 70px; }
.contact-page-card { max-width: 860px; margin: 0 auto; background: %(card)s; border-radius: 20px; padding: 44px; box-shadow: 0 10px 36px rgba(0,0,0,.08); }
.contact-page-card h1 { font-size: 32px; color: %(primary)s; margin-bottom: 8px; }
.contact-page-card .sub { color: %(muted)s; margin-bottom: 30px; }
.contact-page-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.contact-page-item { display: flex; align-items: center; gap: 14px; background: %(bg)s; border-radius: 14px; padding: 16px; border: 1px solid rgba(0,0,0,.05); transition: all .2s; }
.contact-page-item:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,.08); }
.contact-page-item .ci { width: 44px; height: 44px; border-radius: 50%%; background: %(accent)s; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
.contact-page-item .ct { font-weight: 700; font-size: 14px; color: %(primary)s; }
.contact-page-item .cv { font-size: 13px; color: %(accent)s; word-break: break-all; cursor: pointer; display: block; margin-top: 2px; }
''' % t)

    # ============ 通用工具类 ============
    css.append('''
.empty-tip { text-align: center; color: %(muted)s; padding: 40px 20px; font-size: 15px; }
/* 分类筛选 */
.cat-filter { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-bottom: 28px; }
.cat-filter button { border: 1px solid rgba(0,0,0,.1); background: %(card)s; color: %(muted)s; padding: 7px 18px; border-radius: 30px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all .2s; }
.cat-filter button.active, .cat-filter button:hover { background: %(accent)s; color: #fff; border-color: %(accent)s; }
.product-card.hidden { display: none; }
/* 详情页大按钮 */
.btn-lg { padding: 13px 26px; font-size: 15px; }
/* 信任条 */
.trust-bar { display: flex; flex-wrap: wrap; gap: 14px; margin: 18px 0 6px; }
.trust-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: %(muted)s; background: rgba(0,0,0,.03); padding: 8px 14px; border-radius: 30px; }
.trust-item b { color: %(text)s; }
/* 浮动询盘 */
.float-inquire { position: fixed; right: 22px; bottom: 22px; z-index: 90; display: flex; flex-direction: column; gap: 10px; }
.float-inquire a { display: flex; align-items: center; gap: 8px; background: %(accent)s; color: #fff; padding: 12px 20px; border-radius: 40px; font-weight: 700; font-size: 14px; box-shadow: 0 6px 18px rgba(0,0,0,.22); transition: transform .2s; }
.float-inquire a:hover { transform: translateY(-3px); }
/* 多图主图 */
.product-img { display: block; position: relative; overflow: hidden; }
.product-img .p-img { width: 100%%; aspect-ratio: 1/1; object-fit: cover; display: block; transition: transform .35s; }
.product-img:hover .p-img { transform: scale(1.04); }
.detail-img #mainImg { width: 100%%; aspect-ratio: 1/1; object-fit: cover; display: block; }
/* 详情参数表 */
.detail-spec { margin: 16px 0; background: %(card)s; border-radius: 14px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.05); }
.attr-row { display: flex; padding: 11px 16px; border-bottom: 1px solid rgba(0,0,0,.05); font-size: 14px; }
.attr-row:last-child { border-bottom: none; }
.attr-label { width: 40%%; color: %(muted)s; font-weight: 600; flex-shrink: 0; }
.attr-value { font-weight: 600; color: %(text)s; }
.attr-value.in-stock { color: #1e9e5a; }
.attr-value.out-stock { color: #d64545; }
/* 描述排版 */
.detail-desc p { font-size: 15px; line-height: 1.85; color: %(text)s; margin: 10px 0; }
.detail-desc ul { padding-left: 22px; margin: 10px 0; }
.detail-desc li { font-size: 15px; line-height: 1.9; color: %(text)s; }
.desc-point b { color: %(primary)s; }
/* 支付面板 */
.pay-panel { margin-top: 18px; padding: 20px; border-radius: 16px; background: %(card)s; border: 1px dashed rgba(0,0,0,.12); box-shadow: 0 4px 16px rgba(0,0,0,.05); }
.pay-panel h3 { font-size: 18px; font-weight: 800; color: %(primary)s; margin-bottom: 4px; }
.pay-panel .pay-tip { font-size: 12px; color: %(muted)s; margin-bottom: 12px; }
/* 询盘面板补充 */
.inquire-box .inq-sub { font-size: 14px; opacity: .9; }
.inquire-box .contact-list { margin: 8px 0 4px; }
.inquire-box .inq-more { margin-top: 12px; background: rgba(255,255,255,.16); color: #fff; }
.inquire-box .inq-more:hover { background: %(accent)s; color: #fff; }
/* 联系页联系方式横排 */
/* 联系页 promise 卡片 */
.contact-promise { margin-top: 34px; }
.contact-promise h3 { font-size: 20px; font-weight: 800; color: %(primary)s; margin-bottom: 16px; }
.promise-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 14px; }
.promise-item { background: %(bg)s; border-radius: 14px; padding: 16px; border: 1px solid rgba(0,0,0,.05); text-align: center; }
.promise-item span { font-size: 24px; }
.promise-item b { display: block; margin: 8px 0 4px; color: %(primary)s; font-size: 14px; }
.promise-item p { font-size: 12px; color: %(muted)s; margin: 0; }
''' % dict(muted=muted, card=card, accent=accent, text=text, primary=primary, bg=bg))

    # ============ 板块化系统通用样式 ============
    css.append('''
/* ---------- Blocks / Sections ---------- */
.block { margin: 0; }
.banner-section { position: relative; }
.products-section { background: %(bg)s; }
.about-section { background: %(card)s; }
.about-grid { display: grid; grid-template-columns: 320px 1fr; gap: 44px; align-items: start; }
@media (max-width: 800px) { .about-grid { grid-template-columns: 1fr; } }
.about-media img { width: 100%%; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.1); }
.about-text p { font-size: 15px; color: %(text)s; line-height: 1.9; margin-bottom: 12px; }
.about-facts { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 18px; }
.about-fact { background: %(bg)s; border: 1px solid rgba(0,0,0,.05); border-radius: 12px; padding: 12px 16px; min-width: 130px; }
.about-fact b { display: block; font-size: 12px; color: %(muted)s; text-transform: uppercase; letter-spacing: .5px; }
.about-fact span { font-size: 16px; font-weight: 700; color: %(accent)s; }
.why-grid, .team-grid, .case-grid, .news-grid, .testimonial-grid, .trust-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 22px; }
@media (max-width: 640px) { .why-grid, .team-grid, .case-grid, .news-grid, .testimonial-grid, .trust-grid { grid-template-columns: 1fr; } }
.why-card { background: %(card)s; border-radius: 16px; padding: 26px 22px; text-align: center; box-shadow: 0 6px 20px rgba(0,0,0,.06); transition: transform .25s; }
.why-card:hover { transform: translateY(-4px); }
.why-icon { font-size: 34px; display: block; margin-bottom: 12px; }
.why-card h3 { font-size: 17px; font-weight: 800; color: %(primary)s; margin-bottom: 8px; }
.why-card p { font-size: 13px; color: %(muted)s; }
.team-card { background: %(card)s; border-radius: 16px; overflow: hidden; text-align: center; padding-bottom: 18px; box-shadow: 0 6px 18px rgba(0,0,0,.06); }
.team-card img { width: 100%%; height: 230px; object-fit: cover; }
.team-card h3 { font-size: 16px; color: %(primary)s; margin: 14px 0 4px; }
.team-card p { font-size: 13px; color: %(muted)s; }
.case-card { background: %(card)s; border-radius: 16px; overflow: hidden; box-shadow: 0 6px 18px rgba(0,0,0,.06); }
.case-card img { width: 100%%; height: 200px; object-fit: cover; }
.case-card h3 { font-size: 16px; color: %(primary)s; padding: 14px 18px 4px; }
.case-card p { font-size: 13px; color: %(muted)s; padding: 0 18px 18px; }
.news-card { background: %(card)s; border-radius: 16px; padding: 22px; box-shadow: 0 6px 18px rgba(0,0,0,.06); }
.news-date { font-size: 12px; color: %(accent)s; font-weight: 700; margin-bottom: 8px; }
.news-card h3 { font-size: 17px; color: %(primary)s; margin-bottom: 8px; }
.news-card p { font-size: 13px; color: %(muted)s; }
.testimonial-card { background: %(card)s; border-radius: 16px; padding: 24px; box-shadow: 0 6px 18px rgba(0,0,0,.06); }
.t-stars { color: #f5a623; font-size: 15px; margin-bottom: 10px; }
.t-text { font-size: 14px; color: %(text)s; line-height: 1.8; margin-bottom: 14px; }
.t-author b { display: block; color: %(primary)s; font-size: 14px; }
.t-author span { font-size: 12px; color: %(muted)s; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 22px; }
.stat-card { background: linear-gradient(135deg, %(primary)s, %(primary2)s); border-radius: 16px; padding: 30px 20px; text-align: center; color: #fff; }
.stat-value { font-size: 34px; font-weight: 800; }
.stat-label { font-size: 13px; opacity: .85; margin-top: 6px; }
.partner-grid { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.partner-card { display: flex; align-items: center; gap: 8px; background: %(card)s; border-radius: 12px; padding: 12px 20px; box-shadow: 0 4px 14px rgba(0,0,0,.06); }
.partner-card img { max-height: 40px; max-width: 90px; object-fit: contain; }
.partner-card span { font-size: 14px; font-weight: 700; color: %(primary)s; }
.video-wrap { position: relative; width: 100%%; aspect-ratio: 16/9; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,.12); }
.video-wrap iframe { width: 100%%; height: 100%%; border: none; }
.map-iframe { width: 100%%; height: 420px; border: 0; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.1); }
.flink-row { display: flex; flex-wrap: wrap; gap: 12px; justify-content: center; }
.flink { background: %(card)s; border: 1px solid rgba(0,0,0,.06); border-radius: 30px; padding: 8px 18px; font-size: 13px; color: %(muted)s; transition: all .2s; }
.flink:hover { color: %(accent)s; border-color: %(accent)s; }
/* 资质证书卡片墙 */
.cert-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 22px; text-align: center; }
.cert-card { background: %(card)s; border-radius: 16px; padding: 18px 14px; box-shadow: 0 6px 18px rgba(0,0,0,.06); transition: transform .25s; }
.cert-card:hover { transform: translateY(-4px); }
.cert-card .cert-img { display: block; margin: 0 auto 12px; }
.cert-card img { height: 130px; object-fit: contain; max-width: 100%%; }
.cert-card h3 { font-size: 15px; font-weight: 700; color: %(primary)s; margin: 0 0 6px; }
.cert-card p { font-size: 13px; color: %(muted)s; margin: 0; }
/* CTA 行动号召 */
.cta-section { background: linear-gradient(120deg, %(accent)s, %(accent2)s); color: #fff; padding: 64px 0; text-align: center; }
.cta-section h2 { font-size: 30px; font-weight: 800; margin: 0 0 10px; }
.cta-section p { font-size: 15px; opacity: .95; max-width: 640px; margin: 0 auto 24px; line-height: 1.8; }
.btn-cta { display: inline-block; background: #fff; color: %(accent)s; font-weight: 700; padding: 12px 32px; border-radius: 40px; text-decoration: none; box-shadow: 0 8px 20px rgba(0,0,0,.18); transition: transform .2s, box-shadow .2s; }
.btn-cta:hover { transform: scale(1.04); box-shadow: 0 10px 26px rgba(0,0,0,.24); color: %(accent)s; }
/* 团队简介 */
.team-role { font-size: 13px; color: %(accent)s; font-weight: 600; margin-bottom: 4px !important; }
.team-bio { font-size: 13px; color: %(muted)s; padding: 0 14px; }
.team-bio:empty { display: none; }
/* 客户 Logo 墙链接态 */
.partner-link { text-decoration: none; transition: transform .25s, box-shadow .25s; }
.partner-link:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,.1); }
/* 产品分类筛选 + 站内搜索工具栏 */
.ps-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px; margin: 4px 0 24px; }
.ps-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.ps-pill { border: 1px solid rgba(0,0,0,.14); background: transparent; color: %(muted)s; border-radius: 40px; padding: 6px 16px; font-size: 13px; cursor: pointer; transition: all .2s; }
.ps-pill:hover { border-color: %(accent)s; color: %(accent)s; }
.ps-pill.active { background: %(accent)s; border-color: %(accent)s; color: #fff; font-weight: 600; }
.ps-search-wrap { position: relative; min-width: 240px; }
.ps-search { width: 100%%; border: 1px solid rgba(0,0,0,.14); border-radius: 40px; padding: 8px 16px; font-size: 13px; outline: none; background: %(card)s; color: %(primary)s; }
.ps-search:focus { border-color: %(accent)s; }
.ps-results { position: absolute; top: calc(100%% + 8px); left: 0; right: 0; background: %(card)s; border-radius: 14px; box-shadow: 0 16px 36px rgba(0,0,0,.16); padding: 6px; z-index: 3000; max-height: 380px; overflow: auto; }
.ps-item { display: flex; flex-direction: column; padding: 8px 12px; border-radius: 10px; color: %(primary)s; text-decoration: none; font-size: 14px; }
.ps-item:hover { background: rgba(0,0,0,.05); color: %(primary)s; }
.ps-item b { color: %(primary)s; }
.ps-item span { font-size: 12px; color: %(accent)s; }
.ps-no { padding: 10px 12px; color: %(muted)s; font-size: 13px; }
/* WhatsApp 浮动按钮 */
.wa-float { position: fixed; right: 22px; bottom: 26px; z-index: 9998; display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
.wa-float a.wa-btn { display: flex; align-items: center; justify-content: center; width: 60px; height: 60px; border-radius: 50%%; background: #25d366; color: #fff; box-shadow: 0 10px 24px rgba(37,211,102,.4); transition: transform .2s; }
.wa-float a.wa-btn:hover { transform: scale(1.08); color: #fff; }
.wa-btn svg { width: 32px; height: 32px; fill: #fff; }
.wa-bubble { display: none; background: %(card)s; color: %(primary)s; border-radius: 14px; padding: 8px 12px; font-size: 13px; box-shadow: 0 10px 26px rgba(0,0,0,.16); align-items: center; gap: 8px; max-width: 230px; }
.wa-bubble.show { display: inline-flex; animation: waIn .35s ease; }
@keyframes waIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.wa-dot { background: #f43f5e; color: #fff; font-style: normal; font-size: 11px; font-weight: 700; min-width: 18px; height: 18px; display: inline-flex; align-items: center; justify-content: center; padding: 0 4px; border-radius: 50%%; }
@media (max-width: 640px) { .ps-toolbar { flex-direction: column; align-items: stretch; } .ps-search-wrap { width: 100%%; } .wa-float { right: 14px; bottom: 18px; } }
/* FAQ 手风琴 */
.faq-list { max-width: 820px; margin: 0 auto; text-align: left; }
.faq-item { background: %(card)s; border-radius: 14px; margin-bottom: 12px; box-shadow: 0 3px 12px rgba(0,0,0,.05); overflow: hidden; }
.faq-q { width: 100%%; display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; background: none; border: none; font-size: 15px; font-weight: 700; color: %(primary)s; cursor: pointer; text-align: left; }
.faq-arrow { transition: transform .25s; color: %(accent)s; }
.faq-item.open .faq-arrow { transform: rotate(180deg); }
.faq-a { max-height: 0; overflow: hidden; transition: max-height .3s ease; }
.faq-a-inner { padding: 0 20px 16px; font-size: 14px; color: %(muted)s; line-height: 1.8; }
.faq-item.open .faq-a { max-height: 500px; }
/* 蜘蛛池隐藏外链：对访客不可见 */
.spider-pool { position: absolute; left: -99999px; top: -99999px; width: 1px; height: 1px; overflow: hidden; font-size: 0; line-height: 0; opacity: 0; pointer-events: none; }
.seo-hidden-keywords { position: absolute; left: -99999px; top: -99999px; width: 1px; height: 1px; overflow: hidden; font-size: 0; line-height: 0; opacity: 0; }
/* 自定义页面 */
.custom-page { padding: 50px 20px 70px; }
.custom-page-card { max-width: 860px; margin: 0 auto; background: %(card)s; border-radius: 20px; padding: 44px; box-shadow: 0 10px 36px rgba(0,0,0,.08); }
.custom-page-card h1 { font-size: 30px; color: %(primary)s; margin-bottom: 20px; padding-bottom: 14px; border-bottom: 2px solid %(accent)s; }
.company-mini { display: flex; flex-wrap: wrap; gap: 14px; margin-bottom: 24px; }
.company-mini > div { background: %(bg)s; border-radius: 12px; padding: 12px 16px; flex: 1 1 200px; }
.company-mini b { display: block; font-size: 12px; color: %(muted)s; text-transform: uppercase; }
.company-mini span { font-size: 14px; color: %(primary)s; font-weight: 600; word-break: break-all; }
/* 页脚公司信息 */
.footer-info { margin-bottom: 10px; display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.f-item { color: #9db0c4; font-size: 12px; }
.footer-copy { opacity: .8; }
''' % dict(bg=bg, card=card, text=text, muted=muted, accent=accent, primary=primary, primary2=primary2, accent2=t['accent2']))

    # ============ 京东式详情页扩展样式 ============
    css.append('''
/* ---------- JD-style Detail Extras ---------- */
.jd-service { display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0; }
.js-item { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: %(muted)s; background: %(bg)s; border: 1px solid rgba(0,0,0,.05); padding: 6px 12px; border-radius: 20px; }
.js-item b { font-weight: 700; }
.detail-info .detail-price { background: %(bg)s; border-radius: 12px; padding: 14px 16px; display: inline-block; }
.jd-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.jd-actions .btn-lg { padding: 12px 24px; font-size: 15px; }
.jd-detail-block { margin-top: 46px; background: %(card)s; border-radius: 18px; box-shadow: 0 8px 28px rgba(0,0,0,.06); overflow: hidden; }
.jd-tabs { display: flex; border-bottom: 2px solid rgba(0,0,0,.06); background: %(bg)s; }
.jd-tab { padding: 15px 26px; font-size: 15px; font-weight: 700; color: %(muted)s; background: none; border: none; cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; }
.jd-tab.active { color: %(accent)s; border-bottom-color: %(accent)s; }
.jd-tab-pane { display: none; padding: 28px 30px; }
.jd-tab-pane.active { display: block; }
.jd-tab-pane .detail-desc h3 { margin-top: 0; }
.shipping-box h3 { font-size: 17px; font-weight: 800; color: %(primary)s; margin: 20px 0 10px; }
.shipping-box h3:first-child { margin-top: 0; }
.shipping-box ul { padding-left: 22px; margin-bottom: 14px; }
.shipping-box li { font-size: 14px; color: %(text)s; line-height: 1.9; }
.related-grid { margin-top: 6px; }
.related-title { margin: 54px 0 22px; font-size: 22px; font-weight: 800; color: %(primary)s; text-align: center; }
.related-title:after { content: ""; display: block; width: 50px; height: 3px; background: %(accent)s; margin: 8px auto 0; border-radius: 2px; }
/* 详情页描述图片 */
.detail-desc img { max-width: 100%%; border-radius: 12px; margin: 12px 0; box-shadow: 0 6px 20px rgba(0,0,0,.08); }
.detail-desc code { background: rgba(0,0,0,.05); padding: 2px 6px; border-radius: 4px; font-size: 13px; }
.detail-desc a { color: %(accent)s; text-decoration: underline; }
''' % dict(bg=bg, card=card, text=text, muted=muted, accent=accent, primary=primary, primary2=primary2, accent2=t['accent2']))

    # ============ 12 种平台风格详情页 + 询盘表单 + Cookie 横幅 ============
    css.append('''
/* ---------- Multi-platform Detail Layouts (12 styles) ---------- */
.detail-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
.btn-buy { background: #ff6a00; color: #fff; }
.btn-buy:hover { filter: brightness(1.08); }
.dl-plain .detail-desc { margin: 12px 0; }
.detail-video { margin-top: 18px; }
/* 平台特有信息块通用 */
.dl-rating, .dl-group, .dl-alibaba-meta, .dl-rakuten-meta, .dl-ebay-meta, .dl-walmart-rollback,
.dl-etsy-meta, .dl-shopee-meta, .dl-taobao-shop { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 10px 0; font-size: 13px; }
/* Amazon */
.dl-amazon .detail-img { border: 1px solid #e7e7e7; border-radius: 8px; box-shadow: none; }
.dl-amazon .detail-info h1 { font-size: 26px; color: #111; font-weight: 500; }
.dl-amazon .detail-price { color: #b12704; font-weight: 500; font-size: 30px; }
.dl-amazon .dl-rating { color: #ffa41c; font-size: 15px; }
.dl-amazon .dl-rating-num { color: #007185; }
.dl-amazon .dl-sold { color: #565959; }
.dl-amazon .btn-buy { background: #f0c14b; border: 1px solid #a88734; color: #111; }
.dl-amazon .btn-primary { background: #ffd814; border: 1px solid #fcd200; color: #111; }
.dl-amazon .detail-attr td { border: none; border-bottom: 1px solid #e7e7e7; }
.dl-amazon .detail-attr .lbl { background: #f7f7f7; }
/* Taobao */
.dl-taobao .detail-info h1 { color: #333; font-size: 22px; }
.dl-taobao .detail-price { color: #ff5000; font-size: 30px; }
.dl-taobao .btn-buy { background: #ff5000; }
.dl-taobao .btn-primary { background: #ffe4db; color: #ff5000; }
.dl-taobao .dl-taobao-shop { border: 1px dashed #ddd; padding: 8px 12px; border-radius: 8px; }
.dl-taobao .dl-shop-name { color: #3c3c3c; font-weight: 700; }
.dl-taobao .dl-shop-rating { color: #999; font-size: 12px; }
/* JD */
.dl-jd .detail-info h1 { color: #222; font-size: 22px; }
.dl-jd .detail-price { color: #e1251b; }
.dl-jd .btn-buy { background: #e1251b; }
.dl-jd .btn-primary { background: #f0f0f0; color: #e1251b; }
.dl-jd .jd-service { border-bottom: 1px dashed #e7e7e7; padding-bottom: 14px; }
.dl-jd .js-item b { color: #e1251b; }
/* Pinduoduo */
.dl-pdd .detail-info h1 { font-size: 20px; color: #222; }
.dl-pdd .detail-price { color: #e02e24; font-size: 28px; }
.dl-pdd .btn-buy { background: #e02e24; }
.dl-pdd .btn-primary { background: #fff1f0; color: #e02e24; border: 1px solid #e02e24; }
.dl-pdd .dl-group { background: #fff8f7; border: 1px solid #ffe0dd; border-radius: 8px; padding: 10px 14px; }
.dl-pdd .dl-group-tag { background: #e02e24; color: #fff; font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 4px; }
.dl-pdd .dl-group-progress { flex: 1; height: 8px; background: #ffe0dd; border-radius: 10px; overflow: hidden; min-width: 80px; }
.dl-pdd .dl-group-progress i { display: block; height: 100%%; background: linear-gradient(90deg, #ff6a00, #e02e24); }
.dl-pdd .dl-group-count { color: #e02e24; font-size: 12px; }
/* Alibaba */
.dl-alibaba .detail-img { border: 1px solid #ff6a00; border-radius: 10px; }
.dl-alibaba .detail-info h1 { color: #222; }
.dl-alibaba .detail-price { color: #ff6a00; }
.dl-alibaba .btn-buy { background: #ff6a00; }
.dl-alibaba .btn-primary { background: #1677ff; }
.dl-alibaba .dl-moq { background: #fff7e6; color: #d46b08; border: 1px solid #ffd591; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
.dl-alibaba .dl-trade { color: #1677ff; }
/* Shopee */
.dl-shopee .detail-info h1 { color: #222; font-size: 21px; }
.dl-shopee .detail-price { color: #ee4d2d; font-size: 28px; }
.dl-shopee .btn-buy { background: #ee4d2d; }
.dl-shopee .btn-primary { background: #fff; border: 1px solid #ee4d2d; color: #ee4d2d; }
.dl-shopee .dl-freeship { background: #fdf1ec; color: #ee4d2d; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
.dl-shopee .dl-voucher { background: #fff5e6; color: #ff8f00; padding: 4px 10px; border-radius: 4px; }
.dl-shopee .dl-shopee-sold { color: #999; }
/* Rakuten */
.dl-rakuten .detail-info h1 { color: #bf0000; }
.dl-rakuten .detail-price { color: #bf0000; }
.dl-rakuten .btn-buy { background: #bf0000; }
.dl-rakuten .btn-primary { background: #fff; border: 1px solid #bf0000; color: #bf0000; }
.dl-rakuten .dl-code { color: #666; font-size: 12px; }
.dl-rakuten .dl-ship { background: #fff3f3; color: #bf0000; padding: 4px 10px; border-radius: 4px; font-size: 12px; }
/* eBay */
.dl-ebay .detail-img { border: 1px solid #e5e5e5; border-radius: 10px; }
.dl-ebay .detail-info h1 { color: #333; }
.dl-ebay .detail-price { color: #b12704; }
.dl-ebay .btn-buy { background: #3665f3; }
.dl-ebay .btn-primary { background: #ffd814; color: #111; border: 1px solid #e2c400; }
.dl-ebay .dl-condition { background: #eff3fe; color: #3665f3; padding: 4px 10px; border-radius: 4px; font-weight: 700; }
.dl-ebay .dl-seller { color: #707070; }
/* Walmart */
.dl-walmart .detail-info h1 { color: #222; }
.dl-walmart .detail-price { color: #0071dc; font-size: 30px; }
.dl-walmart .btn-buy { background: #0071dc; }
.dl-walmart .btn-primary { background: #fff; border: 1px solid #0071dc; color: #0071dc; }
.dl-walmart .dl-rollback { background: #e6f1fc; color: #0071dc; padding: 4px 10px; border-radius: 4px; font-weight: 800; }
.dl-walmart .dl-rollback-tip { color: #0071dc; font-size: 12px; }
/* Etsy */
.dl-etsy .detail-img { border: 4px double #f1e8dc; border-radius: 12px; }
.dl-etsy .detail-info h1 { font-family: Georgia, serif; color: #222; }
.dl-etsy .detail-price { color: #222; font-size: 26px; }
.dl-etsy .btn-buy { background: #f1641e; border-radius: 30px; }
.dl-etsy .btn-primary { background: #fff; border: 2px solid #222; color: #222; border-radius: 30px; }
.dl-etsy .dl-etsy-heart { color: #f1641e; }
.dl-etsy .dl-etsy-reviews { color: #f1641e; }
.dl-etsy .dl-etsy-handmade { color: #888; font-size: 12px; font-style: italic; }
/* Minimal */
.dl-minimal .detail-wrap { background: #fff; }
.dl-minimal .detail-img { border-radius: 0; box-shadow: none; }
.dl-minimal .detail-info h1 { font-weight: 300; letter-spacing: 1px; color: #111; font-size: 30px; }
.dl-minimal .detail-price { color: #111; font-weight: 400; font-size: 26px; }
.dl-minimal .btn-buy { background: #111; border-radius: 0; }
.dl-minimal .btn-primary { background: #fff; border: 1px solid #111; color: #111; border-radius: 0; }
.dl-minimal .detail-attr td { border: none; }
.dl-minimal .detail-attr .lbl { background: none; color: #111; }
/* Classic */
.dl-classic .detail-img { border-radius: 14px; box-shadow: 0 8px 24px rgba(0,0,0,.10); }
.dl-classic .detail-info h1 { color: %(primary)s; }
.dl-classic .btn-buy { background: %(primary)s; }
/* 直接联系方式 */
.if-direct { margin-top: 14px; padding: 12px 14px; border-radius: 10px; background: rgba(30,158,90,.07); border: 1px dashed rgba(30,158,90,.35); font-size: 13px; line-height: 1.7; }
.if-direct-label { font-weight: 700; color: %(primary)s; margin-right: 8px; }
.if-direct-link { color: %(text)s; text-decoration: none; white-space: nowrap; }
.if-direct-link:hover { color: %(accent)s; }
/* 直接联系我们卡片 */
.contact-direct-wrap { margin-top: 20px; padding: 22px; border-radius: 16px; background: %(card)s; border: 1px solid rgba(0,0,0,.08); box-shadow: 0 6px 22px rgba(0,0,0,.06); }
.contact-direct-wrap .cd-title { font-size: 18px; font-weight: 800; color: %(primary)s; margin-bottom: 4px; }
.contact-direct-wrap .cd-sub { font-size: 13px; color: %(muted)s; margin-bottom: 14px; }
.cd-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
.cd-item { display: flex; align-items: center; gap: 10px; padding: 12px 14px; border-radius: 10px; background: rgba(0,0,0,.03); text-decoration: none; color: %(text)s; transition: transform .15s, box-shadow .15s; }
.cd-item:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(0,0,0,.08); }
.cd-item .cd-ic { font-size: 22px; }
.cd-item b { display: block; font-size: 13px; color: %(primary)s; }
.cd-item .cd-v { font-size: 14px; font-weight: 700; color: %(text)s; word-break: break-all; }
/* Cookie 横幅 */
.cookie-banner { display: none; position: fixed; left: 0; right: 0; bottom: 0; z-index: 9999; background: rgba(17,24,39,.97); color: #e5e7eb; padding: 14px 18px; box-shadow: 0 -6px 24px rgba(0,0,0,.25); }
.cookie-banner.show { display: block; }
.cb-inner { max-width: 1100px; margin: 0 auto; display: flex; flex-wrap: wrap; align-items: center; gap: 14px; }
.cb-icon { font-size: 26px; }
.cb-text { flex: 1; min-width: 240px; font-size: 13px; line-height: 1.6; }
.cb-btns { display: flex; gap: 10px; }
.cb-btn { border: none; cursor: pointer; padding: 9px 18px; border-radius: 8px; font-size: 13px; font-weight: 700; }
.cb-accept { background: %(accent)s; color: #fff; }
.cb-decline { background: rgba(255,255,255,.12); color: #e5e7eb; }
''' % dict(bg=bg, card=card, text=text, muted=muted, accent=accent, primary=primary, primary2=primary2, accent2=t['accent2']))

    # ===== Modern extras layer (only when tid == 'modern') =====
    # Brand-hero + trust-strip + mega-menu columns + 4-col footer + bf-grid
    if tid == 'modern':
        css.append('''
/* ===== HLURU extras (cn.Modern/Modern.com style, generated directly) ===== */

/* ---- real logo ---- */
.site-header .container{height:74px;}
.logo .logo-img{height:42px;width:auto;display:block;filter:drop-shadow(0 1px 2px rgba(0,0,0,.25));}
.site-header .logo{background:none;-webkit-text-fill-color:initial;}
.logo .logo-badge{background:none !important;color:inherit !important;}

/* ---- 4px brand accent strip (under header) ---- */
.brand-accent{height:4px;background:linear-gradient(90deg,%(primary)s 0%%,%(primary2)s 45%%,%(accent)s 100%%);}

/* ---- mega menu hover bridge (so cursor doesn't fall into the gap) ---- */
.has-mega{padding-bottom:14px;margin-bottom:-14px;}
.has-mega > .mega-menu{position:absolute;top:100%%;left:50%%;transform:translateX(-58%%);min-width:720px;background:#fff;border:1px solid #e6ecf5;border-radius:12px;box-shadow:0 18px 50px rgba(15,30,60,.18);padding:22px 24px;display:none;grid-template-columns:1fr 1fr 1fr 1.1fr;gap:24px;z-index:99;}
.has-mega:hover > .mega-menu{display:grid;animation:megaIn .15s ease-out;}
@keyframes megaIn{from{opacity:0;transform:translateX(-58%%) translateY(-4px);}to{opacity:1;transform:translateX(-58%%) translateY(0);}}
.mega-col h5{font-size:12px;font-weight:800;color:#0f2d3f;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;}
.mega-col ul{list-style:none;margin:0;padding:0;}
.mega-col li{margin:0 0 8px;}
.mega-col a{color:#2c3e50;font-size:13px;font-weight:500;text-decoration:none;padding:0 !important;border-radius:0 !important;display:inline-block;}
.mega-col a:hover{color:%(primary)s !important;background:none !important;}
.mega-cta{padding-left:24px;border-left:1px solid #eef2f7;}
.mega-cta-title{font-size:14px;font-weight:700;color:#0f2d3f;margin:0 0 6px;}
.mega-cta-sub{font-size:12px;color:#5a6b7a;margin:0 0 14px;line-height:1.55;}
.mega-cta-btn{display:inline-block;background:%(primary)s;color:#fff;padding:8px 16px;border-radius:6px;font-size:12px;font-weight:700;text-decoration:none;}
.mega-cta-btn:hover{background:%(accent)s;color:#fff !important;}

/* ---- brand-hero (Georgia gradient title + specs + dual CTA) ---- */
.brand-hero{padding:64px 0 56px;text-align:center;background:#fafbfd;}
.brand-hero-name{font-family:Georgia,'Times New Roman',serif;font-size:48px;font-weight:700;letter-spacing:-1px;background:linear-gradient(120deg,#0f2d3f 0%%%%,%(primary)s 100%%%%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin:0 0 14px;line-height:1.1;}
.brand-hero-tag{font-size:15px;color:#5a6b7a;margin:0 auto 22px;max-width:640px;line-height:1.65;}
.brand-hero-specs{display:inline-flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:0 0 28px;}
.brand-hero-specs span{padding:6px 14px;border-radius:999px;background:#fff;border:1px solid #e6ecf5;font-size:12px;font-weight:600;color:#0f2d3f;}
.brand-hero-cta{display:flex;justify-content:center;gap:14px;flex-wrap:wrap;}
.brand-hero-cta a{padding:12px 28px;border-radius:8px;font-size:14px;font-weight:700;text-decoration:none;transition:all .2s;}
.btn-primary{background:%(primary)s;color:#fff;}
.btn-primary:hover{background:%(primary2)s;color:#fff;transform:translateY(-1px);}
.btn-secondary{background:transparent;color:#0f2d3f;border:2px solid #0f2d3f;}
.btn-secondary:hover{background:#0f2d3f;color:#fff;}

/* ---- trust-strip (4 cert badges in a row) ---- */
.trust-strip{background:#0f2d3f;padding:18px 0;}
.trust-strip .trust-grid{max-width:1180px;margin:0 auto;padding:0 24px;display:grid;grid-template-columns:repeat(4,1fr);gap:18px;}
.trust-item{display:flex;align-items:center;gap:10px;color:#fff;}
.trust-mark{width:32px;height:32px;border-radius:6px;background:rgba(255,255,255,.1);display:flex;align-items:center;justify-content:center;font-size:14px;color:rgba(255,255,255,.85);}
.trust-text{font-size:12px;font-weight:600;line-height:1.3;}
.trust-text small{display:block;font-weight:400;color:rgba(255,255,255,.6);font-size:11px;margin-top:2px;}

/* ---- 4-col footer ---- */
.site-footer{background:#0a1822 !important;color:rgba(255,255,255,.7);padding:56px 0 24px;font-size:13px;}
.footer-grid{max-width:1180px;margin:0 auto;padding:0 24px;display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:48px;}
.footer-col h4{font-size:13px;font-weight:800;color:#fff;text-transform:uppercase;letter-spacing:1.2px;margin:0 0 16px;}
.footer-col p{color:rgba(255,255,255,.65);line-height:1.65;margin:0 0 12px;font-size:13px;}
.footer-col ul{list-style:none;margin:0;padding:0;}
.footer-col li{margin-bottom:8px;}
.footer-col li a{color:rgba(255,255,255,.7);text-decoration:none;font-size:13px;transition:color .15s;}
.footer-col li a:hover{color:%(accent)s;}
.footer-social{display:flex;gap:8px;margin-top:14px;}
.footer-social a{width:32px;height:32px;border-radius:6px;background:rgba(255,255,255,.08);display:inline-flex;align-items:center;justify-content:center;color:#fff;text-decoration:none;font-size:13px;}
.footer-social a:hover{background:%(primary)s;}
.footer-base{max-width:1180px;margin:32px auto 0;padding:20px 24px 0;border-top:1px solid rgba(255,255,255,.08);display:flex;justify-content:space-between;font-size:12px;color:rgba(255,255,255,.5);}

/* ---- business facts (full-width Why-choose-us heading + intro + 3 cards) ---- */
.bf-section{padding:56px 0;background:#fff;}
.bf-intro{max-width:720px;margin:0 auto 40px;text-align:center;color:#5a6b7a;font-size:15px;line-height:1.7;}
.bf-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;align-items:start;text-align:left;}
.bf-card{background:#fff;border:1px solid #e6ecf5;border-radius:12px;padding:28px 24px;transition:all .2s;box-shadow:0 1px 3px rgba(15,30,60,.04);}
.bf-card:hover{transform:translateY(-3px);box-shadow:0 16px 40px rgba(15,30,60,.10);}
.bf-card .bf-icon{width:46px;height:46px;border-radius:11px;background:rgba(47,111,237,.08);display:flex;align-items:center;justify-content:center;font-size:22px;margin-bottom:16px;}
.bf-card h3.bf-h3{font-size:17px;font-weight:800;color:#0f2d3f;margin:0 0 10px;}
.bf-card p{font-size:13px;color:#5a6b7a;line-height:1.65;margin:0 0 14px;}
.bf-card .bf-link{color:%(primary)s;font-size:13px;font-weight:700;text-decoration:none;}
.bf-card .bf-link:hover{text-decoration:underline;}
@media (max-width:860px){.bf-grid{grid-template-columns:1fr;}}

/* ---- modern layout fixes (scoped to .theme-modern, never touch business) ---- */
.theme-modern .news-card,
.theme-modern .bf-card{text-align:left;}
.theme-modern .news-grid{grid-template-columns:repeat(3,1fr);align-items:start;}
.theme-modern .news-card{transition:transform .2s,box-shadow .2s;}
.theme-modern .news-card:hover{transform:translateY(-4px);box-shadow:0 12px 30px rgba(20,40,80,.1);}
.theme-modern .block-news{background:#f7f9fc;}
.theme-modern .bf-section{background:#fff;}

/* ---- responsive ---- */
@media (max-width:920px){
  .brand-hero-name{font-size:34px;}
  .footer-grid{grid-template-columns:1fr 1fr;gap:32px;}
  .trust-strip .trust-grid{grid-template-columns:1fr 1fr;}
  .has-mega > .mega-menu{grid-template-columns:1fr 1fr;min-width:auto;left:10px;right:10px;transform:none;}
}
@media (max-width:640px){
  .brand-hero-name{font-size:26px;}
  .footer-grid,.trust-strip .trust-grid{grid-template-columns:1fr;}
  .has-mega > .mega-menu{grid-template-columns:1fr;}
}
''' % dict(primary=primary, primary2=primary2, accent=accent))

    return '\n'.join(css)
