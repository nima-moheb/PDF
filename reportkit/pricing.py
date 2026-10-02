"""Exact, explicit currency arithmetic and a reusable quote page."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from . import engine as e

LABELS = {
    'en': ('Description', 'Quantity', 'Unit price', 'Amount', 'Total', 'Discount', 'Subtotal'),
    'fa': ('شرح خدمات', 'تعداد', 'قیمت واحد', 'مبلغ', 'جمع کل', 'تخفیف', 'جمع خدمات'),
    'es': ('Descripción', 'Cantidad', 'Precio unitario', 'Importe', 'Total', 'Descuento', 'Subtotal'),
}


def calculate(page):
    unit = Decimal('1') if page['currency'] in ('IRR', 'IRT') else Decimal('.01')
    amounts = []
    for item in page['items']:
        price, qty = Decimal(item['unit_price']), Decimal(item['quantity'])
        if price < 0 or qty <= 0 or price != price.quantize(unit):
            raise ValueError('PRICE_FAIL: positive quantities and currency-precision prices required')
        amounts.append((qty * price).quantize(unit, rounding=ROUND_HALF_UP))
    subtotal = sum(amounts, Decimal('0'))
    discount = Decimal(page.get('discount', '0'))
    if discount < 0 or discount > subtotal or discount != discount.quantize(unit):
        raise ValueError('PRICE_FAIL: invalid discount')
    total = subtotal - discount
    if 'expected_total' in page and Decimal(page['expected_total']) != total:
        raise ValueError(f"PRICE_FAIL: expected {page['expected_total']}, calculated {total}")
    return {'amounts': amounts, 'subtotal': subtotal, 'discount': discount, 'total': total}


def money(value, currency, lang):
    places = 0 if currency in ('IRR', 'IRT') else 2
    text = f'{Decimal(value):,.{places}f}'
    if lang == 'fa':
        text = text.translate(str.maketrans('0123456789,.', '۰۱۲۳۴۵۶۷۸۹٬٫'))
    return text


def currency_name(currency, lang):
    if lang == 'fa':
        return {'IRT': 'تومان', 'IRR': 'ریال', 'USD': 'دلار آمریکا', 'EUR': 'یورو', 'GBP': 'پوند'}[currency]
    return {'IRT': 'toman', 'IRR': 'IRR', 'USD': 'USD', 'EUR': 'EUR', 'GBP': 'GBP'}[currency]


def pricing_page(c, meta, p, th, number):
    lang = meta.get('language', 'en'); rtl = lang == 'fa'
    labels = LABELS[lang]; amounts = calculate(p); currency = p['currency']
    e.header_footer(c, meta, number, p['title'], th)
    e.tech_grid(c, th)
    y = e.page_title(c, p['title'], p.get('eyebrow', currency_name(currency, lang)), th)
    x = e.SAFE_X; width = e.W - 2*x
    if p.get('intro'):
        y = e.draw_text(c, p['intro'], x, y, width, size=10.5, max_lines=4) - 7*e.MM
    widths = [width*.43, width*.13, width*.22, width*.22]
    rows = [[item['description'], item['quantity'], money(item['unit_price'], currency, lang), money(amount, currency, lang)]
            for item, amount in zip(p['items'], amounts['amounts'])]
    if rtl:
        for row in rows:
            row[1] = row[1].translate(str.maketrans('0123456789.', '۰۱۲۳۴۵۶۷۸۹٫'))
    def draw_row(values, top, header=False):
        specs=[]
        for value, w in zip(values, widths):
            rt=e.is_fa(value); font=('FaB' if header else 'Fa') if rt else ('LatinB' if header else 'Latin')
            lines=e.wrap(value, font, 9 if not header else 8, w-7*e.MM, rt)
            if len(lines)>4: raise ValueError(f'FIT_FAIL: pricing cell too long: {value}')
            specs.append((lines,rt,font))
        minimum = 16 if header else (27 if len(rows) <= 3 else 17)
        h=max(minimum*e.MM, max(len(v[0]) for v in specs)*14+6*e.MM)
        if top-h<74*e.MM: raise ValueError('FIT_FAIL: pricing rows exceed page; split the quote')
        e.round_rect(c,x,top-h,width,h,6,fill=th['soft'] if header else '#FFFFFF',stroke='#DEE5EF')
        offset=0
        for w,(lines,rt,font) in zip(widths,specs):
            xx=x+width-offset-w if rtl else x+offset
            cy=top-h/2+(len(lines)-1)*7-3
            c.setFillColor(e.color(th['deep']))
            for line in lines:
                e.draw_visual_line(c,line,xx+3.5*e.MM,cy,w-7*e.MM,font,8 if header else 9,rt,align='right' if rtl else 'left'); cy-=14
            offset+=w
        return top-h
    y=draw_row(labels[:4],y,True)
    for row in rows: y=draw_row(row,y)
    y-=8*e.MM
    if amounts['discount']:
        detail=f"{labels[6]}: {money(amounts['subtotal'],currency,lang)}    {labels[5]}: {money(amounts['discount'],currency,lang)}"
        y=e.draw_text(c,detail,x,y,width,size=9,max_lines=2)-4*e.MM
    total=f"{money(amounts['total'],currency,lang)} {currency_name(currency,lang)}"
    e.round_rect(c,x,y-31*e.MM,width,31*e.MM,12,fill=th['deep'])
    e.draw_single_line(c,labels[4],x+7*e.MM,y-9*e.MM,width-14*e.MM,size=10,bold=True,rtl=rtl,colorv='#FFFFFF',align='right' if rtl else 'left')
    e.draw_single_line(c,total,x+7*e.MM,y-23*e.MM,width-14*e.MM,size=27,min_size=18,bold=True,rtl=rtl,colorv='#FFFFFF',align='right' if rtl else 'left')
    if p.get('note'):
        end=e.draw_text(c,p['note'],x,y-42*e.MM,width,size=9.5,max_lines=5)
        if end<25*e.MM: raise ValueError('FIT_FAIL: pricing note exceeds safe area')
