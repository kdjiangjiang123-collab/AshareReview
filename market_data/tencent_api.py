"""腾讯实时行情接口 — 来自悬浮盯盘条的成熟实现。
免费、稳定、无需API key。支持A股 + 指数实时报价。

接口: https://qt.gtimg.cn/q={codes}
返回格式: v_CODE="字段1~字段2~..."
"""

import re
import requests
import time


def _decode_unicode_escapes(s: str) -> str:
    r"""将 JSON 风格的 \uXXXX 转义序列解码为实际字符。
    腾讯智能选股接口某些返回结果中中文以 Unicode 转义形式出现。
    """
    return re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), s)

# ─── 代码前缀映射 ───
def prefix(code: str) -> str:
    """映射股票代码到交易所前缀 (sh/sz/bj)"""
    code = str(code).strip()
    if code.startswith(('sh', 'sz', 'bj')):
        return code  # 已经是完整格式
    if code.startswith('6') or code.startswith('9'):
        return f'sh{code}'
    if code.startswith('8') or code.startswith('4'):
        return f'bj{code}'
    return f'sz{code}'

# ─── 指数代码 ───
INDEX_CODES = {
    '上证指数': 'sh000001',
    '深证成指': 'sz399001',
    '创业板指': 'sz399006',
    '科创50': 'sh000688',
}

# ─── 字段索引（腾讯行情返回的~分隔字段） ───
FIELD_NAME   = 1    # 名称
FIELD_CODE   = 2    # 代码
FIELD_PRICE  = 3    # 当前价
FIELD_PREV   = 4    # 昨收
FIELD_OPEN   = 5    # 今开
FIELD_VOLUME = 6    # 成交量（手）
FIELD_HIGH   = 33   # 最高
FIELD_LOW    = 34   # 最低
FIELD_AMOUNT = 37   # 成交额（万）
FIELD_PCT    = 32   # 涨跌幅%


def _request(url: str, encoding: str = 'gbk') -> str:
    """发起HTTP请求，带重试"""
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=10)
            resp.encoding = encoding
            return resp.text
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(1 * (attempt + 1))


def fetch_realtime(codes: list[str]) -> dict[str, dict]:
    """获取一批股票的实时行情。

    Args:
        codes: 股票代码列表，可以是纯数字如'000001'，或带前缀如'sh000001'

    Returns:
        {code: {name, price, prev_close, open, high, low, volume, amount, pct}}
    """
    if not codes:
        return {}

    full_codes = [prefix(c) for c in codes]
    url = f"https://qt.gtimg.cn/q={','.join(full_codes)}&r={int(time.time()*1000)}"

    try:
        text = _request(url)
    except Exception as e:
        print(f"[tencent] fetch error: {e}")
        return {}

    results = {}
    # 解析响应: v_sh000001="1~上证指数~000001~3987.73~..."
    for match in re.finditer(r'v_(\w+)="(.+)"', text):
        code = match.group(1)
        fields = match.group(2).split('~')

        if len(fields) < 35:
            continue

        try:
            price = float(fields[FIELD_PRICE]) if fields[FIELD_PRICE] else 0
            prev_close = float(fields[FIELD_PREV]) if fields[FIELD_PREV] else 0
            pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

            results[code] = {
                'code': code,
                'name': fields[FIELD_NAME],
                'price': price,
                'prev_close': prev_close,
                'open': float(fields[FIELD_OPEN]) if fields[FIELD_OPEN] else 0,
                'high': float(fields[FIELD_HIGH]) if fields[FIELD_HIGH] else 0,
                'low': float(fields[FIELD_LOW]) if fields[FIELD_LOW] else 0,
                'volume': int(float(fields[FIELD_VOLUME])) if fields[FIELD_VOLUME] else 0,
                'amount': float(fields[FIELD_AMOUNT]) * 10000 if fields[FIELD_AMOUNT] else 0,  # 万→元
                'pct': float(fields[FIELD_PCT]) if fields[FIELD_PCT] else pct,
            }
        except (ValueError, IndexError) as e:
            continue

    return results


def fetch_indices_realtime() -> dict:
    """获取四大指数实时行情"""
    codes = list(INDEX_CODES.values())
    data = fetch_realtime(codes)

    result = {}
    for name, code in INDEX_CODES.items():
        if code in data:
            d = data[code]
            result[name] = {
                'name': name,
                'code': code,
                'close': d['price'],
                'open': d['open'],
                'high': d['high'],
                'low': d['low'],
                'pct': d['pct'],
                'volume': d['volume'],
                'amount': d['amount'],
            }
    return result


def fetch_stocks_realtime(codes: list[str]) -> dict:
    """获取个股实时行情（代码不带前缀也行，内部处理）"""
    full_codes = [prefix(c) for c in codes]
    data = fetch_realtime(full_codes)

    # 映射回原始code
    result = {}
    for orig, full in zip(codes, full_codes):
        if full in data:
            result[orig] = data[full]
    return result


def search_stock_tencent(keyword: str) -> list[dict]:
    """通过腾讯智能选股接口搜索股票。

    接口返回格式: market~code~name~pinyin~type
    多条结果用 ^ 分隔，如: sz~000001~平安银行~payh~GP-A^sh~600519~贵州茅台~gzmt~GP-A
    """
    try:
        url = f"https://smartbox.gtimg.cn/s3/?q={keyword}&t=all&c=ab"
        text = _request(url)
        results = []
        for match in re.finditer(r'"([^"]+)"', text):
            # 先按 ^ 拆开多条结果
            raw_hints = match.group(1).split('^')
            for hint in raw_hints:
                parts = hint.split('~')
                if len(parts) >= 3:
                    market = parts[0]    # "sz" / "sh" / "bj"
                    code_num = parts[1]  # "000001"
                    name = _decode_unicode_escapes(parts[2])      # 解码 \uXXXX → 中文
                    # 只收A股：市场必须是 sz/sh/bj，代码必须是纯数字
                    if market in ('sz', 'sh', 'bj') and code_num.isdigit():
                        full_code = market + code_num  # "sz000001"
                        results.append({'code': full_code, 'name': name})
        return results[:20]
    except Exception as e:
        print(f"[tencent] search error: {e}")
        return []
