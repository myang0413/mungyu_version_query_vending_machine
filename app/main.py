from fastapi import FastAPI, HTTPException
from .schemas import QueryRequest, QueryResponse
from .chains import get_full_chain, get_db
import json

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Text-to-SQL API",
    description="LangChain과 FastAPI를 사용하여 자연어 질문을 SQL로 변환하는 API",
)

# LangChain 체인 로드
full_chain = get_full_chain()

@app.post("/query", response_model=QueryResponse)
async def handle_query(request: QueryRequest):
    """
    사용자의 자연어 질문을 받아 SQL을 생성하고, 실행한 뒤, 자연어 답변과 차트 데이터를 반환합니다.
    """
    question = request.question
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # 전체 체인 실행
        chain_result = full_chain.invoke({"question": question})
        
        # 디버깅을 위한 출력
        print("Chain result:", chain_result)

        # 체인 결과 파싱
        intent_str = chain_result.get("intent", '{}')
        print(f"Intent string: {intent_str}")
        
        try:
            intent_data = json.loads(intent_str) if intent_str.strip() else {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse intent JSON: {e}")
            intent_data = {}
        
        chart_type = intent_data.get("chart_type", "none")

        sql_query = chain_result.get("sql_query", "")
        sql_result_str = chain_result.get("sql_result", "[]")
        
        final_response_str = chain_result.get("final_response", '{}')
        print(f"Final response string: {final_response_str}")
        
        try:
            final_response_data = json.loads(final_response_str) if final_response_str.strip() else {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse final_response JSON: {e}")
            final_response_data = {}
        
        natural_language_response = final_response_data.get("natural_language_response", "")
        chart_data = final_response_data.get("chart_data", [])

        # SQL 결과 파싱
        try:
            result_list = json.loads(sql_result_str)
        except (json.JSONDecodeError, TypeError):
            result_list = [{"result": sql_result_str}]

        # 사용된 테이블 이름 추출
        db = get_db()
        table_names = db.get_usable_table_names()
        used_tables = [name for name in table_names if name in sql_query]

        return QueryResponse(
            sql_query=sql_query,
            table_names=used_tables,
            result=result_list,
            natural_language_response=natural_language_response,
            chart_type=chart_type,
            chart_data=chart_data,
        )
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Text-to-SQL API!"}
