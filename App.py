import streamlit as st
from google import genai
from duckduckgo_search import DDGS
import time

# --- 1. 보안 키 불러오기 ---
# Streamlit Secrets(비밀 금고)에 저장된 키를 가져옵니다.
api_key = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=api_key)

# --- 2. 인터넷 실시간 검색 엔진 ---
def search_policy(query):
    try:
        # 정확도를 높이기 위해 검색어에 키워드 추가
        search_keyword = f"{query} 지원금 자격조건 신청방법 공식사이트"
        results = DDGS().text(keywords=search_keyword, max_results=3)
        
        search_context = ""
        if results:
            for r in results:
                search_context += f"제목: {r.get('title')}\n내용: {r.get('body')}\n링크: {r.get('href')}\n\n"
            return search_context
        else:
            return "검색 결과가 없습니다."
    except Exception as e:
        return f"검색 중 오류 발생: {e}"

# --- 3. 웹페이지 UI 설정 ---
st.set_page_config(page_title="청년 혜택 사이다 번역기", page_icon="💡", layout="centered")

st.title("💡 인스타 DM 구걸 그만! 청년 혜택 번역기")
st.markdown("""
**복잡한 관공서 PDF, 더 이상 읽지 마세요.** 🙅‍♂️
지원금 이름만 입력하면 AI가 실시간으로 문서를 검색하여 **'얼마를, 누가, 어떻게'** 받는지 3초 만에 팩트 체크해 드립니다.
""")

# 검색창
query = st.text_input("🔎 궁금한 지원금 이름을 입력하세요 (예: 청년도약계좌, 내일준비적금)", placeholder="지원금 이름을 입력하고 엔터를 치세요!")

# 버튼을 누르면 작동
if st.button("진짜 혜택 팩트체크 🚀"):
    if query:
        with st.spinner(f"인터넷에서 '{query}' 공식 문서를 뒤지는 중... 🕵️‍♂️"):
            # 1. 인터넷 검색 실행
            context = search_policy(query)
            
            # 2. AI에게 번역 지시 (프롬프트)
            prompt = f"""
            당신은 복잡한 행정 문서를 20대 청년의 눈높이에 맞춰 번역해주는 '사이다 정책 번역기'입니다.
            사용자가 '{query}'에 대해 질문했습니다.
            아래는 실시간 인터넷 검색 결과입니다:
            {context}
            
            위 사실(Fact)에 기반하여 아래 3가지 항목만 명확하게 요약하세요. 관공서의 딱딱한 말투는 버리세요.
            정보가 부족하면 억지로 지어내지 말고 '해당 정보를 명확히 찾을 수 없습니다'라고 답변하세요.
            
            반드시 아래의 마크다운 포맷을 그대로 사용하세요:
            
            ### 💰 그래서 나 얼마 받을 수 있는데?
            (지원 금액, 혜택의 크기를 2~3줄로 명확히 작성)
            
            ### ✅ 나도 해당되나? (핵심 조건)
            (나이, 소득, 직업 등 핵심 자격 요건을 글머리 기호로 알기 쉽게 정리)
            
            ### 🔗 팩트체크 및 공식 신청 링크
            (검색 결과에 있는 신뢰할 수 있는 공식 웹사이트 링크를 마크다운 형식으로 제공. 인스타그램이나 블로그 링크는 절대 금지)
            """
            
            try:
                # 3. Gemini에게 답변 받아오기
                response = client.models.generate_content(model='gemini-1.5-flash', contents=prompt)
                
                st.success("✨ 분석 완료! 정부 공식 데이터를 기반으로 번역했습니다.")
                
                # AI의 답변을 보기 좋게 출력
                st.info(response.text)
                
            except Exception as e:
                st.error(f"AI 분석 중 에러가 발생했습니다: {e}")
                
            # 수익화용 배너 (임시)
            st.markdown("---")
            st.markdown("💸 **[스폰서 광고]** 20대 전용 혜택이 쏟아지는 KB 체크카드 발급받기 [자세히 보기](#)")
    else:
        st.warning("지원금 이름을 먼저 입력해주세요! 😅")
