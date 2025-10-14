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

def get_full_chain():
    db = get_db()
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    # SQL 쿼리 생성 체인
    generate_query_chain = create_sql_query_chain(llm, db)

    # 자연어 답변 생성 프롬프트
    answer_prompt = PromptTemplate.from_template(
        """Given the original question, the generated SQL query, and the SQL result, write a natural language answer.

Original Question: {question}
Generated SQL Query: {sql_query}
SQL Result: {sql_result}
Natural Language Answer:"""
    )

    # 자연어 답변 생성 체인
    answer_chain = answer_prompt | llm | StrOutputParser()

    # 전체 체인 구성
    chain = (
        RunnablePassthrough.assign(sql_query=generate_query_chain).assign(
            sql_result=lambda x: db.run(x["sql_query"]),
        )
        | RunnablePassthrough.assign(natural_language_response=answer_chain)
    )

    return chain

def execute_query(sql_query: str):
    db = get_db()
    try:
        result = db.run(sql_query)
        return result
    except Exception as e:
        return f"Error executing query: {str(e)}"
