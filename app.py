import streamlit as st
import pandas as pd
import plotly.express as px
from database import init_db, get_db, Product, Inventory, PurchaseOrder, AgentLog
import agents

# --- Page Config ---
st.set_page_config(
    page_title="Agentic AI Inventory",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize DB ---
init_db()

# --- Session State Initialization ---
if 'db' not in st.session_state:
    st.session_state.db = get_db()
if 'refresh' not in st.session_state:
    st.session_state.refresh = False

def refresh_data():
    # Refresh session state DB
    st.session_state.db = get_db()
    st.rerun()

# --- Sidebar ---
with st.sidebar:
    st.title("🤖 Agentic AI")
    st.markdown("---")

    page = st.sidebar.selectbox("Navigate", ["Command Center", "Inventory Map", "Demand Forecast", "Purchase Orders", "Logistics", "Agent Logs"])
    
    st.markdown("---")
    st.subheader("Agent Control")
    if st.button("▶ Run Full AI Cycle", type="primary"):
        with st.spinner("Orchestrator running agents..."):
            db = st.session_state.db
            agents.run_full_chain(db)
            st.success("Cycle Complete!")
            refresh_data()
    
    if st.button("🔄 Refresh Data"):
        refresh_data()

# --- Pages ---

db = st.session_state.db

if page == "Command Center":
    st.header("📊 Command Center")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_inv = sum([i.total_stock for i in db.query(Inventory).all()])
    total_val = sum([i.total_stock * p.price for i, p in db.query(Inventory, Product).join(Product, Inventory.sku == Product.sku).all()])
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.status == "Draft").count()
    
    col1.metric("Total Stock", total_inv)
    col2.metric("Inventory Value", f"${total_val:,.2f}")
    col3.metric("Pending POs", pos, delta_color="inverse")
    col4.metric("Active Agents", "8/8")
    
    st.markdown("---")
    
    # Low Stock Alerts
    st.subheader("⚠️ Low Stock Alerts")
    low_stock = db.query(Inventory, Product).join(Product, Inventory.sku == Product.sku).filter(Inventory.total_stock < 20).all()
    
    if low_stock:
        for inv, prod in low_stock:
            st.error(f"**{prod.sku}** ({prod.name}) is critically low: {inv.total_stock} units")
    else:
        st.success("All stock levels are healthy.")

elif page == "Inventory Map":
    st.header("🏭 Inventory Visualization")
    
    data = db.query(Inventory, Product).join(Product, Inventory.sku == Product.sku).all()
    
    # Convert to DataFrame for plotting
    df_data = []
    for inv, prod in data:
        df_data.append({
            "SKU": inv.sku,
            "Name": prod.name,
            "Amazon": inv.amazon_stock,
            "Flipkart": inv.flipkart_stock,
            "Total": inv.total_stock
        })
    
    df = pd.DataFrame(df_data)
    
    # Interactive Bar Chart
    fig = px.bar(df, x="SKU", y=["Amazon", "Flipkart", "Shopify"], barmode="group", title="Stock by Channel")
    st.plotly_chart(fig, use_container_width=True)
    
    # Data Table
    st.subheader("Detailed Table")
    st.dataframe(df, use_container_width=True)

elif page == "Purchase Orders":
    st.header("📑 Purchase Orders")
    
    pos = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
    
    for po in pos:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 2])
            col1.write(f"**{po.po_id}**")
            col2.write(f"SKU: {po.sku}")
            col3.write(f"Qty: {po.qty}")
            
            # Status Badge
            if po.status == "Draft":
                col4.markdown(f'<span style="color:orange; font-weight:bold">{po.status}</span>', unsafe_allow_html=True)
            else:
                col4.markdown(f'<span style="color:green; font-weight:bold">{po.status}</span>', unsafe_allow_html=True)
                
            if po.status == "Draft":
                if col5.button("Approve", key=f"approve_{po.id}"):
                    po.status = "Approved"
                    # Update Stock
                    inv = db.query(Inventory).filter(Inventory.sku == po.sku).first()
                    if inv: inv.total_stock += po.qty
                    db.commit()
                    st.rerun()
            else:
                col5.write("—")
            st.markdown("---")

elif page == "Agent Logs":
    st.header("📜 Agent Activity Logs")
    
    logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(20).all()
    
    for log in logs:
        with st.chat_message(log.agent_name if log.agent_name in ["Inventory Sync Agent", "PO Generation Agent"] else "assistant"):
            st.write(f"**{log.agent_name}**: {log.action}")
            st.caption(f"{log.timestamp} | {log.details}")
