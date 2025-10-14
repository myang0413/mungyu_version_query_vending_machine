import streamlit as st
import requests
import pandas as pd

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
            st.subheader("생성된 SQL 쿼리")
            st.code(data["sql_query"], language="sql")

            st.subheader("사용된 테이블")
            st.write(", ".join(data["table_names"]))

            st.subheader("자연어 답변")
            st.write(data["natural_language_response"])

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
