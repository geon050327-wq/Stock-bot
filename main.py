import os
import requests
from google import genai
import yfinance as yf
from duckduckgo_search import DDGS
from datetime import datetime

# 1. 설정
api_key = os.environ['GEMINI_API_KEY']
discord_url = os.environ['DISCORD_WEBHOOK']
client = genai.Client(api_key=api_key)

# 2. 포트폴리오 설정
my_portfolio = {
    "IREN": 41.79, 
    "PL": 15.84
}

# 3. 시장 지표
market_indices = ["^TNX", "^VIX", "NQ=F"]

embed_fields = [] 
news_summary = ""

print("🚀 [GitHub Action] 자동화 브리핑 시작...")

def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                return f"{r.get('title')} ({r.get('source')})"
        return "특이 뉴스 없음"
    except:
        return "뉴스 검색 불가"

# ----------------------------------------
# 4-1. 거시경제 (한 줄 요약)
# ----------------------------------------
macro_data = []

# 비트코인
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="2d")
    if not hist.empty:
        btc_price = hist['Close'].iloc[-1]
        btc_change = ((btc_price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        btc_icon = "🚀" if btc_change > 0 else "💧"
        btc_str = f"🪙 **비트코인:** ${btc_price:,.0f} ({btc_change:+.2f}%) {btc_icon}"
    else:
        btc_str = "🪙 비트코인: 데이터 없음"
except:
    btc_str = "🪙 비트코인: 조회 실패"

# 금리, 공포, 나스닥
for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="2d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            
            if t == "^TNX":
                icon = "🚨" if chg > 1.0 else "✅"
                name = "금리"
                fmt = f"{cur:.2f}%"
            elif t == "^VIX":
                icon = "😨" if cur > 20 else "😌"
                name = "공포"
                fmt = f"{cur:.1f}"
            elif t == "NQ=F":
                icon = "🇺🇸"
                name = "나스닥"
                fmt = f"{chg:+.2f}%"
            
            macro_data.append(f"{icon} {name} **{fmt}**")
            news_summary += f"[거시] {name}: {cur} ({chg}%)\n"
    except:
        pass

macro_line = " | ".join(macro_data)
description_text = f"{btc_str}\n{macro_line}\n━━━━━━━━━━━━━━━━━━━━"

# ----------------------------------------
# 4-2. 포트폴리오 (카드 디자인)
# ----------------------------------------
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        
        # D-Day
        try:
            cal = stock.calendar
            if cal and 'Earnings Date' in cal:
                nxt = cal['Earnings Date'][0]
                days = (nxt.date() - datetime.now().date()).days
                if days == 0: d_day = "🔥 **오늘 실적발표**"
                elif 0 < days <= 14: d_day = f"⏰ **D-{days}**"
                elif days > 0: d_day = f"📅 D-{days}"
                else: d_day = "✅ 발표완료"
            else: d_day = "" 
        except: d_day = ""

        if not hist.empty:
            current = hist['Close'].iloc[-1]
            chg = ((current - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            
            # 유동성
            vol_ratio = (hist['Volume'].iloc[-1] / hist['Volume'].iloc[:-1].mean()) * 100
            if vol_ratio >= 150: vol_str = f"🌊 {vol_ratio:.0f}% (폭발)"
            else: vol_str = f"💧 {vol_ratio:.0f}%"

            # 수익률
            yield_pct = ((current - my_avg) / my_avg) * 100
            yield_icon = "🔴" if yield_pct > 0 else "🔵"
            yield_str = f"{yield_pct:+.2f}%"

            # 뉴스
            news_txt = ""
            if abs(chg) >= 3.0 or vol_ratio >= 150:
                news = get_news(t)
                if news != "특이 뉴스 없음":
                    news_txt = f"\n> 📰 {news[:30]}..."

            news_summary += f"[{t}] 등락 {chg:.2f}%, 수익 {yield_pct:.2f}%, D-Day {d_day}\n"
            
            card_title = f"💎 **{t}** ${current:.2f} ({chg:+.2f}%)"
            card_body = (
                f"> **수익률:** {yield_icon} **{yield_str}** (평단 ${my_avg})\n"
                f"> **상태:** {vol_str}"
            )
            if d_day: card_body += f" | {d_day}"
            card_body += news_txt

            embed_fields.append({
                "name": card_title,
                "value": card_body,
                "inline": False
            })
            
    except Exception as e:
        print(f"❌ {t} 에러: {e}")

# ----------------------------------------
# 5. AI 분석 및 전송
# ----------------------------------------
prompt = f"""
[상황]
{news_summary}
[임무]
펀더멘털 투자자 브리핑.
1. 시장 분위기(금리/공포)가 성장주에 좋은지 나쁜지 한 문장.
2. PL과 IREN 중 더 신경 써야 할 종목 하나만 콕 집어서 조언.
3. 한국어로, 명확하게.
"""

try:
    response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
    analysis = response.text
except:
    analysis = "분석 대기 중..."

embed_fields.append({
    "name": "🧠 **Gemini Insight**",
    "value": f"```fix\n{analysis}\n```",
    "inline": False
})

embed = {
    "title": "📊 My Portfolio Dashboard",
    "description": description_text,
    "color": 0x2b2d31,
    "fields": embed_fields,
    "footer": {
        "text": "Auto Briefing System",
        "icon_url": "https://cdn-icons-png.flaticon.com/512/9696/9696803.png"
    },
    "timestamp": datetime.now().isoformat()
}

requests.post(discord_url, json={"embeds": [embed]})
print("🚀 [전송 완료]")
