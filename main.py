import os
import requests
from google import genai
import yfinance as yf
from duckduckgo_search import DDGS
from datetime import datetime
import matplotlib.pyplot as plt
import io
import json # 🔥 이거 추가됨 (안전하게 보내기 위해 필수)

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
files = {} # 차트 이미지 담을 가방

print("🎨 [Visual Mode] 차트 그리기 및 브리핑 시작...")

def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                return f"{r.get('title')} ({r.get('source')})"
        return "뉴스 없음"
    except:
        return "검색 불가"

# 차트 그리기 함수
def generate_chart(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        hist = stock.history(period="6mo")
        
        if hist.empty: return None

        plt.figure(figsize=(10, 5))
        plt.plot(hist.index, hist['Close'], label='Price', color='#1f77b4', linewidth=2)
        ma50 = hist['Close'].rolling(window=50).mean()
        plt.plot(hist.index, ma50, label='50-Day MA', color='#ff7f0e', linestyle='--')
        plt.title(f"{ticker_symbol} - 6 Month Trend")
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close()
        return buf
    except Exception as e:
        print(f"❌ {ticker_symbol} 차트 오류: {e}")
        return None

# 3. 시장 지표 (거시)
macro_data = []
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="2d")
    if not hist.empty:
        btc_price = hist['Close'].iloc[-1]
        btc_chg = ((btc_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        btc_str = f"🪙 BTC ${btc_price:,.0f} ({btc_chg:+.2f}%)"
    else:
        btc_str = "🪙 BTC 데이터 없음"
except:
    btc_str = "🪙 BTC 조회 실패"

for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="2d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            
            if t == "^TNX": name, icon = "금리", "🚨" if chg > 1 else "✅"
            elif t == "^VIX": name, icon = "공포", "😨" if cur > 20 else "😌"
            elif t == "NQ=F": name, icon = "나스닥", "🇺🇸"
            
            macro_data.append(f"{icon} {name} {cur:.2f}")
            news_summary += f"[거시] {name}: {cur} ({chg}%)\n"
    except: pass

description = f"{btc_str}\n{' | '.join(macro_data)}\n━━━━━━━━━━━━━━━━━━━━"

# 4. 내 종목 분석
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        
        if not hist.empty:
            current = hist['Close'].iloc[-1]
            chg = ((current - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            yield_pct = ((current - my_avg) / my_avg) * 100
            
            # 차트 생성
            chart_buf = generate_chart(t)
            if chart_buf:
                files[f"{t}.png"] = chart_buf

            news = ""
            if abs(chg) >= 3.0: 
                n = get_news(t)
                if n != "뉴스 없음": news = f"\n> 📰 {n[:30]}..."

            news_summary += f"[{t}] {chg:.2f}%, 수익 {yield_pct:.2f}%\n"
            
            embed_fields.append({
                "name": f"💎 **{t}** ${current:.2f} ({chg:+.2f}%)",
                "value": f"> 수익: **{yield_pct:+.2f}%** (평단 ${my_avg})\n> 상태: {'🔴 수익' if yield_pct>0 else '🔵 손실'}{news}",
                "inline": False
            })
    except Exception as e:
        print(f"❌ {t} 분석 오류: {e}")

# 5. AI 분석 & 전송
try:
    prompt = f"상황:\n{news_summary}\n임무: 펀더멘털 투자자에게 보내는 3줄 요약. 시장 분위기와 내 종목(PL, IREN) 대응 전략."
    response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
    analysis = response.text
except:
    analysis = "분석 대기 중..."

embed_fields.append({

