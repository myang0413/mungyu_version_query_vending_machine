from fastapi import FastAPI, HTTPException
from .schemas import QueryRequest, QueryResponse, VectorSearchRequest, VectorSearchResponse, HybridSearchRequest
from .chains import (
    get_full_chain, get_db, clean_json_response,
    vector_search_unified, vector_search_films, vector_search_actors, 
    vector_search_customers, hybrid_search
)
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
    벡터 검색을 통해 관련 컨텍스트를 추가하여 더 정확한 SQL 생성을 지원합니다.
    """
    question = request.question
    language = request.language
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # 벡터 검색으로 컨텍스트 가져오기
        vector_context = ""
        try:
            hybrid_result = hybrid_search(question, top_k=3)
            vector_context = hybrid_result["context"]
            print(f"Vector context added: {vector_context[:200]}...")
        except Exception as e:
            print(f"Vector search failed (continuing without context): {e}")
            vector_context = ""
        
        # 컨텍스트를 포함한 질문 구성
        enhanced_question = question
        if vector_context:
            enhanced_question = f"{question}\n\n{vector_context}"
        
        # 전체 체인 실행 (언어 파라미터 포함)
        chain_result = full_chain.invoke({"question": enhanced_question, "language": language})
        
        # 디버깅을 위한 출력
        print("Chain result:", chain_result)

        # 체인 결과 파싱
        intent_str = chain_result.get("intent", '{}')
        print(f"Intent string: {intent_str}")
        
        # JSON 정리
        intent_str = clean_json_response(intent_str)
        
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
        
        # JSON 정리
        final_response_str = clean_json_response(final_response_str)
        
        try:
            final_response_data = json.loads(final_response_str) if final_response_str.strip() else {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse final_response JSON: {e}")
            print(f"Raw final_response_str after cleaning: {final_response_str}")
            final_response_data = {}
        
        natural_language_response = final_response_data.get("natural_language_response", "")
        chart_data = final_response_data.get("chart_data", [])
        
        # 디버깅: 파싱된 데이터 출력
        print(f"Parsed natural_language_response: {natural_language_response}")
        print(f"Parsed chart_data: {chart_data}")
        print(f"Chart type: {chart_type}")

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
    return {"message": "Welcome to the Text-to-SQL API with Vector Search!"}

@app.post("/vector-search", response_model=VectorSearchResponse)
async def vector_search_endpoint(request: VectorSearchRequest):
    """
    벡터 검색 API 엔드포인트
    모든 테이블에서 의미 기반 검색을 수행합니다.
    """
    try:
        results = vector_search_unified(
            query=request.query,
            top_k=request.top_k,
            source_filter=request.source_filter
        )
        
        return VectorSearchResponse(
            results=results,
            count=len(results)
        )
    except Exception as e:
        print(f"Vector search error: {e}")
        raise HTTPException(status_code=500, detail=f"Vector search failed: {str(e)}")

@app.post("/vector-search/films", response_model=VectorSearchResponse)
async def vector_search_films_endpoint(request: VectorSearchRequest):
    """
    영화 벡터 검색 API
    영화 데이터에서만 의미 기반 검색을 수행합니다.
    """
    try:
        results = vector_search_films(
            query=request.query,
            top_k=request.top_k
        )
        
        return VectorSearchResponse(
            results=results,
            count=len(results)
        )
    except Exception as e:
        print(f"Film vector search error: {e}")
        raise HTTPException(status_code=500, detail=f"Film vector search failed: {str(e)}")

@app.post("/vector-search/actors", response_model=VectorSearchResponse)
async def vector_search_actors_endpoint(request: VectorSearchRequest):
    """
    배우 벡터 검색 API
    배우 데이터에서만 의미 기반 검색을 수행합니다.
    """
    try:
        results = vector_search_actors(
            query=request.query,
            top_k=request.top_k
        )
        
        return VectorSearchResponse(
            results=results,
            count=len(results)
        )
    except Exception as e:
        print(f"Actor vector search error: {e}")
        raise HTTPException(status_code=500, detail=f"Actor vector search failed: {str(e)}")

@app.post("/vector-search/customers", response_model=VectorSearchResponse)
async def vector_search_customers_endpoint(request: VectorSearchRequest):
    """
    고객 벡터 검색 API
    고객 데이터에서만 의미 기반 검색을 수행합니다.
    """
    try:
        results = vector_search_customers(
            query=request.query,
            top_k=request.top_k
        )
        
        return VectorSearchResponse(
            results=results,
            count=len(results)
        )
    except Exception as e:
        print(f"Customer vector search error: {e}")
        raise HTTPException(status_code=500, detail=f"Customer vector search failed: {str(e)}")

@app.post("/hybrid-query", response_model=QueryResponse)
async def hybrid_query_endpoint(request: HybridSearchRequest):
    """
    하이브리드 검색 API
    벡터 검색 결과를 컨텍스트로 활용하여 SQL 쿼리를 생성합니다.
    """
    question = request.question
    language = request.language
    
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # 벡터 검색으로 컨텍스트 가져오기
        vector_context = ""
        if request.use_vector_context:
            hybrid_result = hybrid_search(question, top_k=request.top_k)
            vector_context = hybrid_result["context"]
            print(f"Vector context added: {vector_context[:200]}...")
        
        # 컨텍스트를 포함한 질문 구성
        enhanced_question = question
        if vector_context:
            enhanced_question = f"{question}\n\n{vector_context}"
        
        # 체인 실행
        chain_result = full_chain.invoke({"question": enhanced_question, "language": language})
        
        # 기존 코드와 동일한 처리
        intent_str = chain_result.get("intent", '{}')
        intent_str = clean_json_response(intent_str)
        
        try:
            intent_data = json.loads(intent_str) if intent_str.strip() else {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse intent JSON: {e}")
            intent_data = {}
        
        chart_type = intent_data.get("chart_type", "none")
        sql_query = chain_result.get("sql_query", "")
        sql_result_str = chain_result.get("sql_result", "[]")
        
        final_response_str = chain_result.get("final_response", '{}')
        final_response_str = clean_json_response(final_response_str)
        
        try:
            final_response_data = json.loads(final_response_str) if final_response_str.strip() else {}
        except json.JSONDecodeError as e:
            print(f"Failed to parse final_response JSON: {e}")
            final_response_data = {}
        
        natural_language_response = final_response_data.get("natural_language_response", "")
        chart_data = final_response_data.get("chart_data", [])

        try:
            result_list = json.loads(sql_result_str)
        except (json.JSONDecodeError, TypeError):
            result_list = [{"result": sql_result_str}]

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
        print(f"Hybrid query error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process hybrid query: {str(e)}")
