import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta
from database import init_db, get_db, Product, Inventory, PurchaseOrder, AgentLog, Returns, SalesHistory
import agents

# --- Page Config ---
st.set_page_config(page_title="Agentic AI Inventory", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")

# Initialize DB
init_db()

# --- Session State Initialization ---
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()
    st.session_state.agent_status = "Idle"

# --- Sidebar & Navigation ---
with st.sidebar:
    st.title("🤖 Agentic AI")
    st.markdown("---")
    
    # Live Agent Status Display
    st.subheader("🟢 System Status")
    status_placeholder = st.empty()
    status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
    
    st.markdown("---")
    
    # Save page state to prevent reset on rerun
    if 'page' not in st.session_state:
        st.session_state.page = "Command Center"
    
    # Find index to keep selection persistent
    pages = ["Command Center", "Inventory Overview", "Demand Forecasting", "Purchase Orders", "Returns & Refunds", "Logistics", "Agent Logs"]
    current_index = pages.index(st.session_state.page)
    
    page = st.selectbox(
        "Navigate", 
        pages, 
        index=current_index,
        key="nav_selectbox"
    )
    st.session_state.page = page # Update state on change
    
    st.markdown("---")
    st.subheader("Agent Control")
    
    if st.button("▶ Run Full AI Cycle", type="primary"):
        st.session_state.agent_status = "Orchestrator: Running Chain..."
        status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
        
        db = get_db()
        with st.spinner("Agents are working..."):
            agents.sync_inventory_agent(db)
            st.session_state.agent_status = "Forecast Agent: Analyzing..."
            status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
            
            agents.forecast_agent(db)
            st.session_state.agent_status = "PO Agent: Generating..."
            status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
            
            agents.po_generation_agent(db)
            st.session_state.agent_status = "Idle"
            status_placeholder.success(f"Current Agent: **Idle**")
        db.close()
        st.rerun()

    if st.button("🔄 Refresh Now"):
        st.rerun()

# --- Main Content ---
db = get_db()

if page == "Command Center":
    st.header("📊 Command Center")
    
    col1, col2, col3, col4 = st.columns(4)
    total_inv = sum([i.total_stock for i in db.query(Inventory).all()])
    total_val = sum([i.total_stock * p.price for i, p in db.query(Inventory, Product).join(Product, Inventory.sku == Product.sku).all()])
    low_stock = db.query(Inventory).filter(Inventory.status != "Healthy").count()
    
    col1.metric("Total Inventory", total_inv)
    col2.metric("Inventory Value", f"${total_val:,.2f}")
    col3.metric("Low Stock Alerts", low_stock, delta_color="inverse")
    col4.metric("System Health", "98%")
    
    # Activity Feed
    st.markdown("---")
    st.subheader("🕒 Agent Activity Feed")
    logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(5).all()
    
    for log in logs:
        with st.chat_message(log.agent_name if log.agent_name in ["Inventory Sync Agent", "PO Generation Agent", "Demand Forecast Agent"] else "assistant"):
            st.write(f"**{log.agent_name}**: {log.action}")
            st.caption(f"{log.timestamp.strftime('%H:%M:%S')} | {log.details}")

elif page == "Inventory Overview":
    st.header("📦 Inventory Overview")
    st.caption("Per-channel stock levels across your entire catalog.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("Category", ["All Categories", "Electronics", "Mobile", "Accessories"], key="cat_select")
    with col2:
        st.selectbox("Channel", ["All Channels", "Amazon", "Flipkart", "Myntra", "Website"], key="chan_select")
    
    data = db.query(Inventory, Product).join(Product, Inventory.sku == Product.sku).all()
    
    df_data = []
    for inv, prod in data:
        df_data.append({
            "Product": prod.name,
            "Amazon": inv.amazon_stock,
            "Myntra": inv.myntra_stock,
            "Flipkart": inv.flipkart_stock,
            "Website": inv.website_stock,
            "Total": inv.total_stock,
            "Reorder Pt": inv.reorder_point,
            "Status": inv.status
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)

elif page == "Demand Forecasting":
    st.header("📈 Demand Forecasting")
    
    sku_select = st.selectbox("Select SKU for Analysis", [p.sku for p in db.query(Product).all()])
    
    history = db.query(SalesHistory).filter(SalesHistory.sku == sku_select).order_by(SalesHistory.date).all()
    
    if not history:
        st.warning("No forecast data yet. Run the AI Cycle first.")
    else:
        hist_df = pd.DataFrame([{'Date': h.date, 'Actual Sales': h.quantity, 'Forecast': h.forecasted_demand} for h in history])
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist_df['Date'], y=hist_df['Actual Sales'], mode='lines+markers', name='Actual Sales'))
        fig.add_trace(go.Scatter(x=hist_df['Date'], y=hist_df['Forecast'], mode='lines+markers', name='AI Forecast', line=dict(dash='dash')))
        fig.update_layout(title=f"Sales vs Forecast: {sku_select}", xaxis_title="Date", yaxis_title="Units")
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🤖 AI Recommendation")
        latest_actual = hist_df.iloc[-1]['Actual Sales']
        latest_forecast = hist_df.iloc[-1]['Forecast']
        
        if latest_actual > latest_forecast:
            st.success(f"✅ Sales are exceeding forecasts! Demand is high. Maintain current stock levels.")
        else:
            st.warning(f"⚠️ Sales are below forecasts. Consider reducing reorder quantities for {sku_select} to avoid overstock.")

elif page == "Returns & Refunds":
    st.header("↩️ Returns & Refunds")
    
    col1, col2 = st.columns(2)
    pending = db.query(Returns).filter(Returns.status == "Pending").count()
    processed = db.query(Returns).filter(Returns.status == "Processed").count()
    col1.metric("Pending Returns", pending)
    col2.metric("Processed Returns", processed)
    
    if st.button("Process New Returns", type="primary"):
        agents.process_returns_agent(db)
        st.rerun()
    
    st.markdown("---")
    
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.subheader("Recent Returns")
        rets = db.query(Returns).order_by(Returns.created_at.desc()).all()
        ret_data = [{'Order': r.order_id, 'SKU': r.sku, 'Channel': r.channel, 'Status': r.status} for r in rets]
        st.dataframe(pd.DataFrame(ret_data), use_container_width=True)
        
    with right_col:
        st.subheader("Return Reasons")
        reason_counts = {'Damaged': 5, 'Wrong Item': 2, 'Late Delivery': 1}
        fig = px.pie(values=list(reason_counts.values()), names=list(reason_counts.keys()), hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Purchase Orders":
    st.header("📑 Purchase Orders")
    pos = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
    for po in pos:
        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
            c1.write(f"**{po.po_id}**")
            c2.write(f"SKU: {po.sku}")
            c3.write(f"Qty: {po.qty}")
            c4.markdown(f"<span style=\"color:{'green' if po.status=='Approved' else 'orange'}; font-weight:bold\">{po.status}</span>", unsafe_allow_html=True)
            if po.status == "Draft":
                if c5.button("Approve", key=f"approve_{po.id}"):
                    po.status = "Approved"
                    inv = db.query(Inventory).filter(Inventory.sku == po.sku).first()
                    if inv: inv.total_stock += po.qty
                    db.commit()
                    st.rerun()
            st.markdown("---")

elif page == "Agent Logs":
    st.header("📜 Full Agent Logs")
    logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(50).all()
    for log in logs:
        with st.expander(f"{log.timestamp} | {log.agent_name}"):
            st.write(f"**Action:** {log.action}")
            st.write(f"**Details:** {log.details}")
