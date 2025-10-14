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
    사용자의 자연어 질문을 받아 SQL을 생성하고, 실행한 뒤, 자연어 답변을 반환합니다.
    """
    question = request.question
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # 전체 체인 실행
        chain_result = full_chain.invoke({"question": question})

        sql_query = chain_result["sql_query"]
        result_str = chain_result["sql_result"]
        natural_language_response = chain_result["natural_language_response"]

        # 결과 파싱
        try:
            result_list = json.loads(result_str)
        except (json.JSONDecodeError, TypeError):
            result_list = [{"result": result_str}]

        # 사용된 테이블 이름 추출
        db = get_db()
        table_names = db.get_usable_table_names()
        used_tables = [name for name in table_names if name in sql_query]

        return QueryResponse(
            sql_query=sql_query,
            table_names=used_tables,
            result=result_list,
            natural_language_response=natural_language_response,
        )
    except Exception as e:
        print(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Text-to-SQL API!"}
