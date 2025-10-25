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

def _msg(state: Dict[str, Any]) -> str:
    return (state.get("user_message") or "").strip().lower()


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

    # From route -> either wait, select retailer, or day summary
    def after_get_route(state: Dict[str, Any]) -> str:
        # msg = (state.get("user_message") or "").lower()
        msg = _msg(state)
        if "day summary" in msg:
            return "day_summary"
        if "visit" in msg and not state.get("selection_failed", False):
            return "SelectRetailer"
        # No visit/summary in message -> stop now, UI will prompt next user action
        return "__END__"

    builder.add_conditional_edges(
        "get_route",
        after_get_route,
        {
            "day_summary": "day_summary",
            "SelectRetailer": "SelectRetailer",
            "__END__": END,
        },
    )

    # SelectRetailer: either we have a store or fall back to route
    def after_select_retailer(state: Dict[str, Any]) -> str:
        msg = _msg(state)
        if "day summary" in msg:
            return "day_summary"
        # SelectRetailer (your node) will set:
        #   - state["Store_Info"] & ["Retailer_ID"] if matched (and next_node="get_retailer_info")
        #   - OR "next_node"="get_route" if not matched/invalid
        next_node = state.get("next_node")
        if next_node == "get_retailer_info" and state.get("Store_Info"):
            return "get_retailer_info"
        return "__END__"#"get_route"

    # From retailer selection -> either get info or back to route or day summary
    builder.add_conditional_edges(
        "SelectRetailer",
        after_select_retailer,
        {
            "day_summary": "day_summary",
            "get_retailer_info": "get_retailer_info",
            # "get_route": "get_route",
            "__END__": END,
        },
    )


    # From retailer info -> pitch
    builder.add_edge("get_retailer_info", "get_sales_pitch")

    
    # After pitch decide: log order (if cart present) or go back/show route or summary
    def after_pitch(state: Dict[str, Any]) -> str:
        # msg = (state.get("user_message") or "").lower()
        msg = _msg(state)
        if "day summary" in msg:
            return "day_summary"
        if state.get("order_products"):
            return "log_order"
        return "__END__"#"get_route"

    builder.add_conditional_edges(
        "get_sales_pitch",
        after_pitch,
        {
            "day_summary": "day_summary",
            "log_order": "log_order",
            # "get_route": "get_route",
            "__END__": END,
        },
    )

    # After logging order → check if finished or wait
    def after_log_order(state: Dict[str, Any]) -> str:
        # msg = (state.get("user_message") or "").lower()
        msg = _msg(state)
        if "day summary" in msg:
            return "day_summary"

        visited = state.get("visited_retailers", []) or []
        route = state.get("Beat_Route_Plan", []) or []
        # Some agents return {"Beat_Route_Plan": [...]} others embed as dict. Normalize:
        if isinstance(route, dict) and "Beat_Route_Plan" in route:
            route = route.get("Beat_Route_Plan") or []

        if route and len(visited) >= len(route):
            return "day_summary"
        return "__END__"#"get_route"

    builder.add_conditional_edges(
        "log_order",
        after_log_order,
        {
            "day_summary": "day_summary",
            # "get_route": "get_route",
            "__END__": END,
        },
    )

    # End
    builder.add_edge("day_summary", END)

    return builder
