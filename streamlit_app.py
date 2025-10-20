import streamlit as st
import requests
import pandas as pd
import altair as alt

st.title("Text-to-SQL 쿼리 자판기")

# 사용자 입력
question = st.text_input("데이터베이스에 질문을 입력하세요:")

if st.button("쿼리 실행"):
    if question:
        try:
            # FastAPI 백엔드에 요청
            response = requests.post("http://127.0.0.1:8000/query", json={"question": question})
            response.raise_for_status()  # 오류 발생 시 예외 발생

            data = response.json()

            # 결과 표시
            st.subheader("자연어 답변")
            st.write(data["natural_language_response"])

            # 차트 표시 (차트 정보가 있는 경우)
            if data.get("chart_type") and data.get("chart_data"):
                st.subheader("데이터 시각화")
                chart_type = data["chart_type"]
                chart_data = pd.DataFrame(data["chart_data"])

                if not chart_data.empty:
                    # 데이터 타입 추론
                    x_col = chart_data.columns[0]
                    y_col = chart_data.columns[1]
                    x_type = 'quantitative' if pd.api.types.is_numeric_dtype(chart_data[x_col]) else 'nominal'
                    y_type = 'quantitative' if pd.api.types.is_numeric_dtype(chart_data[y_col]) else 'nominal'

                    if chart_type == 'bar':
                        chart = alt.Chart(chart_data).mark_bar().encode(
                            x=alt.X(x_col, type=x_type, title=x_col.capitalize()),
                            y=alt.Y(y_col, type=y_type, title=y_col.capitalize()),
                            tooltip=list(chart_data.columns)
                        ).interactive()
                        st.altair_chart(chart, use_container_width=True)
                    elif chart_type == 'line':
                        chart = alt.Chart(chart_data).mark_line().encode(
                            x=alt.X(x_col, type=x_type, title=x_col.capitalize()),
                            y=alt.Y(y_col, type=y_type, title=y_col.capitalize()),
                            tooltip=list(chart_data.columns)
                        ).interactive()
                        st.altair_chart(chart, use_container_width=True)
                    elif chart_type == 'pie':
                        chart = alt.Chart(chart_data).mark_arc().encode(
                            theta=alt.Theta(field=y_col, type='quantitative'),
                            color=alt.Color(field=x_col, type='nominal'),
                            tooltip=list(chart_data.columns)
                        ).interactive()
                        st.altair_chart(chart, use_container_width=True)
                    else:
                        st.write("지원하지 않는 차트 타입입니다.")
                else:
                    st.write("차트를 그릴 데이터가 없습니다.")

            with st.expander("상세 정보 보기"):
                st.subheader("생성된 SQL 쿼리")
                st.code(data["sql_query"], language="sql")

                st.subheader("사용된 테이블")
                st.write(", ".join(data["table_names"]))

                st.subheader("쿼리 결과")
                if data["result"]:
                    try:
                        df = pd.DataFrame(data["result"])
                        st.dataframe(df)
                    except Exception as e:
                        st.write("데이터프레임 변환 중 오류 발생:", e)
                        st.write(data["result"])
                else:
                    st.write("결과가 없습니다.")

        except requests.exceptions.RequestException as e:
            st.error(f"API 요청 중 오류가 발생했습니다: {e}")
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
    else:
        st.warning("질문을 입력해주세요.")
