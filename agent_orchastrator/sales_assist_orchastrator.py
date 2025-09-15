# workflow.py

from agents.get_assigned_beats_agent import GetAssignedBeatsAgent
from agents.get_beat_route_plan_agent import GetBeatRoutePlanAgent
from agents.select_retailer_agent import SelectRetailer
from agents.get_retailer_info_agent import GetRetailerInfoAgent
from agents.get_pitch_summary_agent import PitchSummarizationAgent
from agents.order_logging_agent import OrderLoggingRunnable, OrderLoggingAgent
from agents.day_summary_agent import DaySummaryRunnable, DaySummaryAgent
from utils.set_state import SalesRepState
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END


# Initialize agents
day_summary_agent = DaySummaryAgent()
order_logging_agent = OrderLoggingAgent()

# Wrap them
day_summary_node = DaySummaryRunnable(day_summary_agent)
order_logging_node = OrderLoggingRunnable(order_logging_agent)


def build_agent_graph():
    builder = StateGraph(SalesRepState)

    # ---- Nodes ----
    builder.add_node("get_beat", GetAssignedBeatsAgent)
    builder.add_node("get_route", GetBeatRoutePlanAgent)
    builder.add_node("SelectRetailer", SelectRetailer)
    builder.add_node("get_retailer_info", GetRetailerInfoAgent)
    builder.add_node("get_sales_pitch", PitchSummarizationAgent)
    builder.add_node("log_order", order_logging_node)
    builder.add_node("day_summary", day_summary_node)

    # ---- Edges ----
    builder.add_edge(START, "get_beat")
    builder.add_edge("get_beat", "get_route")

    # From route → either wait, select retailer, or day summary
    def conditional_from_route(state: Dict[str, Any]) -> str:
        msg = (state.get("user_message") or "").lower()
        if "day summary" in msg:
            return "day_summary"
        if "visit" in msg:
            return "SelectRetailer"
        return END  # ✅ stop and wait for next input

    builder.add_conditional_edges("get_route", conditional_from_route, {
        "SelectRetailer": "SelectRetailer",
        "day_summary": "day_summary",
        END: END
    })

    # From retailer selection
    builder.add_edge("SelectRetailer", "get_retailer_info")
    builder.add_edge("get_retailer_info", "get_sales_pitch")

    # After pitch → either log order, go summary, or wait
    def conditional_after_pitch(state: Dict[str, Any]) -> str:
        msg = (state.get("user_message") or "").lower()
        if "day summary" in msg:
            return "day_summary"
        if state.get("order_products"):
            return "log_order"
        return END  # ✅ wait for order input

    builder.add_conditional_edges("get_sales_pitch", conditional_after_pitch, {
        "log_order": "log_order",
        "day_summary": "day_summary",
        END: END
    })

    # After logging order → check if finished or wait
    def conditional_after_order(state: Dict[str, Any]) -> str:
        msg = (state.get("user_message") or "").lower()
        if "day summary" in msg:
            return "day_summary"

        visited = state.get("visited_retailers", [])
        route = state.get("Beat_Route_Plan", [])
        if route and len(visited) >= len(route):
            return "day_summary"
        return END  # ✅ wait for next "visit ..." from user

    builder.add_conditional_edges("log_order", conditional_after_order, {
        "day_summary": "day_summary",
        END: END
    })

    # End
    builder.add_edge("day_summary", END)

    return builder
