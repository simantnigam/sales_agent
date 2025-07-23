from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableLambda
from utils.set_state import SalesRepState
import difflib
from dotenv import load_dotenv
import os

load_dotenv(override=True)

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")



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
    route = state.get("Beat_Route_Plan")

    # Defensive fallback
    if isinstance(route, dict) and "Beat_Route_Plan" in route:
        route = route["Beat_Route_Plan"]
    elif not isinstance(route, list):
        raise ValueError("Invalid Beat_Route_Plan format. Expected a list of retailers.")

    # Construct retailer names list
    route_names = [f"{r['Retailer_ID']} - {r['Name']}" for r in route]
    
    # Run LLM chain
    selected_name = select_chain.invoke({
        "user_message": user_message,
        "route_names": "\n".join(route_names)
    })

    # Fuzzy match with original route
    match = []
    attempts = 5
    while attempts > 0 and not match:
        match = difflib.get_close_matches(selected_name.strip(), route_names, n=1, cutoff=0.4)
        attempts -= 1

    if not match:
        raise ValueError("No matching store found. Please rephrase.")

    matched_id = match[0].split(" - ")[0]

    selected_store = next((r for r in route if r["Retailer_ID"] == matched_id), None)
    return {
        "Store_Info": selected_store
    }



SelectRetailer = RunnableLambda(select_retailer_node)





