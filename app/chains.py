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
            1. `visualization_needed`: 사용자가 데이터 시각화(그래프, 차트 등)를 원하는지 여부 (True/False)
            2. `chart_type`: 시각화가 필요하다면, 어떤 종류의 차트가 가장 적합할지 추천 ('bar', 'line', 'pie', 'scatter', 'table' 등). 필요 없다면 'none'.
            질문: "{question}"
            JSON 출력:"""
        ),
        "English": PromptTemplate.from_template(
            """Analyze the user's question and return a JSON object with two keys:
            1. `visualization_needed`: Whether the user wants data visualization (graph, chart, etc.) (True/False)
            2. `chart_type`: If visualization is needed, recommend the most suitable chart type ('bar', 'line', 'pie', 'scatter', 'table', etc.). If not, use 'none'.
            Question: "{question}"
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
            예: {"Month": "2024-01", "Count": 150} 또는 {"Year": 2024, "Month": 1, "Count": 150}
            
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

            Important: For time-based data (monthly, yearly, etc.), use clear key names in chart_data.
            Example: {{"Month": "2024-01", "Count": 150}} or {{"Year": 2024, "Month": 1, "Count": 150}}
            
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
