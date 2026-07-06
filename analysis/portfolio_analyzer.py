"""Deep portfolio analysis — per-stock technical profile + LLM analysis.

For each holding, fetches 30-day K-line, computes 7 technical indicators,
formats a rich profile, and sends to DeepSeek for per-stock analysis.
"""

import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from market_data.Ashare import get_price
from market_data.tencent_api import fetch_stocks_realtime, fetch_indices_realtime, prefix
from analysis.MyTT import MA, EMA, MACD, KDJ, RSI, BOLL, CROSS, REF, HHV, LLV
from analysis.llm_client import get_llm_client


# ─── Indicator computation ─────────────────────────────────────

def compute_indicators(close: np.ndarray, high: np.ndarray, low: np.ndarray,
                       volume: np.ndarray) -> dict:
    """Compute a suite of technical indicators from price arrays.

    Returns a dict of indicator values, each as a float (latest value)
    or a small list of recent values for trending indicators.
    """
    n = len(close)
    if n < 20:
        return {}

    result = {}

    # Moving averages
    ma5 = MA(close, 5)
    ma10 = MA(close, 10)
    ma20 = MA(close, 20)
    result['ma5'] = round(float(ma5[-1]), 2)
    result['ma10'] = round(float(ma10[-1]), 2)
    result['ma20'] = round(float(ma20[-1]), 2)
    # MA relationship
    ma_arrangement = []
    if ma5[-1] > ma10[-1] > ma20[-1]:
        ma_arrangement.append("多头排列(MA5>MA10>MA20)")
    elif ma5[-1] < ma10[-1] < ma20[-1]:
        ma_arrangement.append("空头排列(MA5<MA10<MA20)")
    else:
        if ma5[-1] > ma20[-1]:
            ma_arrangement.append("短期均线在长期上方")
        else:
            ma_arrangement.append("短期均线在长期下方")
    # Price vs MA
    price = close[-1]
    if price > ma5[-1]:
        ma_arrangement.append(f"股价在MA5上方({price:.2f}>{ma5[-1]:.2f})")
    else:
        ma_arrangement.append(f"股价在MA5下方({price:.2f}<{ma5[-1]:.2f})")
    result['ma_status'] = '; '.join(ma_arrangement)

    # MACD
    dif, dea, macd = MACD(close)
    result['dif'] = round(float(dif[-1]), 3)
    result['dea'] = round(float(dea[-1]), 3)
    result['macd'] = round(float(macd[-1]), 3)
    # MACD signal
    if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
        result['macd_signal'] = '金叉(看涨信号)'
    elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
        result['macd_signal'] = '死叉(看跌信号)'
    elif dif[-1] > dea[-1]:
        result['macd_signal'] = 'DIF在DEA上方(偏多)'
    else:
        result['macd_signal'] = 'DIF在DEA下方(偏空)'
    # MACD histogram direction
    if n >= 3 and macd[-1] > macd[-2]:
        result['macd_histogram'] = '红柱增长(动能增强)'
    elif n >= 3 and macd[-1] < macd[-2]:
        result['macd_histogram'] = '绿柱增长(动能减弱)' if macd[-1] < 0 else '红柱缩短(动能减弱)'
    else:
        result['macd_histogram'] = '动能持平'

    # KDJ
    k, d, j = KDJ(close, high, low)
    result['k'] = round(float(k[-1]), 1)
    result['d'] = round(float(d[-1]), 1)
    result['j'] = round(float(j[-1]), 1)
    if k[-1] > 80 and d[-1] > 80:
        result['kdj_status'] = '超买区(K>80,D>80)'
    elif k[-1] < 20 and d[-1] < 20:
        result['kdj_status'] = '超卖区(K<20,D<20)'
    elif k[-1] > d[-1]:
        result['kdj_status'] = 'K在D上方(偏多)'
    else:
        result['kdj_status'] = 'K在D下方(偏空)'

    # BOLL
    upper, mid, lower = BOLL(close, 20)
    result['boll_upper'] = round(float(upper[-1]), 2)
    result['boll_mid'] = round(float(mid[-1]), 2)
    result['boll_lower'] = round(float(lower[-1]), 2)
    boll_width = (upper[-1] - lower[-1]) / mid[-1] * 100 if mid[-1] else 0
    result['boll_width'] = round(float(boll_width), 1)
    if price >= upper[-1]:
        result['boll_status'] = f"触及上轨(超强,可能存在回调压力)"
    elif price <= lower[-1]:
        result['boll_status'] = f"触及下轨(超弱,可能存在反弹机会)"
    elif price > mid[-1]:
        pct_to_upper = round((upper[-1] - price) / price * 100, 1)
        result['boll_status'] = f"中轨上方,距上轨{pct_to_upper}%"
    else:
        pct_to_lower = round((price - lower[-1]) / price * 100, 1)
        result['boll_status'] = f"中轨下方,距下轨{pct_to_lower}%"

    # RSI
    rsi6 = RSI(close, 6)
    rsi14 = RSI(close, 14)
    rsi24 = RSI(close, 24)
    result['rsi6'] = round(float(rsi6[-1]), 1)
    result['rsi14'] = round(float(rsi14[-1]), 1)
    result['rsi24'] = round(float(rsi24[-1]), 1)
    if rsi14[-1] > 70:
        result['rsi_status'] = f'超买(RSI14={rsi14[-1]:.0f})'
    elif rsi14[-1] < 30:
        result['rsi_status'] = f'超卖(RSI14={rsi14[-1]:.0f})'
    elif rsi14[-1] > 50:
        result['rsi_status'] = f'偏强(RSI14={rsi14[-1]:.0f})'
    else:
        result['rsi_status'] = f'偏弱(RSI14={rsi14[-1]:.0f})'

    # Volume
    vol_ma5 = MA(volume, 5)
    vol_ma20 = MA(volume, 20)
    if vol_ma5[-1] and vol_ma20[-1] and vol_ma20[-1] > 0:
        vol_ratio = round(float(vol_ma5[-1] / vol_ma20[-1]), 2)
        result['vol_ratio'] = vol_ratio
        if vol_ratio > 1.5:
            result['vol_status'] = f"放量(量比{vol_ratio}),近期成交活跃"
        elif vol_ratio > 1.0:
            result['vol_status'] = f"温和放量(量比{vol_ratio})"
        elif vol_ratio > 0.5:
            result['vol_status'] = f"缩量(量比{vol_ratio}),交投清淡"
        else:
            result['vol_status'] = f"极度缩量(量比{vol_ratio})"
    else:
        result['vol_ratio'] = None
        result['vol_status'] = '量能数据不足'

    # Price stats
    result['close_latest'] = round(float(close[-1]), 2)
    result['high_20d'] = round(float(max(high[-20:])), 2)
    result['low_20d'] = round(float(min(low[-20:])), 2)
    if close[-1] and close[-2] and close[-2] != 0:
        result['chg_1d'] = round(float((close[-1] - close[-2]) / close[-2] * 100), 2)
    else:
        result['chg_1d'] = 0
    if close[-1] and close[-6] and close[-6] != 0:
        result['chg_5d'] = round(float((close[-1] - close[-6]) / close[-6] * 100), 2)
    else:
        result['chg_5d'] = 0

    # Support / Resistance (simple: recent swing high/low + MA20 + BOLL)
    result['resistance'] = round(float(max(high[-10:])), 2)  # 近10日最高
    result['support'] = round(float(min(low[-10:])), 2)      # 近10日最低

    return result


# ─── Per-stock data fetch ──────────────────────────────────────

def build_stock_profile(stock_code: str, stock_name: str, cost_price: float) -> Optional[dict]:
    """Fetch K-line + realtime, compute indicators, return a complete profile dict."""
    full_code = prefix(stock_code)

    # Fetch daily K-line (30 days)
    try:
        df = get_price(full_code, frequency='1d', count=35)
        if df is None or df.empty:
            return None
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
    except Exception as e:
        print(f"[portfolio] K-line fetch failed for {stock_code}: {e}")
        return None

    # Compute indicators
    indicators = compute_indicators(close, high, low, volume)
    if not indicators:
        return None

    # Fetch realtime price
    realtime = fetch_stocks_realtime([stock_code])
    rt = realtime.get(stock_code, {})

    current_price = rt.get('price', indicators.get('close_latest', 0))
    today_pct = rt.get('pct', indicators.get('chg_1d', 0))
    today_high = rt.get('high', 0)
    today_low = rt.get('low', 0)
    today_open = rt.get('open', 0)

    # P&L
    if cost_price and cost_price > 0:
        pnl_pct = round((current_price - cost_price) / cost_price * 100, 2)
    else:
        pnl_pct = 0

    return {
        'code': stock_code,
        'name': stock_name,
        'cost': cost_price,
        'current_price': current_price,
        'today_pct': today_pct,
        'today_open': today_open,
        'today_high': today_high,
        'today_low': today_low,
        'pnl_pct': pnl_pct,
        'indicators': indicators,
    }


# ─── Formatter (text profile for LLM) ──────────────────────────

STOCK_PROFILE_TEMPLATE = """## {name}（{code}）

### 基本数据
- 成本价: {cost:.2f}
- 现价: {current_price:.2f}（今日 {today_pct:+.2f}%）
- 今日区间: {today_open:.2f} 开 → 最高 {today_high:.2f} / 最低 {today_low:.2f}
- 持仓浮盈/浮亏: {pnl_pct:+.2f}%

### 技术指标画像
- 收盘价: {close_latest}
- 均线: MA5={ma5}, MA10={ma10}, MA20={ma20}
- 均线状态: {ma_status}
- MACD: DIF={dif}, DEA={dea}, MACD柱={macd}
- MACD信号: {macd_signal}, {macd_histogram}
- KDJ: K={k}, D={d}, J={j} — {kdj_status}
- BOLL: 上轨={boll_upper}, 中轨={boll_mid}, 下轨={boll_lower}
- BOLL状态: {boll_status}, 带宽{boll_width}%
- RSI(6/14/24): {rsi6}/{rsi14}/{rsi24} — {rsi_status}
- 成交量: {vol_status}
- 近20日最高: {high_20d}, 近20日最低: {low_20d}
- 近10日阻力位: {resistance}, 近10日支撑位: {support}
- 1日涨跌幅: {chg_1d:+.2f}%, 5日涨跌幅: {chg_5d:+.2f}%"""


def format_stock_profile(profile: dict) -> str:
    """Format a single stock's profile into LLM-readable text."""
    ind = profile['indicators']
    return STOCK_PROFILE_TEMPLATE.format(
        name=profile['name'], code=profile['code'],
        cost=profile['cost'], current_price=profile['current_price'],
        today_pct=profile['today_pct'],
        today_open=profile['today_open'], today_high=profile['today_high'],
        today_low=profile['today_low'], pnl_pct=profile['pnl_pct'],
        **ind
    )


# ─── LLM analysis ──────────────────────────────────────────────

PORTFOLIO_ANALYSIS_PROMPT = """你是一位拥有12年A股实战经验的职业交易员，擅长技术分析和持仓管理。
你正在对用户的持仓股进行逐只深度分析。

## 分析要求
对每只股票，请从以下维度进行客观、具体的分析（不要泛泛而谈）：

### 1. 趋势判断
- 当前处于什么趋势？（上升/下跌/震荡/转折）
- 均线排列给出的信号是什么？
- 短期（1-3天）和中期（1-2周）趋势是否一致？

### 2. 关键价位
- 最近的支撑位和压力位在哪里？（结合MA、BOLL、近期高低点）
- 当前价格离关键位还有多远？
- 突破哪个价位意味着趋势改变？

### 3. 指标信号
- MACD/KDJ/RSI分别给出了什么信号？
- 这些信号是共振还是背离？
- 成交量是否配合当前走势？

### 4. 风险点
- 这只票当前最大的风险是什么？（追高/破位/缩量/指标背离等）
- 有没有需要警惕的异常信号？

### 5. 操作倾向
- 基于以上分析，给出操作方向倾向：持有 / 减仓观察 / 可加仓 / 倾向清仓
- 说明核心理由（一句话）
- 如果建议操作，给出一个参考价位

## 输出格式
请输出以下JSON对象（整体用对象包裹，stocks字段内是数组）：

{
  "stocks": [
    {
      "code": "股票代码",
      "name": "股票名称",
      "trend": "上升趋势/下降趋势/区间震荡/潜在转折",
      "trend_detail": "趋势的具体描述（50字以内）",
      "support": "支撑位(价格)",
      "resistance": "压力位(价格)",
      "signal_summary": "各指标信号汇总（如：MACD金叉+KDJ超买+RSI偏强,量能配合）",
      "risk": "当前最大风险点",
      "assessment": "持有/减仓观察/可加仓/倾向清仓",
      "assessment_reason": "核心理由（15字以内）",
      "reference_price": 参考价位数字,
      "full_analysis": "完整分析（150-200字）"
    }
  ]
}

注意：务必输出合法的JSON对象，不要用markdown代码块包裹。
]

注意：
- 分析要具体，要引用实际的指标数值
- 不要模棱两可，给出明确的倾向
- 如果是减仓或清仓倾向，说明什么条件下可以改变判断
- 不要给出"建议买入/卖出"这种指令性语言，用"倾向"表达"""


def analyze_portfolio(holdings: list[dict]) -> list[dict]:
    """Run deep analysis on all holdings.

    Args:
        holdings: list of holding dicts from DB (must have stock_code, stock_name, cost_price)

    Returns:
        list of per-stock analysis dicts, each with 'profile' and 'analysis' keys.
    """
    llm = get_llm_client()

    # Step 1: Build profiles for all holdings (concurrent fetches)
    profiles = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {
            ex.submit(build_stock_profile, h['stock_code'], h['stock_name'], h.get('cost_price', 0)): i
            for i, h in enumerate(holdings)
        }
        profile_map = {}
        for f in as_completed(futures):
            idx = futures[f]
            profile = f.result()
            if profile:
                profile_map[idx] = profile
        profiles = [profile_map[i] for i in sorted(profile_map)]

    if not profiles:
        return []

    # Step 2: Format each profile and combine into one message
    profile_texts = []
    for p in profiles:
        profile_texts.append(format_stock_profile(p))
    user_message = "\n\n---\n\n".join(profile_texts)

    # Step 3: Send to LLM — use raw chat + manual parse for max flexibility
    try:
        from analysis.llm_client import extract_json
        raw_text = llm.chat(
            system_prompt=PORTFOLIO_ANALYSIS_PROMPT,
            user_message=user_message,
            max_tokens=4096,
            json_mode=True,
        )
        parsed = extract_json(raw_text)

        # Handle both array and dict responses
        if isinstance(parsed, list):
            analyses = parsed
        elif isinstance(parsed, dict):
            for key in ['stocks', 'analysis', 'holdings', 'results']:
                if key in parsed and isinstance(parsed[key], list):
                    analyses = parsed[key]
                    break
            else:
                analyses = next((v for v in parsed.values() if isinstance(v, list)), [])
        else:
            analyses = []

        if not analyses:
            print(f"[portfolio] WARNING: Could not extract analysis list. raw (first 800): {raw_text[:800]}")
    except Exception as e:
        print(f"[portfolio] LLM analysis failed: {e}")
        return [{'profile': p, 'analysis': {
            'trend': 'API调用失败', 'trend_detail': str(e),
            'signal_summary': str(e)[:80],
            'assessment': '持有', 'assessment_reason': '分析失败',
            'reference_price': 0, 'full_analysis': f'DeepSeek API错误: {e}',
        }} for p in profiles]

    # Step 4: Match analysis results to profiles
    results = []
    for p in profiles:
        matched = None
        for a in analyses:
            if isinstance(a, dict) and (
                a.get('code') == p['code'] or a.get('name') == p['name']
            ):
                matched = a
                break
        results.append({
            'profile': p,
            'analysis': matched or {
                'trend': '未知', 'trend_detail': '分析结果解析失败',
                'support': '-', 'resistance': '-',
                'signal_summary': '-', 'risk': '-',
                'assessment': '持有', 'assessment_reason': '无法分析',
                'reference_price': 0, 'full_analysis': 'LLM返回解析失败，请重试',
            }
        })

    return results
