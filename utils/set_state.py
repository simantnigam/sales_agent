from typing import  List, Dict, Any
from typing_extensions import TypedDict
from pydantic import BaseModel


class SalesRepState(TypedDict, total=False):
    sales_rep_id: str
    Weekday: str
    Beat_ID: str
    Beat_Route_Plan: List[dict]
    Retailer_ID: str
    Product_Recommendations: List[dict]
    Last_Visit_Stock: List[dict]
    Retailer_Info: dict
    Pitch: str
    Store_Info: dict
    user_message: str
    order_products : List[dict]
    feedback: str
    order_log : str
    visited_retailers: List[str]
    Day_Summary: str
    next_node: str
    conversation_end: bool