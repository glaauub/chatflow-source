"""Source-preserving catalog drafts and localization; no scraping or publishing side effects."""
import copy
import hashlib
import html
import json
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import unquote, urlsplit

LANGUAGES = {'en':'English','zh':'简体中文','zh-Hant':'繁體中文','ja':'日本語','ko':'한국어','de':'Deutsch','es':'Español','ru':'Русский','fr':'Français','pt':'Português','ar':'العربية'}
TEXT_FIELDS = ('name','description','spec','category','meta_title','meta_description')

# Keep order, signs and spelling. A number-only counter would accept a changed
# dimension (10×20 -> 20×10) or a dropped minus sign.
_NUMBER = re.compile(r'[+\-−±]?\d+(?:[.,]\d+)*(?:[eE][+\-]?\d+)?')
_IDENTIFIER = re.compile(r'(?<![A-Za-z0-9])[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*(?![A-Za-z0-9])')


def validate_translation_text(source, translated, protected_identifiers=()):
    """Reject altered facts; ordinary words are not treated as model numbers."""
    if not isinstance(source,str) or not isinstance(translated,str):
        raise ValueError('翻译内容必须是文字')
    if not source.strip():
        if translated.strip():raise ValueError('原资料为空，AI 不能凭空添加内容')
        return
    if not translated.strip():raise ValueError('AI 漏译了内容，已拦下')
    if _NUMBER.findall(source)!=_NUMBER.findall(translated):
        raise ValueError('AI 翻译改变了数字、顺序或正负号，已拦下。请检查后重试。')
    def identifiers(value):
        return [token for token in _IDENTIFIER.findall(value)
                if re.search('[A-Za-z]',token) and re.search('[0-9]',token)
                and not re.fullmatch(r'[0-9]+(?:[.,][0-9]+)?(?:g|kg|mg|mm|cm|ml|mL|GB|MB|TB|W|V|A|Hz)',token)]
    unit_names = {'g':'g','gram':'g','grams':'g','gramme':'g','grammes':'g','gramm':'g','gramos':'g','gramas':'g','克':'g','グラム':'g','그램':'g','г':'g','غرام':'g','غراما':'g','جرام':'g',
                  'kg':'kg','kilogram':'kg','kilograms':'kg','公斤':'kg','千克':'kg','キログラム':'kg','킬로그램':'kg','кг':'kg',
                  'mg':'mg','毫克':'mg','ml':'ml','milliliter':'ml','milliliters':'ml','毫升':'ml','ミリリットル':'ml','밀리리터':'ml','мл':'ml',
                  'mm':'mm','millimeter':'mm','millimeters':'mm','毫米':'mm','ミリメートル':'mm','밀리미터':'mm','мм':'mm',
                  'cm':'cm','centimeter':'cm','centimeters':'cm','厘米':'cm','センチメートル':'cm','센티미터':'cm','см':'cm',
                  'gb':'gb','mb':'mb','tb':'tb','w':'w','v':'v','a':'a','hz':'hz',
                  'kilogramm':'kg','kilogramme':'kg','kilogrammes':'kg','kilogramos':'kg','quilogramas':'kg','كيلوغرام':'kg','كغ':'kg',
                  'mililitro':'ml','mililitros':'ml','millilitre':'ml','millilitres':'ml','millilitern':'ml','مل':'ml',
                  'millimetre':'mm','millimetres':'mm','millimetern':'mm','milímetro':'mm','milímetros':'mm','مم':'mm',
                  'centimetre':'cm','centimetres':'cm','zentimeter':'cm','centímetro':'cm','centímetros':'cm','سم':'cm',
                  '°c':'celsius','℃':'celsius','°f':'fahrenheit','℉':'fahrenheit','摄氏度':'celsius','攝氏度':'celsius','华氏度':'fahrenheit','華氏度':'fahrenheit'}
    units = re.compile(r'([+\-−±]?\d+(?:[.,]\d+)*)\s*(' + '|'.join(re.escape(k) for k in sorted(unit_names,key=len,reverse=True)) + r')(?![A-Za-z])',re.I)
    def measurements(value):
        return [(number,unit_names[unit.lower()]) for number,unit in units.findall(value)]
    if measurements(source)!=measurements(translated):
        raise ValueError('AI 翻译改变了计量单位，已拦下，请检查后重试')
    if identifiers(source)!=identifiers(translated):
        raise ValueError('AI 翻译改变了型号或编号，已拦下。请检查后重试。')
    for identifier in protected_identifiers:
        if not isinstance(identifier,str) or not identifier:continue
        matcher=re.compile(r'(?<![A-Za-z0-9])'+re.escape(identifier)+r'(?![A-Za-z0-9])')
        count=len(matcher.findall(source))
        if count and len(matcher.findall(translated))!=count:
            raise ValueError('AI 翻译改变了原商品型号或 SKU，已拦下')


def text(value, limit=20000):
    if value is None: return ''
    if not isinstance(value, (str,int,float)): raise ValueError('文字字段格式不正确')
    value = str(value).strip()
    if len(value) > limit: raise ValueError('文字太长，请拆分产品介绍')
    return value


def amount(value):
    if value is None or value=='': return None
    try: number=Decimal(str(value))
    except InvalidOperation: raise ValueError('价格必须是数值；未知价格请留空')
    if not number.is_finite() or number<0: raise ValueError('价格不能是负数或无穷大')
    return str(number)


def web_url(value):
    if isinstance(value,str) and (re.search(r'[\x00-\x1f\x7f\u2028\u2029]',value) or any(ch in value for ch in '\\<>"\'')):
        raise ValueError('来源或图片地址不能包含引号、反斜杠或控制字符')
    value=text(value,4000)
    if value.startswith('//'): value='https:'+value
    if not value: return ''
    if any(ch.isspace() for ch in value):raise ValueError('网址中的空格请保留为 %20 编码')
    checked=value
    # The URL is later used in HTML attributes and some legacy inline JS. Check
    # both URL and HTML encodings repeatedly, without changing the actual URL.
    # Percent-encoded ordinary spaces in image paths remain valid.
    while True:
        if re.search(r'[\x00-\x1f\x7f\u2028\u2029]',checked) or any(ch in checked for ch in '\\<>"\''):
            raise ValueError('来源或图片地址包含不安全的编码字符')
        decoded=html.unescape(unquote(checked))
        if decoded==checked:break
        checked=decoded
    parts=urlsplit(value)
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('来源或图片地址必须是普通网页地址')
    return value


def normalize_product(raw):
    if not isinstance(raw,dict): raise ValueError('商品资料必须是对象')
    product={key:text(raw.get(key)) for key in TEXT_FIELDS}
    if not product['name']: raise ValueError('缺少商品名称')
    product.update(source_platform=text(raw.get('source_platform'),80),source_id=text(raw.get('source_id'),160),source_url=web_url(raw.get('source_url')),sku=text(raw.get('sku'),160),model=text(raw.get('model'),160),price=amount(raw.get('price')),currency=text(raw.get('currency'),8).upper())
    if product['currency'] and not re.fullmatch('[A-Z]{3}',product['currency']): raise ValueError('货币请用 CNY、USD 等三个字母')
    images=raw.get('images') or []
    if not isinstance(images,list) or len(images)>100: raise ValueError('每个商品最多 100 张图片')
    product['images']=list(dict.fromkeys(web_url(x) for x in images if x))
    variants=raw.get('variants') or []
    if not isinstance(variants,list) or len(variants)>1000: raise ValueError('每个商品最多 1000 个规格组合')
    product['variants']=[];seen=set()
    for index,v in enumerate(variants):
        if not isinstance(v,dict): raise ValueError('SKU 资料格式不正确')
        identifier=text(v.get('source_sku') or v.get('sku'),160)
        if not identifier: raise ValueError('每个规格组合必须保留原 SKU 编号')
        if identifier in seen: raise ValueError('同一商品有重复的 SKU 编号：'+identifier)
        seen.add(identifier)
        stock=v.get('stock')
        if stock is not None and stock!='':
            if isinstance(stock,bool) or not re.fullmatch(r'\d+',str(stock)): raise ValueError('库存必须是非负整数，未知请留空')
            stock=int(stock)
        else: stock=None
        attributes=v.get('attributes') or []
        if not isinstance(attributes,list) or len(attributes)>30: raise ValueError('规格属性格式不正确')
        attrs=[]
        for a in attributes:
            if not isinstance(a,dict): raise ValueError('规格属性格式不正确')
            name=text(a.get('name'),120);value=text(a.get('value'),300)
            if not name or not value: raise ValueError('规格名称和值都不能为空')
            attrs.append({'name':name,'value':value})
        product['variants'].append({'source_sku':identifier,'sku':text(v.get('sku') or identifier,160),'attributes':attrs,'price':amount(v.get('price')),'stock':stock,'image':web_url(v.get('image'))})
    product['warnings']=[]
    if not product['source_url']:product['warnings'].append('没有原商品链接')
    if not product['images']:product['warnings'].append('没有商品图片')
    if product['price'] is not None and not product['currency']:product['warnings'].append('有价格但没有货币，请确认币种')
    product['fingerprint']=hashlib.sha256(json.dumps([product['source_platform'],product['source_id'] or product['source_url'] or product['name']],ensure_ascii=False).encode()).hexdigest()
    return product


def translation_input(product):
    # Send language-bearing text only; identifiers, stock and prices are excluded.
    fields={k:product.get(k,'') for k in TEXT_FIELDS}
    fields['variants']=[{'attributes':copy.deepcopy(v['attributes'])} for v in product['variants']]
    return fields


def accept_translation(product,language,result):
    if language not in LANGUAGES: raise ValueError('语言不在当前系统的选项里')
    if not isinstance(result,dict) or set(result)!=set(TEXT_FIELDS)|{'variants'}: raise ValueError('翻译字段不完整或夹带额外字段')
    translated={k:text(result[k]) for k in TEXT_FIELDS}
    if not translated['name']:raise ValueError('翻译后商品名称为空')
    protected=[product.get('model',''),product.get('sku','')]
    for variant in product['variants']:protected.extend((variant.get('source_sku',''),variant.get('sku','')))
    for key in TEXT_FIELDS:validate_translation_text(product.get(key,''),translated[key],protected)
    variants=result['variants']
    if not isinstance(variants,list) or len(variants)!=len(product['variants']):raise ValueError('翻译后的规格数量与原商品不一致')
    translated['variants']=[]
    for source,new in zip(product['variants'],variants):
        if not isinstance(new,dict) or set(new)!={'attributes'}:raise ValueError('翻译不能更改 SKU、价格、库存或图片')
        attrs=new['attributes']
        if not isinstance(attrs,list) or len(attrs)!=len(source['attributes']):raise ValueError('翻译后的规格属性数量不一致')
        output=[]
        for original,a in zip(source['attributes'],attrs):
            if not isinstance(a,dict) or set(a)!={'name','value'}:raise ValueError('翻译的规格属性格式不正确')
            n=text(a['name'],120);v=text(a['value'],300)
            if not n or not v:raise ValueError('翻译后的规格不能为空')
            validate_translation_text(original['name'],n,protected)
            validate_translation_text(original['value'],v,protected)
            output.append({'name':n,'value':v})
        translated['variants'].append({'attributes':output})
    return translated


def localized(product,language,translations):
    result=copy.deepcopy(product)
    if language not in translations:return result
    translated=accept_translation(product,language,translations[language])
    for key in TEXT_FIELDS:result[key]=translated[key]
    for variant,words in zip(result['variants'],translated['variants']):variant['attributes']=words['attributes']
    return result


def from_onebound_item(payload,platform='taobao'):
    """Normalize documented item_get fields; unsupported shapes fail rather than inventing SKUs."""
    item=payload.get('item') if isinstance(payload,dict) else None
    if not isinstance(item,dict) or not item.get('title'):raise ValueError('接口没有返回完整商品详情')
    skus=item.get('skus') or {};skus=skus.get('sku',[]) if isinstance(skus,dict) else skus
    variants=[]
    for s in skus:
        attrs=[]
        for chunk in (s.get('properties_name') or '').split(';'):
            if not chunk:continue
            parts=chunk.split(':',3)
            if len(parts)!=4:raise ValueError('接口的 SKU 规格格式尚未适配，请保留原始资料')
            attrs.append({'name':parts[2],'value':parts[3]})
        variants.append({'source_sku':s.get('sku_id'),'sku':s.get('outer_id') or s.get('sku_id'),'attributes':attrs,'price':s.get('price'),'stock':s.get('quantity'),'image':s.get('pic_url')})
    pictures=item.get('item_imgs') or []
    if isinstance(pictures,dict):pictures=pictures.get('item_img',[])
    images=[p.get('url') for p in pictures if isinstance(p,dict) and p.get('url')]
    if item.get('pic_url'):images.insert(0,item['pic_url'])
    return normalize_product({'name':item['title'],'description':html.unescape(re.sub('<[^>]+>',' ',item.get('desc') or '')),'source_platform':platform,'source_id':str(item.get('num_iid') or ''),'source_url':item.get('detail_url'),'price':None if str(item.get('price'))=='-1' else item.get('price'),'currency':item.get('currency') or '', 'images':images,'variants':variants})
