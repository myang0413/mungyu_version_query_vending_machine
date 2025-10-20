import os
import psycopg2
from langchain_community.utilities import SQLDatabase
from langchain_openai import ChatOpenAI
from langchain.chains import create_sql_query_chain
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import json

load_dotenv()

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
    # Remove common prefixes
    query = query.strip()
    
    # Remove "SQLQuery:" prefix if present
    if query.startswith("SQLQuery:"):
        query = query[len("SQLQuery:"):].strip()
    
    # Remove markdown code blocks
    if "```sql" in query:
        query = query.split("```sql")[1].split("```")[0].strip()
    elif "```" in query:
        query = query.split("```")[1].split("```")[0].strip()
    
    return query

def get_full_chain():
    db = get_db()
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0)

    # 1. 의도 파악 체인
    intent_prompt = PromptTemplate.from_template(
        """사용자의 질문을 분석하여 다음 두 가지를 판단해 JSON 형식으로 반환하세요:
        1. `visualization_needed`: 사용자가 데이터 시각화(그래프, 차트 등)를 원하는지 여부 (True/False)
        2. `chart_type`: 시각화가 필요하다면, 어떤 종류의 차트가 가장 적합할지 추천 ('bar', 'line', 'pie', 'scatter', 'table' 등). 필요 없다면 'none'.

        질문: "{question}"

        JSON 출력:"""
    )
    intent_chain = intent_prompt | llm | StrOutputParser()

    # 2. SQL 쿼리 생성 체인
    generate_query_chain = create_sql_query_chain(llm, db)

    # 3. 자연어 답변 및 차트 데이터 생성 체인
    answer_prompt = PromptTemplate.from_template(
        """Given the user's question, the generated SQL query, and the SQL result, provide a comprehensive answer in two parts:
        1. A natural language response that directly answers the question.
        2. If the user asked for a visualization, provide the necessary data for the chart in a valid JSON format. The JSON should be a list of objects, where each object represents a data point.

        Question: {question}
        SQL Query: {sql_query}
        SQL Result: {sql_result}
        User Intent: {intent}

        Provide your response as a single JSON object with two keys: 'natural_language_response' and 'chart_data'.
        - 'natural_language_response': [Your natural language answer here]
        - 'chart_data': [Your JSON data for the chart here, or an empty list [] if no chart is needed]
        """
    )
    answer_chain = answer_prompt | llm | StrOutputParser()

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
