from pydantic import BaseModel
from typing import List, Any, Dict, Optional

class QueryRequest(BaseModel):
    question: str
    language: Optional[str] = "한국어"

class QueryResponse(BaseModel):
    sql_query: str
    table_names: List[str]
    result: List[Dict[str, Any]]
    natural_language_response: str
    chart_type: Optional[str] = None
    chart_data: Optional[List[Dict[str, Any]]] = None

# 벡터 검색 스키마
class VectorSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    source_filter: Optional[str] = None  # 'film', 'actor', 'customer', 'category'

class VectorSearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    count: int

class HybridSearchRequest(BaseModel):
    question: str
    language: Optional[str] = "한국어"
    use_vector_context: Optional[bool] = True
    top_k: Optional[int] = 3
