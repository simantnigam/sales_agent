from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda
from utils.set_state import SalesRepState
import difflib
from dotenv import load_dotenv
import os
import re

load_dotenv(override=True)

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

def normalize_route(route_like):
    if isinstance(route_like, dict) and "Beat_Route_Plan" in route_like:
        return route_like.get("Beat_Route_Plan") or []
    return route_like or []

llm = ChatOpenAI(model="gpt-4o-mini")


select_prompt = ChatPromptTemplate.from_messages([
    ("system", 
     "You're a helpful assistant helping a sales rep select a store to visit from their daily route. "
     "You are given a list of retailers (with their IDs and names). Based on the user's message, identify the matching retailer."),
    ("user", "User message: {user_message}\n\nRetailer Route: {route_names}")
])

select_chain = select_prompt | llm | StrOutputParser()


def select_retailer_node(state: SalesRepState) -> SalesRepState:
    user_message = state.get("user_message", "")
    # route = state.get("Beat_Route_Plan")
    route = normalize_route(state.get("Beat_Route_Plan"))

    # Defensive fallback
    if isinstance(route, dict) and "Beat_Route_Plan" in route:
        route = route["Beat_Route_Plan"]
    elif not isinstance(route, list):
        # raise ValueError("Invalid Beat_Route_Plan format. Expected a list of retailers.")
        state["user_message"] = "Invalid Beat_Route_Plan format."
        state["next_node"] = "get_route"
        return state
    

    # 1) DIRECT MATCH: "visit 1" -> Visit_Sequence
    seq_match = re.search(r"\bvisit\s*(store\s*number\s*)?(\d+)\b", user_message)
    if seq_match:
        seq = int(seq_match.group(2))
        store = next((r for r in route if int(r["Visit_Sequence"]) == seq), None)
        if store:
            state["Store_Info"] = store
            state["Retailer_ID"] = store["Retailer_ID"]
            state["next_node"] = "get_retailer_info"
            state["selection_failed"] = False

            print(f"[Debug] select retailer: {state['Retailer_ID']} by Visit_Sequence {seq}")
            return state
        
    # 2) DIRECT MATCH BY Retailer_ID
    id_match = re.search(r"\b([A-Za-z0-9]{3,6})\b", user_message)
    if id_match:
        token = id_match.group(1).upper()
        store = next((r for r in route if str(r["Retailer_ID"]).upper() == token), None)
        if store:
            state["Store_Info"] = store
            state["Retailer_ID"] = store["Retailer_ID"]
            state["next_node"] = "get_retailer_info"
            state["selection_failed"] = False
            return state

    # Construct retailer names list
    # route_names = [f"{r['Retailer_ID']} - {r['Name']} - Sequence :{r['Visit_Sequence']}" for r in route]
    route_names = [f"{r['Visit_Sequence']}. {r['Name']} (ID: {r['Retailer_ID']})" for r in route]
    
    # Run LLM chain
    selected_name = select_chain.invoke({
        "user_message": user_message,
        "route_names": "\n".join(route_names)
    })

    # Fuzzy match with original route
    match = []
    attempts = 10
    while attempts > 0 and not match:
        match = difflib.get_close_matches(selected_name.strip(), route_names, n=1, cutoff=0.4)
        attempts -= 1

    if not match:
        # raise ValueError("No matching store found. Please rephrase.")
        state["Retailer_ID"] = None
        state["Store_Info"] = None
        state["user_message"] = f"No matching store found for '{user_message}'. Showing route again."
        state["next_node"] = "get_route"
        state["selection_failed"] = True
        return state

    matched_id = match[0].split(" - ")[0]

    # selected_store = next((r for r in route if r["Retailer_ID"] == matched_id), None)
    selected_store = next((r for r in route if str(r["Retailer_ID"]) == matched_id), None)

    state["Retailer_ID"] = matched_id
    state["Store_Info"] = selected_store
    state["next_node"] = "get_retailer_info"
    state["selection_failed"] = False
    
    return state



SelectRetailer = RunnableLambda(select_retailer_node)





