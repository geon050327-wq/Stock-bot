import os
import requests
from google import genai
import yfinance as yf
from duckduckgo_search import DDGS
from datetime import datetime
import json
import io
import pandas as pd

# ---------------------------------------------------------
# 🔥 [필수] 모니터 없는 서버 설정
import matplotlib
matplotlib.use('Agg') 
import mplfinance as mpf
# ---------------------------------------------------------

# 1. 설정
api_key = os.environ['GEMINI_API_KEY']
discord_url = os.environ['DISCORD_WEBHOOK']
client = genai.Client(api_key=api_key)

# 2. 포트폴리오
my_portfolio = {
    "IREN": 41.79, 
    "PL": 15.84
}

# 장기 투자자를 위한 매크로 (달러, 금리, 나스닥)
market_indices = ["DX-Y.NYB", "^TNX", "NQ=F"] 
news_summary = ""
embed_fields = []
files = {} 

print("🦅 [Pure Narrative Mode] 유동성과 내러티브 분석 중...")

# 뉴스 가져오기
def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                title = r.get('title', '제목 없음')
                source = r.get('source', '뉴스')
                url = r.get('url', '')
                if url: return f"[{title}]({url}) - {source}"
                else: return f"{title} - {source}"
        return ""
    except: return ""

# 차트 (장기 추세용 200일선)
def generate_long_term_chart(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="1y") 
        if df.empty: return None

        # 스타일: 디스코드 다크 테마
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', 
                                   wick='inherit', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', 
                               facecolor='#2b2d31', gridcolor='#40444b', gridstyle=':')
        
        buf = io.BytesIO()
        # 50일/200일 이평선 표시
        mpf.plot(df, type='candle', style=s, 
                 volume=True, mav=(50, 200), 
                 title=f"\n{ticker_symbol} (1 Year Trend)",
                 savefig=dict(fname=buf, dpi=100, bbox_inches='tight', pad_inches=0.1)
                )
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"❌ {ticker_symbol} 차트 실패: {e}")
        return None

# 3. 매크로 유동성 체크
macro_data = []
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="5d")
    btc_p = hist['Close'].iloc[-1]
    btc_chg = ((btc_p - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
    btc_str = f"🪙 BTC ${btc_p:,.0f} ({btc_chg:+.2f}%)"
except: btc_str = "🪙 BTC 대기"

for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            
            if t == "DX-Y.NYB": name, icon = "달러($)", "💵"
            elif t == "^TNX": name, icon = "금리(10Y)", "🏦"
            elif t == "NQ=F": name, icon = "나스닥", "🇺🇸"
            else: name, icon = t, ""

            val_str = f"{cur:.2f}" if "NQ" not in t else f"{chg:+.2f}%"
            macro_data.append(f"{icon} {name} {val_str}")
            news_summary += f"[매크로] {name}: {cur} ({chg:.2f}%)\n"
    except: pass

description = f"{btc_str}\n{' | '.join(macro_data)}\n━━━━━━━━━━━━━━━━━━━━"

# 4. 내 종목 분석 (PSR 삭제, 내러티브 집중)
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="1y")
        info = stock.info
        
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            yield_pct = ((cur - my_avg) / my_avg) * 100
            market_cap = info.get('marketCap', 0) / 1000000000 # Billions

            # 장기 추세 판독 (200일선 기준)
            ma200 = hist['Close'].rolling(window=200).mean().iloc[-1]
            if cur > ma200:
                trend = "📈 강세장 (Bull)"
                trend_color = "🟢"
            else:
                trend = "📉 약세장 (Bear)"
                trend_color = "🔴"

            # 차트 생성
            chart_buf = generate_long_term_chart(t)
            if chart_buf: files[f"{t}.png"] = chart_buf

            # 뉴스
            n = get_news(t)
            news_txt = f"\n> 📰 {n}" if n else ""

            # AI에게 보낼 요약 (PSR 제거됨)
            news_summary += f"[{t}] 시총 ${market_cap:.2f}B, 추세: {trend}, 뉴스: {n}\n"
            
            embed_fields.append({
                "name": f"💎 **{t}** (Market Cap: ${market_cap:.2f}B)",
                "value": f"> 수익: **{yield_pct:+.2f}%**\n> 추세: {trend_color} **{trend}**{news_txt}",
                "inline": False
            })
    except Exception as e:
        print(f"❌ {t} 에러: {e}")

# 5. AI 분석 (유동성 & 내러티브 중심)
try:
    prompt = f"""
    [상황]
    {news_summary}
    [임무]
    당신은 '유동성(Liquidity)과 내러티브(Narrative)'를 중시하는 장기 투자자입니다.
    1. PSR, PER 같은 가치평가 지표는 무시하고, 오직 '성장 스토리'가 유효한지만 판단하세요.
    2. 매크로 환경(금리/달러)이 현재의 내러티브를 뒷받침하는지 분석하세요.
    3. 단기 등락은 무시하고 큰 흐름만 짚어주세요.
    4. 말투: 간결하고 통찰력 있게. (한글)
    """
    response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
    analysis = response.text
except: analysis = "내러티브 분석 대기 중..."

embed_fields.append({"name": "🧠 **Narrative Insight**", "value": f"```fix\n{analysis}\n```", "inline": False})

payload = {
    "embeds": [{
        "title": "🏛️ Narrative & Liquidity Report",
        "description": description,
        "color": 0x5865F2,
        "fields": embed_fields,
        "timestamp": datetime.now().isoformat()
    }]
}

if files:
    multipart_files = {k: (k, v, 'image/png') for k, v in files.items()}
    requests.post(discord_url, data={"payload_json": json.dumps(payload)}, files=multipart_files)
else:
    requests.post(discord_url, json=payload)

print("🚀 [전송 완료] PSR 제거됨")
