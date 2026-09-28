import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta
from database import (
    init_db, get_db,
    Product, Inventory, PurchaseOrder, AgentLog, Returns, SalesHistory,
    Supplier, Shipment, Alert, AuditTrail,
)
import agents
from llm_assistant import ask as llm_ask

st.set_page_config(
    page_title="Agentic AI Inventory",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_db()

# --- Session state ---
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = time.time()
    st.session_state.agent_status = "Idle"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Sidebar ---
with st.sidebar:
    st.title("🤖 Agentic AI")
    st.markdown("---")

    st.subheader("🟢 System Status")
    status_placeholder = st.empty()
    if st.session_state.agent_status == "Idle":
        status_placeholder.success("Current Agent: **Idle**")
    else:
        status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")

    st.markdown("---")

    if "page" not in st.session_state:
        st.session_state.page = "Command Center"

    pages = [
        "Command Center", "Inventory Overview", "Demand Forecasting",
        "Purchase Orders", "Returns & Refunds", "Logistics",
        "Supplier Management", "Alerts", "Audit Trail",
        "AI Assistant", "Agent Logs",
    ]
    current_index = pages.index(st.session_state.page)
    page = st.selectbox("Navigate", pages, index=current_index, key="nav_selectbox")
    st.session_state.page = page

    st.markdown("---")
    st.subheader("Agent Control")

    if st.button("▶ Run Full AI Cycle", type="primary"):
        st.session_state.agent_status = "Orchestrator: Running Chain..."
        status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
        db = get_db()
        try:
            with st.spinner("Agents are working..."):
                st.session_state.agent_status = "Inventory Sync Agent: Syncing..."
                status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
                agents.sync_inventory_agent(db)

                st.session_state.agent_status = "Forecast Agent: Analyzing..."
                status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
                agents.forecast_agent(db)

                st.session_state.agent_status = "Anomaly Agent: Scanning..."
                status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
                agents.anomaly_detection_agent(db)

                st.session_state.agent_status = "PO Agent: Generating..."
                status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
                agents.po_generation_agent(db)

                st.session_state.agent_status = "Supplier Health Agent: Reviewing..."
                status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
                agents.supplier_health_agent(db)

                st.session_state.agent_status = "Restock Agent: Sweeping..."
                status_placeholder.info(f"Current Agent: **{st.session_state.agent_status}**")
                agents.restock_agent(db)

                st.session_state.agent_status = "Idle"
                status_placeholder.success("Current Agent: **Idle**")
        finally:
            db.close()
        st.rerun()

    if st.button("🔄 Refresh Now"):
        st.rerun()

# --- Main content ---
# IMPORTANT: this try/finally pair wraps ALL page handlers below.
# Every `elif page == "..."` block must stay INSIDE this try block.
# The `finally: db.close()` at the very bottom MUST be at the same indentation
# as the `try:`. If either gets moved or dedented, you'll get a SyntaxError.
db = get_db()
try:
    # ============================================================
    # Command Center
    # ============================================================
    if page == "Command Center":
        st.header("📊 Command Center")

        unresolved_alerts = db.query(Alert).filter(Alert.resolved == False).all()
        if unresolved_alerts:
            sev_color = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
            with st.container():
                st.markdown(f"#### ⚠️ {len(unresolved_alerts)} Active Alerts")
                for a in unresolved_alerts[:5]:
                    st.markdown(
                        f"{sev_color.get(a.severity, '⚪')} **[{a.severity.upper()}]** "
                        f"{a.source} → {a.message}"
                    )

        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        total_inv = sum(i.total_stock for i in db.query(Inventory).all())
        inv_with_price = db.query(Inventory, Product).join(
            Product, Inventory.sku == Product.sku
        ).all()
        total_val = sum(i.total_stock * p.price for i, p in inv_with_price)
        low_stock = db.query(Inventory).filter(Inventory.status != "Healthy").count()
        pending_pos = db.query(PurchaseOrder).filter(PurchaseOrder.status == "Draft").count()

        col1.metric("Total Inventory", f"{total_inv:,}")
        col2.metric("Inventory Value", f"${total_val:,.2f}")
        col3.metric("Low Stock Alerts", low_stock, delta_color="inverse")
        col4.metric("Pending POs", pending_pos)

        st.markdown("---")
        st.subheader("🕒 Agent Activity Feed")
        logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(8).all()
        for log in logs:
            with st.chat_message("assistant"):
                st.write(f"**{log.agent_name}**: {log.action}")
                st.caption(f"{log.timestamp.strftime('%H:%M:%S')} | {log.details}")

    # ============================================================
    # Inventory Overview
    # ============================================================
    
        # ============================================================
    # Inventory Overview
    # ============================================================
    elif page == "Inventory Overview":
        st.header("📦 Inventory Overview")
        st.caption("Per-channel stock levels across your entire catalog.")

        # Read filter values from session state (with defaults)
        cat_filter = st.session_state.get("cat_select", "All Categories")
        chan_filter = st.session_state.get("chan_select", "All Channels")

        col1, col2 = st.columns(2)
        with col1:
            st.selectbox(
                "Category",
                ["All Categories", "Electronics", "Mobile", "Accessories"],
                key="cat_select",
            )
        with col2:
            st.selectbox(
                "Channel",
                ["All Channels", "Amazon", "Flipkart", "Myntra", "Website"],
                key="chan_select",
            )

        # Re-read after widget interaction (Streamlit reruns the script)
        cat_filter = st.session_state.get("cat_select", "All Categories")
        chan_filter = st.session_state.get("chan_select", "All Channels")

        # Build the base query
        query = db.query(Inventory, Product).join(
            Product, Inventory.sku == Product.sku
        )

        # Apply Category filter
        if cat_filter != "All Categories":
            query = query.filter(Product.category == cat_filter)

        # Apply Channel filter — when a specific channel is selected,
        # only show SKUs that actually have stock (>0) in that channel.
        channel_column_map = {
            "Amazon": Inventory.amazon_stock,
            "Flipkart": Inventory.flipkart_stock,
            "Myntra": Inventory.myntra_stock,
            "Website": Inventory.website_stock,
        }
        if chan_filter != "All Channels":
            chan_col = channel_column_map[chan_filter]
            query = query.filter(chan_col > 0)

        data = query.all()

        # Build dataframe
        df_data = []
        for inv, prod in data:
            df_data.append({
                "Product": prod.name,
                "SKU": inv.sku,
                "Category": prod.category,
                "Amazon": inv.amazon_stock,
                "Myntra": inv.myntra_stock,
                "Flipkart": inv.flipkart_stock,
                "Website": inv.website_stock,
                "Total": inv.total_stock,
                "Reorder Pt": inv.reorder_point,
                "Status": inv.status,
            })

        if not df_data:
            st.info(
                f"No products match the selected filters "
                f"(Category: **{cat_filter}**, Channel: **{chan_filter}**)."
            )
        else:
            df = pd.DataFrame(df_data)

            # Show filter summary
            st.caption(
                f"Showing {len(df)} of {db.query(Inventory).count()} SKUs "
                f"• Category: **{cat_filter}** • Channel: **{chan_filter}**"
            )

            def _status_color(val):
                # Dark-theme-friendly colors
                if val == "Critical":
                    return "background-color: #7f1d1d; color: #fecaca; font-weight: bold"
                if val == "Low":
                    return "background-color: #78350f; color: #fde68a; font-weight: bold"
                if val == "Healthy":
                    return "background-color: #14532d; color: #bbf7d0; font-weight: bold"
                return ""

            st.dataframe(
                df.style.map(_status_color, subset=["Status"]),
                use_container_width=True,
                hide_index=True,
            )
    # ============================================================
    # Demand Forecasting
    # ============================================================
    elif page == "Demand Forecasting":
        st.header("📈 Demand Forecasting")
        st.caption("Weighted moving average + linear trend, generated by the Demand Forecast Agent.")

        sku_select = st.selectbox(
            "Select SKU for Analysis",
            [p.sku for p in db.query(Product).all()],
        )
        history = (
            db.query(SalesHistory)
              .filter(SalesHistory.sku == sku_select)
              .order_by(SalesHistory.date)
              .all()
        )

        if not history:
            st.warning("No forecast data yet. Run the AI Cycle first.")
        else:
            hist_df = pd.DataFrame([
                {"Date": h.date, "Actual Sales": h.quantity, "Forecast": h.forecasted_demand}
                for h in history
            ])
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hist_df["Date"], y=hist_df["Actual Sales"],
                mode="lines+markers", name="Actual Sales",
            ))
            fig.add_trace(go.Scatter(
                x=hist_df["Date"], y=hist_df["Forecast"],
                mode="lines+markers", name="AI Forecast",
                line=dict(dash="dash"),
            ))
            fig.update_layout(
                title=f"Sales vs Forecast: {sku_select}",
                xaxis_title="Date",
                yaxis_title="Units",
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.subheader("🤖 AI Recommendation")
            actual_sales = [h.quantity for h in history if h.quantity > 0]
            if actual_sales:
                avg = sum(actual_sales) / len(actual_sales)
                latest_actual = actual_sales[-1]
                latest_forecast = history[-1].forecasted_demand
                if latest_actual > latest_forecast * 1.1:
                    st.success(
                        f"✅ Sales for {sku_select} are exceeding forecasts by "
                        f"{((latest_actual/latest_forecast)-1)*100:.0f}%. "
                        f"Avg demand: {avg:.1f}/day. Maintain or increase stock."
                    )
                elif latest_actual < latest_forecast * 0.9:
                    st.warning(
                        f"⚠️ Sales for {sku_select} are below forecasts. "
                        f"Consider reducing reorder qty to avoid overstock."
                    )
                else:
                    st.info(
                        f"Sales for {sku_select} are tracking forecast closely "
                        f"(avg {avg:.1f}/day)."
                    )

    # ============================================================
    # Purchase Orders
    # ============================================================
    elif page == "Purchase Orders":
        st.header("📑 Purchase Orders")
        st.caption("Each PO has an AI-generated quantity and rationale.")

        pos = db.query(PurchaseOrder).order_by(PurchaseOrder.created_at.desc()).all()
        if not pos:
            st.info("No POs yet. Run the AI Cycle to generate draft POs.")

        for po in pos:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 2])
                c1.write(f"**{po.po_id}**")
                c2.write(f"SKU: `{po.sku}`")
                c3.write(f"Qty: **{po.qty}**")
                status_color = "#22c55e" if po.status == "Approved" else "#f97316"
                c4.markdown(
                    f"<span style='color:{status_color}; font-weight:bold'>"
                    f"{po.status}</span>",
                    unsafe_allow_html=True,
                )
                if po.status == "Draft":
                    if c5.button("Approve", key=f"approve_{po.id}"):
                        po.status = "Approved"
                        po.approved_at = datetime.utcnow()
                        inv = db.query(Inventory).filter(Inventory.sku == po.sku).first()
                        if inv:
                            inv.total_stock += po.qty
                        db.commit()
                        st.rerun()
                if po.rationale:
                    with st.expander("🤖 AI rationale"):
                        st.write(po.rationale)
                st.markdown("---")

    # ============================================================
    # Returns & Refunds
    # ============================================================
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
            ret_data = []
            for r in rets:
                ret_data.append({
                    "Order": r.order_id,
                    "SKU": r.sku,
                    "Channel": r.channel,
                    "Reason": r.reason,
                    "Status": r.status,
                })
            st.dataframe(pd.DataFrame(ret_data), use_container_width=True)

        with right_col:
            st.subheader("Return Reasons")
            reason_counts = {}
            for r in rets:
                reason_counts[r.reason] = reason_counts.get(r.reason, 0) + 1
            if reason_counts:
                fig = px.pie(
                    values=list(reason_counts.values()),
                    names=list(reason_counts.keys()),
                    hole=0.4,
                )
                st.plotly_chart(fig, use_container_width=True)

    # ============================================================
    # Logistics  (NEW)
    # ============================================================
    elif page == "Logistics":
        st.header("🚚 Logistics")
        st.caption("Inbound shipments from suppliers. The Restock Agent auto-delivers any shipment past its ETA.")

        col1, col2, col3 = st.columns(3)
        col1.metric("In Transit", db.query(Shipment).filter(Shipment.status == "In Transit").count())
        col2.metric("Delayed", db.query(Shipment).filter(Shipment.status == "Delayed").count())
        col3.metric("Delivered", db.query(Shipment).filter(Shipment.status == "Delivered").count())

        st.markdown("---")
        st.subheader("Active Shipments")
        shipments = db.query(Shipment).order_by(Shipment.created_at.desc()).all()

        ship_data = []
        for s in shipments:
            eta_str = s.eta.strftime("%Y-%m-%d %H:%M") if s.eta else "-"
            ship_data.append({
                "Shipment ID": s.shipment_id,
                "SKU": s.sku,
                "Qty": s.qty,
                "Carrier": s.carrier,
                "Tracking": s.tracking_id,
                "Status": s.status,
                "ETA": eta_str,
            })

        st.dataframe(pd.DataFrame(ship_data), use_container_width=True)

        if st.button("Run Restock Agent Now", type="primary"):
            delivered = agents.restock_agent(db)
            st.success(f"Delivered {delivered} shipments.")
            st.rerun()

    # ============================================================
    # Supplier Management  (NEW)
    # ============================================================
    elif page == "Supplier Management":
        st.header("🏭 Supplier Management")
        st.caption("Performance scorecard for all suppliers.")

        suppliers = db.query(Supplier).all()
        sup_data = []
        for s in suppliers:
            sup_data.append({
                "Name": s.name,
                "Email": s.contact_email,
                "Phone": s.phone,
                "Lead Time (days)": s.lead_time_days,
                "On-Time Rate": f"{s.on_time_rate*100:.1f}%",
                "Quality Rate": f"{s.quality_rate*100:.1f}%",
                "Active": "✅" if s.active else "❌",
            })
        st.dataframe(pd.DataFrame(sup_data), use_container_width=True)

        st.markdown("---")
        st.subheader("On-Time Rate vs Quality Rate")
        fig = px.scatter(
            [s.__dict__ for s in suppliers],
            x="on_time_rate",
            y="quality_rate",
            text="name",
            labels={"on_time_rate": "On-Time Rate", "quality_rate": "Quality Rate"},
            range_x=[0.8, 1.0],
            range_y=[0.9, 1.0],
        )
        fig.update_traces(textposition="top center")
        st.plotly_chart(fig, use_container_width=True)

        if st.button("Run Supplier Health Agent", type="primary"):
            flagged = agents.supplier_health_agent(db)
            st.success(f"Reviewed {len(suppliers)} suppliers; flagged {flagged}.")
            st.rerun()

    # ============================================================
    # Alerts  (NEW)
    # ============================================================
    elif page == "Alerts":
        st.header("🔔 Alert Center")
        alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(50).all()
        sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
        if not alerts:
            st.success("✅ No alerts. System is healthy.")
        for a in alerts:
            col1, col2, col3 = st.columns([1, 6, 2])
            col1.write(sev_icon.get(a.severity, "⚪"))
            col2.write(f"**{a.source}** → {a.message}")
            col3.write(a.created_at.strftime("%Y-%m-%d %H:%M"))
            if not a.resolved:
                if col3.button("Resolve", key=f"resolve_{a.id}"):
                    a.resolved = True
                    db.commit()
                    st.rerun()
            st.markdown("---")

    # ============================================================
    # Audit Trail  (NEW)
    # ============================================================
    elif page == "Audit Trail":
        st.header("📜 Audit Trail")
        st.caption("Immutable record of every state change in the system.")
        audits = db.query(AuditTrail).order_by(AuditTrail.timestamp.desc()).limit(100).all()
        aud_data = []
        for a in audits:
            aud_data.append({
                "Timestamp": a.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Actor": a.actor,
                "Action": a.action,
                "Entity": a.entity,
                "Entity ID": a.entity_id,
                "Before": a.before,
                "After": a.after,
            })
        st.dataframe(pd.DataFrame(aud_data), use_container_width=True)

    # ============================================================
    # AI Assistant  (NEW)
    # ============================================================
    elif page == "AI Assistant":
        st.header("🤖 AI Assistant")
        st.caption("Ask questions about your inventory in plain English.")

        st.markdown("**Try:**")
        suggestions = [
            "Which SKUs are critical?",
            "What's my total inventory value?",
            "Show me all pending POs",
            "Which supplier has the worst on-time rate?",
            "How many returns are pending?",
        ]
        cols = st.columns(len(suggestions))
        for col, q in zip(cols, suggestions):
            if col.button(q, key=f"sugg_{q}"):
                st.session_state.chat_history.append({"role": "user", "content": q})
                result = llm_ask(q, db)
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "mode": result["mode"],
                })
                st.rerun()

        st.markdown("---")
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])
                if msg["role"] == "assistant" and "mode" in msg:
                    badge = "🧠 LLM" if msg["mode"] == "llm" else "⚙️ Rule-based"
                    st.caption(f"Answer engine: {badge}")

        user_q = st.chat_input("Ask anything about your inventory...")
        if user_q:
            st.session_state.chat_history.append({"role": "user", "content": user_q})
            with st.spinner("Thinking..."):
                result = llm_ask(user_q, db)
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": result["answer"],
                "mode": result["mode"],
            })
            st.rerun()

    # ============================================================
    # Agent Logs
    # ============================================================
    elif page == "Agent Logs":
        st.header("📜 Full Agent Logs")
        logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(50).all()
        for log in logs:
            with st.expander(f"{log.timestamp} | {log.agent_name}"):
                st.write(f"**Action:** {log.action}")
                st.write(f"**Details:** {log.details}")

finally:
    # IMPORTANT: this closes the try block opened above.
    # If you remove this, Python will raise SyntaxError.
    db.close()
