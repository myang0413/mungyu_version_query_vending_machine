from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from openai import OpenAI
import streamlit as st
import pandas as pd
import os

# .env 파일의 절대 경로를 지정하여 환경 변수 불러오기
from pathlib import Path

# __file__은 현재 실행 중인 스크립트의 경로를 나타냅니다.
# .parent를 사용하여 해당 파일이 속한 디렉터리를 얻습니다.
# 이를 통해 항상 main.py와 동일한 위치에 있는 .env 파일을 찾습니다.
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# db
# .env 파일 로딩에 실패할 경우를 대비하여 docker-compose.yml과 일치하는 기본값을 사용합니다.
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5433")
DB_NAME = os.getenv("DB_NAME", "dvdrental")
DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DB_URL, echo=True, future=True)

# external api
API_KEY = os.getenv("OPENAI_API_KEY") # 개인 api 키
client = OpenAI(api_key=API_KEY)

# argument - 환경변수로 초기화 여부 확인
INIT_TABLE_DOCS = os.getenv("INIT_TABLE_DOCS", "0") == "1"

def run_query(query: str, params: dict = None):
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]

def run_command(query: str, params: dict = None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})

def get_embedding(text:str, model:str="text-embedding-3-small") -> list[float]:
    # dims: 1536
    response = client.embeddings.create(
        input=text,
        model=model
    )
    embedding = response.data[0].embedding
    return embedding

def extract_ddl(table_name):
    ddl_query = f"""SELECT 
        column_name, 
        data_type,
        is_nullable,
        column_default
    FROM 
        information_schema.columns
    WHERE 
        table_schema = 'public' AND table_name = '{table_name}';"""
    
    result = run_query(ddl_query)

    column_dict = {
        # ✅ 수정: 리스트 ["column_name"] 대신 v["column_name"] (문자열 값) 사용
        v["column_name"]:{ 
            "data_type": v["data_type"],
            "is_nullable": v["is_nullable"],
            "column_default": v["column_default"]
        } for v in result
    }

    return column_dict

def make_table_desc_dict():
    # dvdrental 속 테이블들에 대한 간단한 설명을 작성한 메타 정보.
    table_desc_dict = { 
        "actor": "contains actors data including first name and last name.",
        "film": "contains films data such as title, release year, length, rating, etc.",
        "film_actor": "contains the relationships between films and actors.",
        "category": "contains film’s categories data.",
        "film_category": "containing the relationships between films and categories.",
        "store": "contains the store data including manager staff and address.",
        "inventory": "stores inventory data.",
        "rental": "stores rental data.",
        "payment": "stores customer’s payments.",
        "staff": "stores staff data.",
        "customer": "stores customer’s data.",
        "address": "stores address data for staff and customers.",
        "city": "stores the city names.",
        "country": "stores the country names."
    }
    return table_desc_dict
    
def insert_doc(name: str):
    """테이블명, DDL, 짧은 설명을 합쳐서 하나의 문서로 저장"""
    # 설명 + DDL 합치기
    table_desc_dict = make_table_desc_dict()
    ddl = extract_ddl(name)
    summary = table_desc_dict[name]
    
    doc_text = f"""
    <Description>
    
    {summary}
    
    </Description>



    <DDL>
    
    {ddl}
    
    </DDL>
    
    """
    embedding = get_embedding(doc_text)

    run_command(
        """
        INSERT INTO table_docs (name, description, embedding)
        VALUES (:name, :description, :embedding)
        """,
        {"name": name, "description": doc_text, "embedding": embedding}
    )
    

def create_table_docs_if_not_exists():
    """'table_docs' 테이블이 존재하지 않으면 생성합니다."""
    # pg_vector 확장이 활성화되어 있는지 확인하고, 없으면 생성
    run_command("CREATE EXTENSION IF NOT EXISTS vector;")
    # table_docs 테이블이 없으면 생성
    run_command("""
        CREATE TABLE IF NOT EXISTS table_docs (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            embedding VECTOR(1536)
        );
    """)

def initialize_table_docs():
    """'table_docs' 테이블이 비어 있으면 모든 테이블의 문서와 임베딩을 채웁니다."""
    create_table_docs_if_not_exists()
    
    # 테이블이 비어 있는지 확인
    count_result = run_query("SELECT COUNT(*) as count FROM table_docs")
    if count_result[0]['count'] == 0:
        st.info("Table documents not found. Initializing... Please wait.")
        print("Initializing table documents and embeddings...")
        
        progress_bar = st.progress(0)
        tables = list(make_table_desc_dict().keys())
        total_tables = len(tables)

        for i, table_name in enumerate(tables):
            try:
                insert_doc(table_name)
                progress_bar.progress((i + 1) / total_tables, text=f"Processing {table_name}...")
            except Exception as e:
                st.error(f"Error processing table {table_name}: {e}")
                print(f"Error processing table {table_name}: {e}")
        
        st.success("Initialization complete!")
        st.balloons()
        print("Initialization complete.")
    else:
        print("Table documents are already initialized.")

# 애플리케이션 시작 시 테이블 문서 초기화 실행
initialize_table_docs()


def search_docs(query: str, limit: int = 1):
    # 질의 → 유사 문서 검색
    query_emb = get_embedding(query)
    sql = """
        SELECT id, name, description,
               embedding <=> (:query_emb)::vector AS distance
        FROM table_docs
        ORDER BY embedding <=> (:query_emb)::vector
        LIMIT :limit;
    """
    return run_query(sql, {"query_emb": query_emb, "limit": limit})

def clean_sql_output(raw: str) -> str:
    import re
    return re.sub(r"^```sql\n|\n```$", "", raw.strip())

def generate_sql(natural_query: str, limit: int = 2):
    # 1. 유사 테이블 검색
    results = search_docs(natural_query, limit=limit)
    name = results[0]["name"] if results else ""
    context = results[0]["description"] if results else ""

    # 2. LLM 프롬프트 구성
    system_prompt = """You are an expert SQL generator.
    
    You will be given:
    1. A natural language query from the user.
    2. A context object where each key is a table name and its value is text that includes:
       - A <Description> ... </Description> block: short natural language description of the table.
       - A <DDL> ... </DDL> block: the schema of that table, with column names, data types, and constraints.
    
    Your task:
    - Generate a valid SQL query that answers the natural language query.
    - Use only the provided tables and columns.
    - Do not invent tables or columns that are not in the context.
    - Return only the SQL query, nothing else.
    """

    
    user_prompt = f"""

    <name>
    the name of the table is `{name}` .
    </name>

    <Question>
    {natural_query}
    </Question>


    <Context>
    {context}
    </Context>
    
    """

    # 3. OpenAI 호출
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.5,
        max_completion_tokens=300,
    )
    print("-------")
    print(user_prompt)
    print("-------")
    
    sql_query = resp.choices[0].message.content
    return clean_sql_output(sql_query)

if __name__ == "__main__":
    st.title("📝 Text2SQL Demo")

    natural_query = st.text_input("Enter your question:", "List the title and release year of movies.")

    if st.button("Run"):
        with st.spinner('Generating SQL...'):
            query = generate_sql(natural_query)
        
        st.subheader("Generated SQL Query")
        st.code(query, language="sql")

        try:
            rows = run_query(query)
            df = pd.DataFrame(rows)
            st.dataframe(df)
        except Exception as e:
            st.error(f"Error running query: {e}")