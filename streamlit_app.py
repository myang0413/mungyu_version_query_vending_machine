import streamlit as st
import requests
import pandas as pd
import altair as alt
import json
from datetime import datetime

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
        "example_questions": "💡 예시 질문",
        "examples": [
            "카테고리별 영화 수를 막대 그래프로 보여줘",
            "가장 많이 대여한 고객 10명을 보여줘",
            "월별 대여 건수 추이를 선 그래프로",
            "배우별 출연 영화 수를 보여줘"
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
        "example_questions": "💡 Example Questions",
        "examples": [
            "Show me the number of movies by category as a bar chart",
            "Top 10 customers by rental count",
            "Show rental trends by month as a line chart",
            "Show the number of movies per actor"
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
    st.header(LANGUAGES[st.session_state.language]["language"])
    selected_language = st.selectbox(
        "",
        options=["한국어", "English"],
        index=0 if st.session_state.language == "한국어" else 1,
        key="lang_select"
    )
    st.session_state.language = selected_language
    
    lang = LANGUAGES[st.session_state.language]
    
    st.markdown("---")
    st.subheader(lang["example_questions"])
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
                # FastAPI 백엔드에 요청 (언어 정보 포함)
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
                            x_col = chart_data.columns[0]
                            y_col = chart_data.columns[1]
                            x_type = 'quantitative' if pd.api.types.is_numeric_dtype(chart_data[x_col]) else 'nominal'
                            y_type = 'quantitative' if pd.api.types.is_numeric_dtype(chart_data[y_col]) else 'nominal'
                            
                            if chart_type == 'bar':
                                chart = alt.Chart(chart_data).mark_bar().encode(
                                    x=alt.X(x_col, type=x_type, title=x_col.capitalize()),
                                    y=alt.Y(y_col, type=y_type, title=y_col.capitalize()),
                                    tooltip=list(chart_data.columns)
                                ).properties(height=300).interactive()
                                st.altair_chart(chart, use_container_width=True)
                            elif chart_type == 'line':
                                chart = alt.Chart(chart_data).mark_line(point=True).encode(
                                    x=alt.X(x_col, type=x_type, title=x_col.capitalize()),
                                    y=alt.Y(y_col, type=y_type, title=y_col.capitalize()),
                                    tooltip=list(chart_data.columns)
                                ).properties(height=300).interactive()
                                st.altair_chart(chart, use_container_width=True)
                            elif chart_type == 'pie':
                                chart = alt.Chart(chart_data).mark_arc().encode(
                                    theta=alt.Theta(field=y_col, type='quantitative'),
                                    color=alt.Color(field=x_col, type='nominal'),
                                    tooltip=list(chart_data.columns)
                                ).properties(height=300)
                                st.altair_chart(chart, use_container_width=True)
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
