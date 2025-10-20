import os
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains import create_sql_query_chain
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import json

load_dotenv()

# OpenAI Embeddings 초기화
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

def get_db():
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    return SQLDatabase.from_uri(
        f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

def clean_sql_query(query: str) -> str:
    """
    LLM이 생성한 SQL 쿼리에서 불필요한 텍스트를 제거합니다.
    """
    query = query.strip()
    
    # Remove markdown code blocks
    if "```sql" in query:
        query = query.split("```sql")[1].split("```")[0].strip()
    elif "```" in query:
        query = query.split("```")[1].split("```")[0].strip()
    
    # Remove "Question:" line if present (여러 줄 형식 처리)
    lines = query.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        # "Question:"으로 시작하는 줄 제거
        if line.startswith("Question:"):
            continue
        # "SQLQuery:" 프리픽스 제거
        if line.startswith("SQLQuery:"):
            line = line[len("SQLQuery:"):].strip()
        if line:
            cleaned_lines.append(line)
    
    query = ' '.join(cleaned_lines)
    return query

def clean_json_response(response: str) -> str:
    """
    LLM이 생성한 JSON 응답에서 마크다운 코드 블록을 제거합니다.
    """
    response = response.strip()
    
    # Remove markdown code blocks
    if "```json" in response:
        response = response.split("```json")[1].split("```")[0].strip()
    elif "```" in response:
        response = response.split("```")[1].split("```")[0].strip()
    
    return response

def get_full_chain():
    db = get_db()
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)

    # 1. 의도 파악 체인 (다국어 지원)
    intent_prompts = {
        "한국어": PromptTemplate.from_template(
            """사용자의 질문을 분석하여 다음 두 가지를 판단해 JSON 형식으로 반환하세요:
            1. `visualization_needed`: 사용자가 명시적으로 데이터 시각화를 요청했는지 여부 (True/False)
               - True인 경우: "시각화", "그래프", "차트", "그림", "플롯", "보여줘" 등의 시각화 관련 키워드가 포함된 경우
               - False인 경우: 단순히 데이터를 조회하거나 "알려줘", "보여줘", "몇 개", "수를 세어줘" 등 시각화 없이 답변만 원하는 경우
            2. `chart_type`: 시각화가 필요하다면, 어떤 종류의 차트가 가장 적합할지 추천 ('bar', 'line', 'pie', 'scatter', 'table' 등). 필요 없다면 'none'.
            
            질문: "{question}"
            
            중요: "보여줘"만으로는 시각화가 필요하다고 판단하지 마세요. "시각화해줘", "그래프로 보여줘", "차트로 만들어줘" 등 명시적인 시각화 요청이 있을 때만 True로 설정하세요.
            JSON 출력:"""
        ),
        "English": PromptTemplate.from_template(
            """Analyze the user's question and return a JSON object with two keys:
            1. `visualization_needed`: Whether the user explicitly requested data visualization (True/False)
               - True: When the question contains visualization keywords like "visualize", "graph", "chart", "plot", "show me a graph", etc.
               - False: When the user only wants data or information without visualization (e.g., "show me", "tell me", "how many", "count")
            2. `chart_type`: If visualization is needed, recommend the most suitable chart type ('bar', 'line', 'pie', 'scatter', 'table', etc.). If not, use 'none'.
            
            Question: "{question}"
            
            Important: "show me" alone does NOT mean visualization is needed. Only set True when there's an explicit visualization request like "visualize", "show me a graph", "create a chart", etc.
            JSON output:"""
        )
    }

    # 2. SQL 쿼리 생성 체인
    generate_query_chain = create_sql_query_chain(llm, db)

    # 3. 자연어 답변 및 차트 데이터 생성 체인 (다국어 지원)
    answer_prompts = {
        "한국어": PromptTemplate.from_template(
            """사용자의 질문, 생성된 SQL 쿼리, 그리고 SQL 결과를 바탕으로 포괄적인 답변을 두 부분으로 나누어 제공하세요:
            1. 질문에 직접적으로 답변하는 자연어 응답. (답변 언어: 한국어)
            2. 사용자가 시각화를 요청한 경우, 차트에 필요한 데이터를 유효한 JSON 형식으로 제공. JSON은 각 데이터 포인트를 나타내는 객체들의 리스트여야 합니다.

            질문: {question}
            SQL 쿼리: {sql_query}
            SQL 결과: {sql_result}
            사용자 의도: {intent}

            중요: 시간 기반 데이터(월별, 연도별 등)의 경우, chart_data의 키 이름을 명확하게 지정하세요.
            예: {{{{"Month": "2024-01", "Count": 150}}}} 또는 {{{{"Year": 2024, "Month": 1, "Count": 150}}}}
            
            'natural_language_response'와 'chart_data' 두 개의 키를 가진 단일 JSON 객체로 응답을 제공하세요.
            - 'natural_language_response': [여기에 자연어 답변]
            - 'chart_data': [여기에 차트용 JSON 데이터, 차트가 필요 없으면 빈 리스트 []]"""
        ),
        "English": PromptTemplate.from_template(
            """Given the user's question, the generated SQL query, and the SQL result, provide a comprehensive answer in two parts:
            1. A natural language response that directly answers the question. (Answer Language: English)
            2. If the user asked for a visualization, provide the necessary data for the chart in a valid JSON format. The JSON should be a list of objects, where each object represents a data point.

            Question: {question}
            SQL Query: {sql_query}
            SQL Result: {sql_result}
            User Intent: {intent}

            CRITICAL RULES:
            - ALWAYS use actual names (category names, customer names, actor names, etc.) instead of IDs in both the natural language response and chart_data
            - If the SQL result contains both ID and name columns (e.g., category_id and name), ALWAYS use the name column
            - Make your response human-readable and meaningful
            
            Important guidelines for chart_data:
            - Use descriptive, human-readable key names (e.g., "Category", "Count", "Revenue", "Customer_Name")
            - For categorical data (categories, names, etc.), use string values (NOT IDs)
            - For numerical data (counts, amounts, etc.), use numeric values
            - For time-based data, use clear key names: {{"Month": "2024-01", "Count": 150}} or {{"Year": 2024, "Month": 1, "Count": 150}}
            - Example for categories: [{{"Category": "Action", "Movie_Count": 74}}, {{"Category": "Drama", "Movie_Count": 73}}]
            - NEVER use: [{{"Category_ID": 15, "Movie_Count": 74}}] - this is WRONG!
            
            Provide your response as a single JSON object with two keys: 'natural_language_response' and 'chart_data'.
            - 'natural_language_response': [Your natural language answer here]
            - 'chart_data': [Your JSON data for the chart here, or an empty list [] if no chart is needed]"""
        )
    }

    # 동적 프롬프트 선택을 위한 체인 구성
    def select_intent_prompt(x):
        language = x.get("language", "한국어")
        prompt = intent_prompts.get(language, intent_prompts["한국어"])
        return prompt.invoke({"question": x["question"]})
    
    def select_answer_prompt(x):
        language = x.get("language", "한국어")
        prompt = answer_prompts.get(language, answer_prompts["한국어"])
        return prompt.invoke({
            "question": x["question"],
            "sql_query": x["sql_query"],
            "sql_result": x["sql_result"],
            "intent": x["intent"]
        })
    
    intent_chain = select_intent_prompt | llm | StrOutputParser()
    answer_chain = select_answer_prompt | llm | StrOutputParser()

    # 4. 전체 체인 구성
    def run_db_query(x):
        sql_query = clean_sql_query(x["sql_query"])
        try:
            return db.run(sql_query)
        except Exception as e:
            return f"Error executing query: {str(e)}"

    chain = (
        RunnablePassthrough.assign(intent=intent_chain)
        .assign(sql_query=generate_query_chain)
        .assign(sql_result=run_db_query)
        .assign(final_response=answer_chain)
    )
    
    return chain

def execute_query(sql_query: str):
    db = get_db()
    try:
        result = db.run(sql_query)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}"

# ============================================
# 벡터 검색 기능
# ============================================

def get_vector_db_connection():
    """pgvector 데이터베이스 연결 생성"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def vector_search_unified(query: str, top_k: int = 5, source_filter: str = None):
    """
    통합 벡터 검색 (모든 테이블에서 검색)
    
    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수
        source_filter: 특정 테이블만 검색 ('film', 'actor', 'customer', 'category')
    
    Returns:
        검색 결과 리스트
    """
    # 쿼리 임베딩 생성
    query_embedding = embeddings_model.embed_query(query)
    
    conn = get_vector_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # SQL 쿼리 구성
    if source_filter:
        sql = """
            SELECT 
                source_table,
                source_id,
                content,
                metadata,
                1 - (embedding <=> %s::vector) as similarity
            FROM unified_embeddings
            WHERE source_table = %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        cur.execute(sql, (query_embedding, source_filter, query_embedding, top_k))
    else:
        sql = """
            SELECT 
                source_table,
                source_id,
                content,
                metadata,
                1 - (embedding <=> %s::vector) as similarity
            FROM unified_embeddings
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        cur.execute(sql, (query_embedding, query_embedding, top_k))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(row) for row in results]

def vector_search_films(query: str, top_k: int = 5):
    """
    영화 벡터 검색
    
    Args:
        query: 검색 쿼리 (예: "액션 영화", "로맨틱 코미디")
        top_k: 반환할 결과 수
    
    Returns:
        검색 결과 리스트
    """
    query_embedding = embeddings_model.embed_query(query)
    
    conn = get_vector_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql = """
        SELECT 
            fe.film_id,
            fe.content,
            f.title,
            f.description,
            f.release_year,
            f.rating,
            1 - (fe.embedding <=> %s::vector) as similarity
        FROM film_embeddings fe
        JOIN film f ON fe.film_id = f.film_id
        ORDER BY fe.embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (query_embedding, query_embedding, top_k))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(row) for row in results]

def vector_search_actors(query: str, top_k: int = 5):
    """
    배우 벡터 검색
    
    Args:
        query: 검색 쿼리 (예: "액션 영화에 출연한 배우")
        top_k: 반환할 결과 수
    
    Returns:
        검색 결과 리스트
    """
    query_embedding = embeddings_model.embed_query(query)
    
    conn = get_vector_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql = """
        SELECT 
            ae.actor_id,
            ae.content,
            a.first_name,
            a.last_name,
            1 - (ae.embedding <=> %s::vector) as similarity
        FROM actor_embeddings ae
        JOIN actor a ON ae.actor_id = a.actor_id
        ORDER BY ae.embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (query_embedding, query_embedding, top_k))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(row) for row in results]

def vector_search_customers(query: str, top_k: int = 5):
    """
    고객 벡터 검색
    
    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수
    
    Returns:
        검색 결과 리스트
    """
    query_embedding = embeddings_model.embed_query(query)
    
    conn = get_vector_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    sql = """
        SELECT 
            ce.customer_id,
            ce.content,
            c.first_name,
            c.last_name,
            c.email,
            1 - (ce.embedding <=> %s::vector) as similarity
        FROM customer_embeddings ce
        JOIN customer c ON ce.customer_id = c.customer_id
        ORDER BY ce.embedding <=> %s::vector
        LIMIT %s
    """
    cur.execute(sql, (query_embedding, query_embedding, top_k))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    return [dict(row) for row in results]

def hybrid_search(query: str, top_k: int = 5):
    """
    하이브리드 검색: 벡터 검색 결과를 기반으로 SQL 쿼리 생성을 위한 컨텍스트 제공
    
    Args:
        query: 사용자 질문
        top_k: 벡터 검색 결과 수
    
    Returns:
        벡터 검색 결과와 관련 컨텍스트
    """
    # 통합 벡터 검색 수행
    vector_results = vector_search_unified(query, top_k=top_k)
    
    # 결과를 컨텍스트 문자열로 변환
    context = "\n\n=== Relevant Data from Vector Search ===\n"
    for i, result in enumerate(vector_results, 1):
        context += f"\n{i}. [{result['source_table'].upper()}] (Similarity: {result['similarity']:.3f})\n"
        context += f"   {result['content'][:200]}...\n"
    
    return {
        "vector_results": vector_results,
        "context": context
    }
