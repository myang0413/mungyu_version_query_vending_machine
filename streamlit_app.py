import streamlit as st
import requests
import pandas as pd
import altair as alt
import json
from datetime import datetime
import base64

# 페이지 설정
st.set_page_config(
    page_title="Text-to-SQL Query Vending Machine",
    page_icon="🔍",
    layout="wide"
)

# 다국어 지원
LANGUAGES = {
    "한국어": {
        "title": "🔍 Text-to-SQL 쿼리 자판기",
        "subtitle": "자연어로 데이터베이스에 질문하세요",
        "language": "언어 선택",
        "input_placeholder": "예: 가장 많이 대여된 영화 10개를 보여줘",
        "input_label": "질문을 입력하세요",
        "run_button": "🚀 쿼리 실행",
        "clear_button": "🗑️ 대화 기록 삭제",
        "answer_header": "💬 답변",
        "chart_header": "📊 데이터 시각화",
        "details_header": "📋 상세 정보",
        "sql_header": "생성된 SQL 쿼리",
        "tables_header": "사용된 테이블",
        "result_header": "쿼리 결과",
        "history_header": "📜 대화 기록",
        "no_result": "결과가 없습니다.",
        "no_chart_data": "차트를 그릴 데이터가 없습니다.",
        "unsupported_chart": "지원하지 않는 차트 타입입니다.",
        "error_api": "API 요청 중 오류가 발생했습니다",
        "error_general": "오류가 발생했습니다",
        "warning_empty": "질문을 입력해주세요.",
        "download_excel": "📥 엑셀로 다운로드",
        "download_chart": "💾 차트 저장",
        "example_questions": "💡 예시 질문",
        "examples": [
            "카테고리별 영화 수를 시각화 해줘",
            "가장 많이 대여한 고객 10명을 보여줘",
            "배우별 출연 영화 수를 보여줘",
            "가장 많은 영화를 대여한 고객의 이름과 대여 횟수를 알려주세요.",
            "액션(Action) 장르의 영화 목록을 보여주세요."
            "배우 PENELOPE GUINESS가 출연한 모든 영화의 제목은 무엇인가요?",
            "등급이 'R'인 모든 영화의 제목과 설명은 무엇인가요?",
            "가장 최근에 가입한 고객 5명은 누구인가요?",
            "가장 많은 수익을 낸 상위 5개의 영화는 무엇인가요?"
        ]
    },
    "English": {
        "title": "🔍 Text-to-SQL Query Vending Machine",
        "subtitle": "Ask your database in natural language",
        "language": "Select Language",
        "input_placeholder": "e.g., Show me the top 10 most rented movies",
        "input_label": "Enter your question",
        "run_button": "🚀 Run Query",
        "clear_button": "🗑️ Clear History",
        "answer_header": "💬 Answer",
        "chart_header": "📊 Data Visualization",
        "details_header": "📋 Details",
        "sql_header": "Generated SQL Query",
        "tables_header": "Tables Used",
        "result_header": "Query Result",
        "history_header": "📜 Conversation History",
        "no_result": "No results.",
        "no_chart_data": "No data available for chart.",
        "unsupported_chart": "Unsupported chart type.",
        "error_api": "API request error",
        "error_general": "An error occurred",
        "warning_empty": "Please enter a question.",
        "download_excel": "📥 Download as Excel",
        "download_chart": "💾 Save Chart",
        "example_questions": "💡 Example Questions",
        "examples": [
            "Visualize the number of movies by category",
            "Top 10 customers by rental count",
            "Show the number of movies per actor",
             "Please provide the name and number of rentals for the customer who rented the most movies.",
            "Show me a list of movies in the Action genre.",
            "What are the titles of all movies starring PENELOPE GUINESS?",
            "What are the titles and descriptions of all movies rated ‘R’?",
            "Who are the 5 most recently registered customers?",
            "What are the top 5 highest-grossing movies?"
        ]
    }
}

# 세션 상태 초기화
if "language" not in st.session_state:
    st.session_state.language = "한국어"
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# 사이드바 설정
with st.sidebar:
    lang = LANGUAGES[st.session_state.language]
    st.header(lang["language"])
    selected_language = st.selectbox(
        "",
        options=["한국어", "English"],
        index=0 if st.session_state.language == "한국어" else 1,
        key="lang_select"
    )
    st.session_state.language = selected_language
    
    # 언어 변경 시 lang 재설정
    lang = LANGUAGES[st.session_state.language]
    
    st.markdown("---")
    st.markdown(f"**{lang['example_questions']}**")
    for example in lang["examples"]:
        st.markdown(f"- {example}")
    
    st.markdown("---")
    if st.button(lang["clear_button"], use_container_width=True):
        st.session_state.conversation_history = []
        st.rerun()

# 메인 화면
lang = LANGUAGES[st.session_state.language]
st.title(lang["title"])
st.markdown(f"### {lang['subtitle']}")

# 질문 입력
if "current_question" in st.session_state:
    question = st.text_input(
        lang["input_label"],
        value=st.session_state.current_question,
        placeholder=lang["input_placeholder"]
    )
    del st.session_state.current_question
else:
    question = st.text_input(
        lang["input_label"],
        placeholder=lang["input_placeholder"]
    )

if st.button(lang["run_button"], type="primary", use_container_width=True):
    if question:
        with st.spinner("⏳ Processing..."):
            try:
                # FastAPI 백엔드에 요청
                response = requests.post(
                    "http://127.0.0.1:8000/query",
                    json={"question": question, "language": st.session_state.language}
                )
                response.raise_for_status()
                data = response.json()
                
                # 대화 기록에 추가
                st.session_state.conversation_history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "question": question,
                    "answer": data["natural_language_response"],
                    "sql_query": data["sql_query"],
                    "chart_type": data.get("chart_type"),
                    "chart_data": data.get("chart_data"),
                    "result": data["result"]
                })
                
                # 결과 표시
                st.success("✅ Query executed successfully!")
                    
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.subheader(lang["answer_header"])
                    st.markdown(data["natural_language_response"])
                
                with col2:
                    # 차트 표시
                    if data.get("chart_type") and data.get("chart_data") and data["chart_type"] != "none":
                        st.subheader(lang["chart_header"])
                        chart_type = data["chart_type"]
                        chart_data = pd.DataFrame(data["chart_data"])
                        
                        if not chart_data.empty and len(chart_data.columns) >= 2:
                            # 데이터 타입을 기반으로 X축과 Y축 자동 결정
                            numeric_cols = [col for col in chart_data.columns if pd.api.types.is_numeric_dtype(chart_data[col])]
                            non_numeric_cols = [col for col in chart_data.columns if not pd.api.types.is_numeric_dtype(chart_data[col])]
                            
                            # Y축은 숫자형 컬럼, X축은 비숫자형 컬럼 (카테고리)
                            if len(numeric_cols) > 0 and len(non_numeric_cols) > 0:
                                y_col = numeric_cols[0]
                                x_col = non_numeric_cols[0]
                            elif len(numeric_cols) >= 2:
                                # 모두 숫자형이면 첫 번째를 X, 두 번째를 Y로
                                x_col = numeric_cols[0]
                                y_col = numeric_cols[1]
                            else:
                                # 기본값: 첫 번째 컬럼을 X, 두 번째를 Y로
                                x_col = chart_data.columns[0]
                                y_col = chart_data.columns[1]
                            
                            x_type = 'quantitative' if pd.api.types.is_numeric_dtype(chart_data[x_col]) else 'nominal'
                            y_type = 'quantitative' if pd.api.types.is_numeric_dtype(chart_data[y_col]) else 'nominal'
                            
                            chart = None
                            if chart_type == 'bar':
                                chart = alt.Chart(chart_data).mark_bar().encode(
                                    x=alt.X(x_col, type=x_type, title=x_col),
                                    y=alt.Y(y_col, type=y_type, title=y_col),
                                    tooltip=list(chart_data.columns)
                                ).properties(height=300).interactive()
                            elif chart_type == 'line':
                                chart = alt.Chart(chart_data).mark_line(point=True).encode(
                                    x=alt.X(x_col, type=x_type, title=x_col),
                                    y=alt.Y(y_col, type=y_type, title=y_col),
                                    tooltip=list(chart_data.columns)
                                ).properties(height=300).interactive()
                            elif chart_type == 'pie':
                                chart = alt.Chart(chart_data).mark_arc().encode(
                                    theta=alt.Theta(field=y_col, type='quantitative'),
                                    color=alt.Color(field=x_col, type='nominal'),
                                    tooltip=list(chart_data.columns)
                                ).properties(height=300)
                            
                            if chart:
                                st.altair_chart(chart, use_container_width=True)
                                
                                # 차트 저장 버튼 (3개 열)
                                col_chart1, col_chart2, col_chart3 = st.columns(3)
                                
                                with col_chart1:
                                    # PNG 형식으로 차트 이미지 다운로드
                                    try:
                                        import vl_convert as vlc
                                        png_data = vlc.vegalite_to_png(chart.to_dict(), scale=2)
                                        st.download_button(
                                            label=f"🖼️ {lang['download_chart']} (PNG)",
                                            data=png_data,
                                            file_name=f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                                            mime="image/png",
                                            use_container_width=True,
                                            help="PNG 이미지 파일"
                                        )
                                    except ImportError:
                                        # vl-convert가 없으면 SVG로 대체
                                        svg_data = chart.to_json()
                                        st.download_button(
                                            label=f"🖼️ {lang['download_chart']} (SVG)",
                                            data=svg_data,
                                            file_name=f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg",
                                            mime="image/svg+xml",
                                            use_container_width=True,
                                            help="SVG 벡터 이미지"
                                        )
                                
                                with col_chart2:
                                    # SVG 형식으로 차트 이미지 다운로드
                                    try:
                                        import vl_convert as vlc
                                        svg_data = vlc.vegalite_to_svg(chart.to_dict())
                                        st.download_button(
                                            label=f"🎨 {lang['download_chart']} (SVG)",
                                            data=svg_data,
                                            file_name=f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.svg",
                                            mime="image/svg+xml",
                                            use_container_width=True,
                                            help="SVG 벡터 이미지 (확대해도 선명)"
                                        )
                                    except ImportError:
                                        # JSON 폴백
                                        chart_json = chart_data.to_json(orient='records', force_ascii=False)
                                        st.download_button(
                                            label=f"📊 {lang['download_chart']} (JSON)",
                                            data=chart_json,
                                            file_name=f"chart_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                            mime="application/json",
                                            use_container_width=True,
                                            help="구조화된 데이터 형식"
                                        )
                                
                                with col_chart3:
                                    # CSV 형식으로 차트 데이터 다운로드
                                    chart_csv = chart_data.to_csv(index=False).encode('utf-8-sig')
                                    st.download_button(
                                        label=f"📥 {lang['download_chart']} (CSV)",
                                        data=chart_csv,
                                        file_name=f"chart_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                        mime="text/csv",
                                        use_container_width=True,
                                        help="엑셀에서 열 수 있는 형식"
                                    )
                            else:
                                st.info(lang["unsupported_chart"])
                        else:
                            st.info(lang["no_chart_data"])
                
                # 상세 정보
                with st.expander(lang["details_header"]):
                    st.markdown(f"**{lang['sql_header']}**")
                    st.code(data["sql_query"], language="sql")
                    
                    st.markdown(f"**{lang['tables_header']}**")
                    st.write(", ".join(data["table_names"]))
                    
                    st.markdown(f"**{lang['result_header']}**")
                    if data["result"]:
                        try:
                            df = pd.DataFrame(data["result"])
                            st.dataframe(df, use_container_width=True)
                            
                            # 엑셀 다운로드 버튼
                            csv = df.to_csv(index=False).encode('utf-8-sig')
                            st.download_button(
                                label=lang["download_excel"],
                                data=csv,
                                file_name=f"query_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                        except Exception as e:
                            st.write(lang["error_general"], e)
                            st.write(data["result"])
                    else:
                        st.info(lang["no_result"])
                
            except requests.exceptions.RequestException as e:
                st.error(f"{lang['error_api']}: {e}")
            except Exception as e:
                st.error(f"{lang['error_general']}: {e}")
    else:
        st.warning(lang["warning_empty"])

# 대화 기록 표시
if st.session_state.conversation_history:
    st.markdown("---")
    st.subheader(lang["history_header"])
    
    for i, conv in enumerate(reversed(st.session_state.conversation_history)):
        with st.expander(f"🕐 {conv['timestamp']} - {conv['question'][:50]}..."):
            st.markdown(f"**Q:** {conv['question']}")
            st.markdown(f"**A:** {conv['answer']}")
            if conv.get('chart_data') and conv.get('chart_type') != 'none':
                st.caption(f"📊 Chart: {conv['chart_type']}")
