# app.py
import uuid
import base64
import sqlite3
from io import BytesIO
from PIL import Image

import streamlit as st
from langgraph.checkpoint.memory import MemorySaver

from agent_orchastrator.sales_assist_orchastrator import build_agent_graph
from utils.get_sales_reps import get_active_agents
from utils.get_day import get_current_day


DB_PATH = "sales_agent_co_pilot.db"

# ---------- Helpers ----------
def get_product_price(product_id: str) -> float:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT Price FROM products WHERE Product_ID = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    return float(row[0]) if row else 0.0

def ensure_list(val):
    return val if isinstance(val, list) else []

def normalize_route(route_like):
    if isinstance(route_like, dict) and "Beat_Route_Plan" in route_like:
        return route_like.get("Beat_Route_Plan") or []
    return route_like or []


# ---------- Streamlit App State ----------
st.set_page_config(page_title="Sales Assistant", layout="wide")

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "cart" not in st.session_state:
    st.session_state.cart = []   # [{Product_ID, Product_Name, Quantity, Price}]

if "graph_state" not in st.session_state:
    st.session_state.graph_state = {}

if "show_cart_ui" not in st.session_state:
    st.session_state.show_cart_ui = False

# ---------- Graph Setup ----------
memory = MemorySaver()
builder = build_agent_graph()
executable_graph = builder.compile(checkpointer=memory)
config = {"configurable": {"thread_id": st.session_state.thread_id}}

# ---------- UI Tabs ----------
tab1, tab2 = st.tabs(["Sales Rep Assistant", "Agentic Flow"])


# =====================================
# TAB 1 — CHAT / SALES REP WORKFLOW UI
# =====================================
with tab1:
    st.title("AI Sales Rep Assistant")

    # First-time greeting
    if not st.session_state.messages:
        weekday = get_current_day()
        sales_reps = get_active_agents()
        st.session_state.weekday = weekday
        st.session_state.sales_reps = sales_reps

        st.session_state.messages.append({
            "role": "assistant",
            "content": f"Hello! Today is **{weekday}**. Please select your Sales Rep to begin."
        })

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ---------- Select Sales Rep ----------
    if "sales_rep_id" not in st.session_state:
        selected_rep = st.selectbox("Select Sales Rep", st.session_state.sales_reps)
        if st.button("Confirm"):
            st.session_state.sales_rep_id = selected_rep
            
            state = {
                "sales_rep_id": selected_rep,
                "Weekday": st.session_state.weekday,
                "user_message": ""
            }

            result = executable_graph.invoke(state, config=config)
            st.session_state.graph_state = result

            beat_id = result.get("Beat_ID", "N/A")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"✅ Assigned Beat: **{beat_id}**\n\nType **plan** to view route or **visit <store>** to begin."
            })
            st.rerun()

    # ---------- Process User Input ----------
    else:
        user_input = st.chat_input("Ask your assistant…")

        if user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})

            prev_state = st.session_state.graph_state
            new_state = {
                **prev_state,
                "sales_rep_id": st.session_state.sales_rep_id,
                "Weekday": st.session_state.weekday,
                "user_message": user_input
            }

            if "visit" not in user_input.lower():
                st.session_state.show_cart_ui = False

            result = executable_graph.invoke(new_state, config=config)
            st.session_state.graph_state = result

            # ----- Day Summary -----
            if "day summary" in user_input.lower():
                summary = result.get("Day_Summary", "No summary available.")
                st.session_state.messages.append({"role": "assistant", "content": summary})
                st.rerun()

            # ----- Show Route -----
            # if "plan" in user_input.lower():
            #     route = normalize_route(result.get("Beat_Route_Plan"))
            #     plan = "\n".join([f"{r['Visit_Sequence']}. {r['Name']} (ID: {r['Retailer_ID']})" for r in route])
            #     st.session_state.messages.append({"role": "assistant", "content": f"### 📍 Route Plan\n{plan}"})
            #     st.rerun()
            if "plan" in user_input.lower():
                route = normalize_route(result.get("Beat_Route_Plan"))
                # visited_retailers is expected to be a list of retailer IDs in the graph state
                visited = set(map(str, result.get("visited_retailers", []) or []))

                # If user asked for unvisited/remaining, filter out visited stores
                show_only_unvisited = any(k in user_input.lower() for k in ("unvisited", "remaining", "pending", "not visited"))

                lines = []
                for r in route:
                    rid = str(r.get("Retailer_ID", ""))
                    seq = r.get("Visit_Sequence", "?")
                    name = r.get("Name", "Unknown")
                    if show_only_unvisited and rid in visited:
                        continue
                    suffix = " (visited)" if rid in visited else ""
                    lines.append(f"{seq}. {name} (ID: {rid}){suffix}")

                if not lines:
                    if show_only_unvisited:
                        msg = "✅ No unvisited stores remain on the route."
                    else:
                        msg = "No stores available in the route."
                else:
                    msg = "### 📍 Route Plan\n" + "\n".join(lines)

                st.session_state.messages.append({"role": "assistant", "content": msg})
                st.rerun()

            # ----- Visit Store -----
            if "visit" in user_input.lower():
                store = result.get("Store_Info")

                if not store:
                    # No match → Show plan again
                    route = normalize_route(result.get("Beat_Route_Plan"))
                    hint = "⚠️ Could not match the store. Try: `visit <store name/id/sequence>`"
                    plan = "\n".join([f"{r['Visit_Sequence']}. {r['Name']} (ID: {r['Retailer_ID']})" for r in route])
                    st.session_state.messages.append({"role": "assistant", "content": f"{hint}\n\n### Route\n{plan}"})
                    st.rerun()

                stock = ensure_list(result.get("Last_Visit_Stock"))
                recs = ensure_list(result.get("Product_Recommendations"))
                pitch = result.get("Pitch", "")

                stock_text = "\n".join([f"- {s['Product_Name']}: {s['Available_Stock']}" for s in stock])
                rec_text = "\n".join([f"- {r['Product_Name']}" for r in recs])

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"""### 🏬 {store['Name']} (ID: {store['Retailer_ID']})

**Last Visit Stock:**  
{stock_text or 'No stock data'}

**Recommended Products:**  
{rec_text or 'No recommendations'}

**Suggested Pitch:**  
{pitch or 'No pitch available.'}
"""
                })

                # ✅ Rerun here to show summary first, then UI below
                st.session_state.show_cart_ui = True
                st.rerun()


        # -----------------------
        # ✅ SECOND-PHASE UI RENDERING (Add-To-Cart)
        # -----------------------
        result = st.session_state.graph_state
        store = result.get("Store_Info")

        if st.session_state.show_cart_ui and store:
            

            st.write("---")
            st.subheader("🛒 Add to Cart")


            recs = ensure_list(result.get("Product_Recommendations"))
            product_options = {r["Product_Name"]: r["Product_ID"] for r in recs}

            if product_options:
                selected_name = st.selectbox("Product", list(product_options.keys()))
                qty = st.number_input("Quantity", min_value=1, step=1)
                available_stock = st.number_input("Available Stock", min_value=0, step=1, value=0)
                # feedback = st.text_area("Retailer Feedback")

                if st.button("Add to Order"):
                    pid = product_options[selected_name]
                    price = get_product_price(pid)
                    st.session_state.cart.append({
                        "Product_ID": pid,
                        "Product_Name": selected_name,
                        "Quantity": int(qty),
                        "Price": price,
                        "Available_Stock": int(available_stock)
                    })
                    st.success(f"✅ Added {selected_name}")

            if st.session_state.cart:
                st.subheader("🧾 Current Order")
                for item in st.session_state.cart:
                    st.write(f"- {item['Product_Name']} x {item['Quantity']} @ {item['Price']}")

                feedback = st.text_area("Retailer Feedback")

                if st.button("Submit Order ✅"):
                    visit_id = str(uuid.uuid4())
                    order_state = {
                        **result,
                        "visit_id": visit_id,
                        "retailer_id": store["Retailer_ID"],
                        "order_products": st.session_state.cart,
                        "feedback": feedback
                    }
                    result2 = executable_graph.invoke(order_state, config=config)
                    st.session_state.graph_state = result2
                    st.session_state.cart = []
                    st.session_state.show_cart_ui = False
                    st.success("Order submitted! Continue with `visit next` or `plan`.")
                    st.rerun()

                if st.button("No Order to Submit"):
                    visit_id = str(uuid.uuid4())
                    st.session_state.cart = []
                    order_state = {
                        **result,
                        "visit_id": visit_id,
                        "retailer_id": store["Retailer_ID"],
                        "order_products": st.session_state.cart,
                        "feedback": feedback
                    }
                    result2 = executable_graph.invoke(order_state, config=config)
                    st.session_state.graph_state = result2
                    st.session_state.show_cart_ui = False
                    st.info("No order submitted. You can continue with `visit next` or `plan`.")
                    st.rerun()


# =====================================
# TAB 2 — GRAPH VISUALIZATION
# =====================================
# ---------- tab 2 ----------
with tab2:
    st.title("Agentic Flow")
    png_bytes = executable_graph.get_graph().draw_mermaid_png()
    image = Image.open(BytesIO(png_bytes))
    st.image(image, caption="Agentic Flow Diagram")

    if st.button("Export Graph PNG"):
        b64 = base64.b64encode(png_bytes).decode()
        href = f'<a href="data:image/png;base64,{b64}" download="sales_graph.png">Download PNG</a>'
        st.markdown(href, unsafe_allow_html=True)
