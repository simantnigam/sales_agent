from agents.get_assigned_beats_agent import GetAssignedBeatsAgent
from agents.get_beat_route_plan_agent import GetBeatRoutePlanAgent
from agents.select_retailer_agent import SelectRetailer
from agents.get_retailer_info_agent import GetRetailerInfoAgent
from agents.get_pitch_summary_agent import PitchSummarizationAgent
from utils.set_state import SalesRepState
from typing import  List, Dict, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph,START,END


# Building the Agentic graph
def build_agent_graph():
    builder = StateGraph(SalesRepState)

    # nodes 
    builder.add_node("get_beat",GetAssignedBeatsAgent)
    builder.add_node("get_route", GetBeatRoutePlanAgent)
    builder.add_node("SelectRetailer",SelectRetailer)
    builder.add_node("get_retailer_info", GetRetailerInfoAgent)
    builder.add_node("get_sales_pitch", PitchSummarizationAgent)


    # edges
    builder.add_edge(START, "get_beat")
    builder.add_edge("get_beat","get_route")
    builder.add_edge("get_route","SelectRetailer")
    builder.add_edge("SelectRetailer", "get_retailer_info")
    builder.add_edge("get_retailer_info","get_sales_pitch")
    builder.add_edge("get_sales_pitch",END)


    # agent_graph = builder.compile(checkpointer=checkpointer)


    return builder