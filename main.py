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
# 🔥 [핵심] 블룸버그 스타일 차트 엔진 (mplfinance)
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

market_indices = ["^TNX", "^VIX", "NQ=F"]
news_summary = ""
embed_fields = []
files = {} 

print("📈 [Bloomberg Mode] 프로페셔널 차트 생성 중...")

def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                return f"{r.get('title')} ({r.get('source')})"
        return ""
    except:
        return ""

# 🔥 [NEW] RSI 계산기 (과매수/과매도 판단용)
def calculate_rsi(data, window=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# 🔥 [NEW] 블룸버그 스타일 캔들 차트 생성
def generate_candle_chart(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        # 6개월치 데이터 가져오기
        df = stock.history(period="6mo")
        
        if df.empty: return None

        # 1. 스타일 설정 (블룸버그 다크 테마)
        # 상승: 초록, 하락: 빨강, 배경: 디스코드 다크(#2b2d31)
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', 
                                   wick='inherit', volume='in', ohlc_bars='inherit')
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', 
                               facecolor='#2b2d31', gridcolor='#40444b', gridstyle=':')
        
        # 2. 차트 그리기 (캔들 + 이동평균선 + 거래량)
        buf = io.BytesIO()
        mpf.plot(df, type='candle', style=s, 
                 volume=True, # 거래량 표시
                 mav=(20, 50), # 20일/50일 이평선
                 title=f"\n{ticker_symbol} Daily Chart",
                 savefig=dict(fname=buf, dpi=100, bbox_inches='tight', pad_inches=0.1)
                )
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"❌ {ticker_symbol} 차트 오류: {e}")
        return None

# 3. 시장 지표 (거시)
macro_data = []

# 비트코인
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="5d")
    if not hist.empty:
        btc_price = hist['Close'].iloc[-1]
        btc_prev = hist['Close'].iloc[-2]
        btc_chg = ((btc_price - btc_prev) / btc_prev) * 100
        btc_icon = "🚀" if btc_chg > 0 else "💧"
        btc_str = f"🪙 BTC ${btc_price:,.0f} ({btc_chg:+.2f}%) {btc_icon}"
    else:
        btc_str = "🪙 BTC 대기중"
except:
    btc_str = "🪙 BTC 통신장애"

# 기타 지표
for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            prev = hist['Close'].iloc[-2]
            chg = ((cur - prev) / prev) * 100
            
            if t == "^TNX": name, icon = "금리", "🚨" if chg > 1 else "✅"
            elif t == "^VIX": name, icon = "공포", "😨" if cur > 20 else "😌"
            elif t == "NQ=F": name, icon = "나스닥", "🇺🇸"
            
            if t == "NQ=F": val_str = f"{chg:+.2f}%"
            else: val_str = f"{cur:.2f}"

            macro_data.append(f"{icon} {name} {val_str}")
            news_summary += f"[거시] {name}: {cur} ({chg:.2f}%)\n"
    except: pass

description = f"{btc_str}\n{' | '.join(macro_data)}\n━━━━━━━━━━━━━━━━━━━━"

# 4. 내 종목 분석 (RSI + 캔들차트)
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="6mo") # RSI 계산 위해 넉넉히
        
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            chg = ((current - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            yield_pct = ((current - my_avg) / my_avg) * 100
            
            # 🔥 RSI 계산
            rsi_val = calculate_rsi(hist)
            rsi_state = "중립"
            if rsi_val >= 70: rsi_state = "🔥 과매수(고점주의)"
            elif rsi_val <= 30: rsi_state = "🥶 과매도(저점기회)"
            
            # 차트 생성
            chart_buf = generate_candle_chart(t)
            if chart_buf:
                files[f"{t}.png"] = chart_buf

            # 뉴스
            news_txt = ""
            if abs(chg) >= 3.0: 
                n = get_news(t)
                if n: news_txt = f"\n> 📰 {n[:25]}..."

            news_summary += f"[{t}] {chg:.2f}%, 수익 {yield_pct:.2f}%, RSI {rsi_val:.0f}\n"
            
            embed_fields.append({
                "name": f"💎 **{t}** ${current:.2f} ({chg:+.2f}%)",
                "value": (f"> 수익: **{yield_pct:+.2f}%** (평단 ${my_avg})\n"
                          f"> 지표: RSI **{rsi_val:.0f}** ({rsi_state})\n"
                          f"> 상태: {'🔴 수익' if yield_pct>0 else '🔵 손실'}{news_txt}"),
                "inline": False
            })
    except Exception as e:
        print(f"❌ {t} 분석 오류: {e}")

# 5. AI 분석 & 전송
try:
    prompt = f"상황:\n{news_summary}\n임무: 블룸버그 애널리스트 톤으로 브리핑. RSI 지표와 추세를 보고 매수/매도/홀딩 전략 제시. (한글로)"
    response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
    analysis = response.text
except:
    analysis = "분석 대기 중..."

embed_fields.append({
    "name": "🧠 **Bloomberg Insight**",
    "value": f"```fix\n{analysis}\n```",
    "inline": False
})

payload = {
    "embeds": [{
        "title": "📊 My Bloomberg Terminal",
        "description": description,
        "color": 0xff5f00, # 블룸버그 오렌지 색상
        "fields": embed_fields,
        "footer": {"text": "Powered by Python & Gemini"},
        "timestamp": datetime.now().isoformat()
    }]
}

if files:
    multipart_files = {}
    for filename, buf in files.items():
        multipart_files[filename] = (filename, buf, 'image/png')
    requests.post(discord_url, data={"payload_json": json.dumps(payload)}, files=multipart_files)
else:
    requests.post(discord_url, json=payload)

print("🚀 [전송 완료] 블룸버그 스타일 차트 적용 완료!")

