import streamlit as st
from langgraph.checkpoint.memory import MemorySaver
from agent_orchastrator.sales_assist_orchastrator import build_agent_graph
from utils.get_sales_reps import get_active_agents
from utils.get_day import get_current_day
import base64
from io import BytesIO
import uuid
from PIL import Image
import sqlite3
from agents.order_logging_agent import OrderLoggingAgent

db_path = "sales_agent_co_pilot.db"

# Helper: fetch product price
def get_product_price(product_id: str) -> float:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT Price FROM products WHERE Product_ID = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0.0

# Memory & Graph Setup
# thread_id = str(uuid.uuid4())
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
builder = build_agent_graph()
memory = MemorySaver()

executable_graph = builder.compile(
    checkpointer=memory
)

config = {"configurable": {"thread_id": st.session_state.thread_id}}


# UI Setup
st.set_page_config(page_title="Sales Assistant", layout="wide")
tab1, tab2 = st.tabs(["Sales Rep Assistant", "Agentic Flow"])

# if "thread_id" not in st.session_state:
#     st.session_state.thread_id = thread_id


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
            init_state = {
                "sales_rep_id": selected_rep,
                "Weekday": st.session_state.weekday
            }


            #initial graph run
            result = executable_graph.invoke(init_state,config=config)
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
            prev_state = st.session_state.get("graph_state", {})
            new_state = {
                **prev_state,
                "sales_rep_id": st.session_state.sales_rep_id,
                "Weekday": st.session_state.weekday,
                "user_message": user_input
            }

            result = executable_graph.invoke(new_state, config=config)
            st.session_state.graph_state = result

            response = ""

            # ---- Handle different queries ----
            if "day summary" in user_input.lower():
                response = f"## End of Day Summary\n\n{result.get('Day_Summary', 'No summary available')}"

            elif "plan" in user_input.lower():
                # route = graph_state.get("Beat_Route_Plan", [])
                route = result.get("Beat_Route_Plan", [])
                if route:
                    route_str = "\n".join([f"{r['Visit_Sequence']}. {r['Name']}" for r in route])
                    response = f"Route Plan for today :\n{route_str}"
                else:
                    response = "Route plan not found."

            elif "visit" in user_input.lower():
                if "Store_Info" not in result or not result["Store_Info"]:
                    response = "No store matched your request. Please try again."
                else:
                    store_info = result["Store_Info"]
                    retailer_id = store_info["Retailer_ID"]
                    visit_id = str(uuid.uuid4())

                    pitch = result.get("Pitch", "No pitch available.")
                    stock = result.get("Last_Visit_Stock", [])
                    recs = result.get("Product_Recommendations", [])

                    rec_text = "\n".join([f"- {r['Product_Name']}" for r in recs]) if recs else "None"
                    stock_text = "\n".join([f"- {s['Product_Name']}: {s['Available_Stock']}" for s in stock]) if stock else "No stock data"

                    response = f"""
                    ### Store: {store_info.get("Name", "Unknown")}

                    **Last Visit Stock:**  
                    {stock_text}

                    **Recommended Products:**  
                    {rec_text}

                    **Suggested Pitch:**  
                    {pitch}
                    """

                    # Order logging form
                    with st.form(key=f"order_form_{visit_id}"):
                        st.subheader("Log Order")

                        if recs:
                            product_options = {rec["Product_Name"]: rec["Product_ID"] for rec in recs}
                            selected_product_name = st.selectbox("Select Product", list(product_options.keys()))
                            selected_product_id = product_options[selected_product_name]

                            price = get_product_price(selected_product_id)
                            st.markdown(f"**Price:** {price}")

                            qty = st.number_input("Enter Quantity", min_value=1, step=1)
                            feedback = st.text_area("Retailer Feedback (optional)")

                            if st.form_submit_button("Log Order"):
                                order_products = [{
                                    "Product_ID": selected_product_id,
                                    "Quantity": qty,
                                    "Available_Stock": 0,
                                    "Price": price
                                }]

                                new_state = {
                                    **result,
                                    "sales_rep_id": st.session_state.sales_rep_id,
                                    "Weekday": st.session_state.weekday,
                                    "order_products": order_products,
                                    "feedback": feedback
                                }

                                result = executable_graph.invoke(new_state, config=config)
                                st.session_state.graph_state = result

                                st.success(f"✅ Order for {selected_product_name} logged successfully!")
                                st.session_state.messages.append({
                                    "role": "assistant",
                                    "content": f"Order logged for {selected_product_name}. Please select the next store from your beat plan."
                                })
                                st.rerun()

            # --- Append bot response ---
            if response:
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.rerun()


# Agentic Flow Tab
with tab2:
    st.title("Agentic Flow")

    # Mermaid render
    png_bytes = executable_graph.get_graph().draw_mermaid_png()
    image = Image.open(BytesIO(png_bytes))
    st.image(image, caption="Agentic Flow Diagram")


    # Download PNG
    if st.button("Export Graph PNG"):
        png_bytes = executable_graph.get_graph().draw_mermaid_png()
        b64 = base64.b64encode(png_bytes).decode()
        href = f'<a href="data:image/png;base64,{b64}" download="sales_graph.png">Download PNG</a>'
        st.markdown(href, unsafe_allow_html=True)