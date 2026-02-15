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
# 🔥 [필수 설정] 모니터 없는 서버에서 차트 그리기
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

print("📈 [Bloomberg Mode] 강제 구동 시작...")

def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                return f"{r.get('title')} ({r.get('source')})"
        return ""
    except:
        return ""

def calculate_rsi(data, window=14):
    try:
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50

# 🔥 블룸버그 스타일 차트 생성 (실패 시 에러 뿜고 전사)
def generate_candle_chart(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="6mo")
        
        if df.empty: return None

        # 스타일: 디스코드 다크 테마에 맞춤
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', 
                                   wick='inherit', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', 
                               facecolor='#2b2d31', gridcolor='#40444b', gridstyle=':')
        
        buf = io.BytesIO()
        mpf.plot(df, type='candle', style=s, 
                 volume=True, mav=(20, 50),
                 title=f"\n{ticker_symbol}",
                 savefig=dict(fname=buf, dpi=100, bbox_inches='tight', pad_inches=0.1)
                )
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"❌ {ticker_symbol} 차트 그리기 실패: {e}")
        return None

# 3. 시장 지표
macro_data = []
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="5d")
    if not hist.empty:
        btc_p = hist['Close'].iloc[-1]
        btc_chg = ((btc_p - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        btc_str = f"🪙 BTC ${btc_p:,.0f} ({btc_chg:+.2f}%)"
    else: btc_str = "🪙 BTC 대기"
except: btc_str = "🪙 BTC 통신장애"

for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            val = f"{chg:+.2f}%" if "NQ" in t else f"{cur:.2f}"
            
            icon = ""
            if t == "^TNX": icon = "🚨" if chg > 1 else "✅"
            elif t == "^VIX": icon = "😨" if cur > 20 else "😌"
            
            macro_data.append(f"{icon} {t.replace('^','')} {val}")
            news_summary += f"[거시] {t}: {cur} ({chg:.2f}%)\n"
    except: pass

description = f"{btc_str}\n{' | '.join(macro_data)}\n━━━━━━━━━━━━━━━━━━━━"

# 4. 분석
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="6mo")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            yield_pct = ((current := cur) - my_avg) / my_avg * 100
            rsi = calculate_rsi(hist)

            # 차트 생성 (무조건 블룸버그)
            chart_buf = generate_candle_chart(t)
            if chart_buf: files[f"{t}.png"] = chart_buf

            news_txt = ""
            if abs(chg) >= 3.0:
                n = get_news(t)
                if n: news_txt = f"\n> 📰 {n[:25]}..."
            
            # RSI 상태 메시지
            rsi_msg = "중립"
            if rsi >= 70: rsi_msg = "🔥 과매수"
            elif rsi <= 30: rsi_msg = "🥶 과매도"

            news_summary += f"[{t}] {chg:.2f}%, RSI {rsi:.0f}\n"
            
            embed_fields.append({
                "name": f"💎 **{t}** ${cur:.2f} ({chg:+.2f}%)",
                "value": f"> 수익: **{yield_pct:+.2f}%**\n> RSI: **{rsi:.0f}** ({rsi_msg}){news_txt}",
                "inline": False
            })
    except Exception as e:
        print(f"❌ {t} 에러: {e}")

# 5. 전송
try:
    prompt = f"상황:\n{news_summary}\n임무: 블룸버그 톤으로 3줄 요약. (한글)"
    response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
    analysis = response.text
except: analysis = "분석 대기 중..."

embed_fields.append({"name": "🧠 **Bloomberg Insight**", "value": f"```fix\n{analysis}\n```", "inline": False})

payload = {
    "embeds": [{
        "title": "📊 My Bloomberg Terminal",
        "description": description,
        "color": 0xff5f00,
        "fields": embed_fields,
        "timestamp": datetime.now().isoformat()
    }]
}

if files:
    multipart_files = {k: (k, v, 'image/png') for k, v in files.items()}
    requests.post(discord_url, data={"payload_json": json.dumps(payload)}, files=multipart_files)
else:
    requests.post(discord_url, json=payload)

print("🚀 [전송 완료]")
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
# 🔥 [필수 설정] 모니터 없는 서버에서 차트 그리기
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

print("📈 [Bloomberg Mode] 강제 구동 시작...")

def get_news(symbol):
    try:
        results = DDGS().news(keywords=f"{symbol} stock news", max_results=1)
        if results:
            for r in results:
                return f"{r.get('title')} ({r.get('source')})"
        return ""
    except:
        return ""

def calculate_rsi(data, window=14):
    try:
        delta = data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1]
    except:
        return 50

# 🔥 블룸버그 스타일 차트 생성 (실패 시 에러 뿜고 전사)
def generate_candle_chart(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="6mo")
        
        if df.empty: return None

        # 스타일: 디스코드 다크 테마에 맞춤
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', 
                                   wick='inherit', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds', 
                               facecolor='#2b2d31', gridcolor='#40444b', gridstyle=':')
        
        buf = io.BytesIO()
        mpf.plot(df, type='candle', style=s, 
                 volume=True, mav=(20, 50),
                 title=f"\n{ticker_symbol}",
                 savefig=dict(fname=buf, dpi=100, bbox_inches='tight', pad_inches=0.1)
                )
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"❌ {ticker_symbol} 차트 그리기 실패: {e}")
        return None

# 3. 시장 지표
macro_data = []
try:
    btc = yf.Ticker("BTC-USD")
    hist = btc.history(period="5d")
    if not hist.empty:
        btc_p = hist['Close'].iloc[-1]
        btc_chg = ((btc_p - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
        btc_str = f"🪙 BTC ${btc_p:,.0f} ({btc_chg:+.2f}%)"
    else: btc_str = "🪙 BTC 대기"
except: btc_str = "🪙 BTC 통신장애"

for t in market_indices:
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="5d")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            val = f"{chg:+.2f}%" if "NQ" in t else f"{cur:.2f}"
            
            icon = ""
            if t == "^TNX": icon = "🚨" if chg > 1 else "✅"
            elif t == "^VIX": icon = "😨" if cur > 20 else "😌"
            
            macro_data.append(f"{icon} {t.replace('^','')} {val}")
            news_summary += f"[거시] {t}: {cur} ({chg:.2f}%)\n"
    except: pass

description = f"{btc_str}\n{' | '.join(macro_data)}\n━━━━━━━━━━━━━━━━━━━━"

# 4. 분석
for t, my_avg in my_portfolio.items():
    try:
        stock = yf.Ticker(t)
        hist = stock.history(period="6mo")
        if not hist.empty:
            cur = hist['Close'].iloc[-1]
            chg = ((cur - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            yield_pct = ((current := cur) - my_avg) / my_avg * 100
            rsi = calculate_rsi(hist)

            # 차트 생성 (무조건 블룸버그)
            chart_buf = generate_candle_chart(t)
            if chart_buf: files[f"{t}.png"] = chart_buf

            news_txt = ""
            if abs(chg) >= 3.0:
                n = get_news(t)
                if n: news_txt = f"\n> 📰 {n[:25]}..."
            
            # RSI 상태 메시지
            rsi_msg = "중립"
            if rsi >= 70: rsi_msg = "🔥 과매수"
            elif rsi <= 30: rsi_msg = "🥶 과매도"

            news_summary += f"[{t}] {chg:.2f}%, RSI {rsi:.0f}\n"
            
            embed_fields.append({
                "name": f"💎 **{t}** ${cur:.2f} ({chg:+.2f}%)",
                "value": f"> 수익: **{yield_pct:+.2f}%**\n> RSI: **{rsi:.0f}** ({rsi_msg}){news_txt}",
                "inline": False
            })
    except Exception as e:
        print(f"❌ {t} 에러: {e}")

# 5. 전송
try:
    prompt = f"상황:\n{news_summary}\n임무: 블룸버그 톤으로 3줄 요약. (한글)"
    response = client.models.generate_content(model='gemini-flash-latest', contents=prompt)
    analysis = response.text
except: analysis = "분석 대기 중..."

embed_fields.append({"name": "🧠 **Bloomberg Insight**", "value": f"```fix\n{analysis}\n```", "inline": False})

payload = {
    "embeds": [{
        "title": "📊 My Bloomberg Terminal",
        "description": description,
        "color": 0xff5f00,
        "fields": embed_fields,
        "timestamp": datetime.now().isoformat()
    }]
}

if files:
    multipart_files = {k: (k, v, 'image/png') for k, v in files.items()}
    requests.post(discord_url, data={"payload_json": json.dumps(payload)}, files=multipart_files)
else:
    requests.post(discord_url, json=payload)

print("🚀 [전송 완료]")

