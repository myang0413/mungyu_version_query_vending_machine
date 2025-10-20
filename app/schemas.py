from pydantic import BaseModel
from typing import List, Any, Dict, Optional

class QueryRequest(BaseModel):
    question: str

class QueryResponse(BaseModel):
    sql_query: str
    table_names: List[str]
    result: List[Dict[str, Any]]
    natural_language_response: str
    chart_type: Optional[str] = None
    chart_data: Optional[List[Dict[str, Any]]] = None
