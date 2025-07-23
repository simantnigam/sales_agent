import streamlit as st
from langgraph.checkpoint.memory import MemorySaver
from agent_orchastrator.sales_assist_orchastrator import build_agent_graph
from utils.get_sales_reps import get_active_agents
from utils.get_day import get_current_day
import base64
from io import BytesIO
import uuid
from PIL import Image




# Memory & Graph Setup
thread_id = str(uuid.uuid4())
builder = build_agent_graph()
memory = MemorySaver()

executable_graph = builder.compile(
    checkpointer=memory
)

config = {"configurable": {"thread_id": thread_id}}


# UI Setup
st.set_page_config(page_title="Sales Assistant", layout="wide")
tab1, tab2 = st.tabs(["Sales Rep Assistant", "Agentic Flow"])

if "thread_id" not in st.session_state:
    st.session_state.thread_id = thread_id


# Chat bot tab

with tab1:
    st.title("AI Sales Rep Assistant")

    if "messages" not in st.session_state:
        st.session_state.messages = []

        weekday = get_current_day()
        sales_reps = get_active_agents()
        st.session_state.weekday = weekday
        st.session_state.sales_reps = sales_reps

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Hello! Today is **{weekday}**. Please select your Sales Rep to begin:"
        })

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Sales rep dropdown
    if "sales_rep_id" not in st.session_state:
        selected_rep = st.selectbox("Select Sales Rep", st.session_state.sales_reps)
        if st.button("Confirm"):
            st.session_state.sales_rep_id = selected_rep


            # Initial state
            state = {
                "sales_rep_id": selected_rep,
                "Weekday": st.session_state.weekday
            }


            #initial graph run
            result = executable_graph.invoke(state,config=config)
            st.session_state.graph_state = result

            # Append beat info
            beat_id = result.get("Beat_ID")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"Assigned Beat ID for {selected_rep}: **{beat_id}**"
            })
            st.rerun()


    else:
        # Chat Input
        user_input = st.chat_input("Ask your assistant...")


        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})

            # Parse based on simple heuristics
            response = ""
            graph_state = st.session_state.graph_state

            if "plan" in user_input.lower():
                route = graph_state.get("Beat_Route_Plan", [])
                if route:
                    route_str = "\n".join([f"{r['Visit_Sequence']}. {r['Name']}" for r in route])
                    response = f"Route Plan for today :\n{route_str}"
                else:
                    response = "Route plan not found."

            if "visit" in user_input.lower():
                graph_state = st.session_state.get("graph_state", {})
                state = {
                    "sales_rep_id": st.session_state.sales_rep_id,
                    "Weekday": st.session_state.weekday,
                    "user_message": user_input
                }

                # Re-invoke the graph with new user message
                result = executable_graph.invoke(state, config=config)
                st.session_state.graph_state = result

                pitch = result["Pitch"]
                stock = result["Last_Visit_Stock"]
                recs = result["Product_Recommendations"]


                rec_text = "\n".join([f"- {r['Product_Name']}" for r in recs])
                stock_text = "\n".join([f"- {s['Product_Name']}: {s['Available_Stock']}" for s in stock])

                response = f"""
                ### Store: {result['Store_Info'].get("Name")}

                **Last Visit Stock:**  
                {stock_text}

                **Recommended Products:**  
                {rec_text}

                **Suggested Pitch:**  
                {pitch}
                """



            st.session_state.messages.append({"role": "assistant","content": response})
            st.rerun()