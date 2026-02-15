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
# 🔥 [확인] mplfinance 로딩 시도 (여기서 실패하면 로그에 뜸)
try:
    import matplotlib
    matplotlib.use('Agg') 
    import mplfinance as mpf
    print("✅ mplfinance 로딩 성공")
except ImportError as e:
    print(f"❌ mplfinance 로딩 실패: {e}")
    print("👉 requirements.txt 파일을 확인하세요!")
    mpf = None
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

print("🚀 [Debug Mode] 봇 가동 시작...")

def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                return f"{r.get('title')} ({r.get('source')})"
        return ""
    except:
        return ""

# RSI 계산
def calculate_rsi(data, window=14):
    try:
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50 # 에러 시 중간값

# 차트 생성 (안전 모드)
def generate_candle_chart(ticker_symbol):
    if mpf is None: return None # 라이브러리 없으면 패스
    
    print(f"🎨 {ticker_symbol} 차트 그리는 중...")
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="6mo")
        
        if df.empty:
            print(f"⚠️ {ticker_symbol} 데이터 없음")
            return None

        # 스타일 설정 (기본 스타일 사용해서 에러 방지)
        s = mpf.make_mpf_style(base_mpf_style='nightclouds', facecolor='#2b2d31')
        
        buf = io.BytesIO()
        mpf.plot(df, type='candle', style=s, 
                 volume=True, mav=(20, 50),
                 title=f"\n{ticker_symbol}",
                 savefig=dict(fname=buf, dpi=100, bbox_inches='tight')
                )
        buf.seek(0)
        print(f"✅ {ticker_symbol} 차트 완성")
        return buf
    except Exception as e:
        print(f"❌ {ticker_symbol} 차트 오류: {e}")
        return None

# 3. 시장 지표
print("📊 시장 데이터 수집 중...")
macro_data = []

# 비트코인
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="5d")
    if not hist.empty:
        btc_price = hist['Close'].iloc[-1]
        btc_chg = ((btc_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        btc_str = f"🪙 BTC ${btc_price:,.0f} ({btc_chg:+.2f}%)"
    else:
        btc_str = "🪙 BTC 대기중"
except:
    btc_str = "🪙 BTC 통신장애"

for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            if t == "NQ=F": val = f"{chg:+.2f}%"
            else: val = f"{cur:.2f}"
            macro_data.append(f"{t.replace('^','')} {val}")
    except: pass

description = f"{btc_str}\n{' | '.join(macro_data)}\n━━━━━━━━━━━━━━━━━━━━"

# 4. 포트폴리오 분석
print("💎 내 종목 분석 중...")
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="6mo")
        
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            chg = ((current - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            yield_pct = ((current - my_avg) / my_avg) * 100
            rsi = calculate_rsi(hist)
            
            # 차트 시도
            chart_buf = generate_candle_chart(t)
            if chart_buf:
                files[f"{t}.png"] = chart_buf

            news_txt = ""
            if abs(chg) >= 3.0:
                n = get_news(t)
                if n: news_txt = f"\n> 📰 {n[:25]}..."

            news_summary += f"[{t}] {chg:.2f}%, RSI {rsi:.0f}\n"
            
            embed_fields.append({
                "name": f"💎 **{t}** ${current:.2f} ({chg:+.2f}%)",
                "value": f"> 수익: **{yield_pct:+.2f}%**\n> RSI: **{rsi:.0f}**{news_txt}",
                "inline": False
            })
    except Exception as e:
        print(f"❌ {t} 분석 중 에러: {e}")

# 5. 전송
print("📨 디스코드로 전송 준비...")
payload = {
    "embeds": [{
        "title": "📊 Debug Report",
        "description": description,
        "color": 0xff5f00,
        "fields": embed_fields,
        "footer": {"text": "Debug Mode Active"},
        "timestamp": datetime.now().isoformat()
    }]
}

try:
    if files:
        print(f"📦 차트 {len(files)}개 포함 전송 시도...")
