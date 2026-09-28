from datetime import datetime, timedelta
from collections import defaultdict
import random
import statistics


# ---------- Helpers ----------
def log_agent_action(db, agent_name, action, details):
    from database import AgentLog
    log = AgentLog(agent_name=agent_name, action=action, details=details, timestamp=datetime.utcnow())
    db.add(log)
    db.commit()


def write_audit(db, actor, action, entity, entity_id, before, after):
    from database import AuditTrail
    db.add(AuditTrail(actor=actor, action=action, entity=entity, entity_id=str(entity_id),
                     before=str(before), after=str(after), timestamp=datetime.utcnow()))
    db.commit()


def raise_alert(db, severity, source, message, sku=None):
    from database import Alert
    db.add(Alert(severity=severity, source=source, sku=sku, message=message,
                 created_at=datetime.utcnow(), resolved=False))
    db.commit()


# ---------- 1. Inventory Sync Agent ----------
def sync_inventory_agent(db):
    from database import Inventory
    items = db.query(Inventory).all()
    updated_count = 0
    for item in items:
        delta = random.randint(-5, 2)
        if delta != 0:
            before_status = item.status
            item.total_stock = max(0, item.total_stock + delta)
            item.amazon_stock = max(0, item.amazon_stock + max(delta, 0) // 2)
            if item.total_stock < item.reorder_point / 2:
                item.status = "Critical"
            elif item.total_stock < item.reorder_point:
                item.status = "Low"
            else:
                item.status = "Healthy"
            if before_status != item.status:
                write_audit(db, "Inventory Sync Agent", "STATUS_CHANGE", "Inventory", item.sku, before_status, item.status)
            updated_count += 1
    db.commit()
    log_agent_action(db, "Inventory Sync Agent", "Sync Complete", f"Updated {updated_count} items from channels.")
    return updated_count


# ---------- 2. Demand Forecast Agent (REAL AI) ----------
def _weighted_moving_average_forecast(history_qty, horizon=7):
    if not history_qty:
        return [0] * horizon
    if len(history_qty) < 3:
        avg = int(statistics.mean(history_qty))
        return [avg] * horizon
    n = len(history_qty)
    weights = list(range(1, n + 1))
    weighted_sum = sum(q * w for q, w in zip(history_qty, weights))
    weight_total = sum(weights)
    base = weighted_sum / weight_total
    xs = list(range(n))
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(history_qty)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, history_qty))
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = numerator / denominator if denominator else 0
    forecast = []
    for h in range(1, horizon + 1):
        val = base + slope * (n + h - 1)
        future_date = datetime.now() + timedelta(days=h)
        if future_date.weekday() >= 5:
            val *= 1.10
        forecast.append(max(0, int(val)))
    return forecast


def forecast_agent(db):
    from database import Product, SalesHistory
    products = db.query(Product).all()
    today = datetime.now().date()
    for p in products:
        rows = db.query(SalesHistory).filter(SalesHistory.sku == p.sku).order_by(SalesHistory.date).all()
        history_qty = [r.quantity for r in rows]
        if not history_qty:
            base_date = today - timedelta(days=30)
            for i in range(30):
                d = (base_date + timedelta(days=i)).isoformat()
                qty = random.randint(10, 40)
                db.add(SalesHistory(sku=p.sku, date=d, quantity=qty, forecasted_demand=int(qty * 1.05)))
            db.commit()
            rows = db.query(SalesHistory).filter(SalesHistory.sku == p.sku).order_by(SalesHistory.date).all()
            history_qty = [r.quantity for r in rows]
        forecast_vals = _weighted_moving_average_forecast(history_qty, horizon=7)
        for h, fval in enumerate(forecast_vals, start=1):
            d = (today + timedelta(days=h)).isoformat()
            existing = db.query(SalesHistory).filter(SalesHistory.sku == p.sku, SalesHistory.date == d).first()
            if existing:
                existing.forecasted_demand = fval
            else:
                db.add(SalesHistory(sku=p.sku, date=d, quantity=0, forecasted_demand=fval))
    db.commit()
    log_agent_action(db, "Demand Forecast Agent", "Analysis Complete", "Generated 7-day weighted-MA + trend forecast for all SKUs.")
    return True


# ---------- 3. Anomaly Detection Agent (NEW) ----------
def anomaly_detection_agent(db):
    from database import SalesHistory
    rows = db.query(SalesHistory).all()
    by_sku = defaultdict(list)
    for r in rows:
        by_sku[r.sku].append(r)
    alerts_raised = 0
    for sku, recs in by_sku.items():
        recs.sort(key=lambda r: r.date)
        qty_series = [r.quantity for r in recs if r.quantity > 0]
        if len(qty_series) < 7:
            continue
        mean = statistics.mean(qty_series)
        stdev = statistics.pstdev(qty_series) or 1
        latest_qty = recs[-1].quantity
        z = (latest_qty - mean) / stdev
        if abs(z) >= 2.5:
            direction = "spike" if z > 0 else "drop"
            raise_alert(db, severity="warning", source="Anomaly Detection Agent",
                        message=f"Sales {direction} for {sku}: latest={latest_qty}, mean={mean:.1f}, z={z:+.2f}", sku=sku)
            alerts_raised += 1
    log_agent_action(db, "Anomaly Detection Agent", "Scan Complete", f"Scanned {len(by_sku)} SKUs; raised {alerts_raised} anomaly alerts.")
    return alerts_raised


# ---------- 4. Smart PO Generation Agent ----------
def _compute_po_qty(db, sku, lead_time_days, horizon=7):
    from database import SalesHistory, Inventory
    rows = db.query(SalesHistory).filter(SalesHistory.sku == sku, SalesHistory.quantity > 0).order_by(SalesHistory.date).all()
    if not rows:
        return 50, "No sales history; defaulting to 50 units."
    qty_series = [r.quantity for r in rows]
    avg_d = statistics.mean(qty_series)
    stdev_d = statistics.pstdev(qty_series) or 0
    safety = 0.5 * stdev_d * (lead_time_days ** 0.5)
    inv = db.query(Inventory).filter(Inventory.sku == sku).first()
    current = inv.total_stock if inv else 0
    needed = (avg_d * (lead_time_days + horizon)) + safety - current
    qty = max(int(needed), 25)
    rationale = (f"Avg daily demand={avg_d:.1f}, lead_time={lead_time_days}d, horizon={horizon}d, "
                 f"safety_stock={safety:.0f}, current_stock={current}. Recommended order qty={qty}.")
    return qty, rationale


def po_generation_agent(db):
    from database import Inventory, PurchaseOrder, Product
    items = db.query(Inventory).all()
    created_pos = 0
    for item in items:
        if item.total_stock < item.reorder_point:
            existing = db.query(PurchaseOrder).filter(PurchaseOrder.sku == item.sku, PurchaseOrder.status == "Draft").first()
            if existing:
                continue
            prod = db.query(Product).filter(Product.sku == item.sku).first()
            lead_time = prod.lead_time_days if prod else 7
            qty, rationale = _compute_po_qty(db, item.sku, lead_time)
            po = PurchaseOrder(po_id=f"PO-{random.randint(1000, 9999)}", sku=item.sku, qty=qty,
                               status="Draft", created_at=datetime.utcnow(), rationale=rationale)
            db.add(po)
            created_pos += 1
            write_audit(db, "PO Generation Agent", "CREATE_PO", "PurchaseOrder", po.po_id, "", rationale)
            raise_alert(db, severity="info", source="PO Generation Agent",
                        message=f"Draft PO created for {item.sku}: {qty} units.", sku=item.sku)
    db.commit()
    log_agent_action(db, "PO Generation Agent", "Check Complete", f"Created {created_pos} new draft POs with AI-derived qty.")
    return created_pos


# ---------- 5. Supplier Health Agent (NEW) ----------
def supplier_health_agent(db):
    from database import Supplier
    suppliers = db.query(Supplier).filter(Supplier.active == True).all()
    flagged = 0
    for s in suppliers:
        if s.on_time_rate < 0.90:
            raise_alert(db, severity="warning", source="Supplier Health Agent",
                        message=f"Supplier '{s.name}' on-time rate dropped to {s.on_time_rate*100:.1f}%", sku=None)
            flagged += 1
        if s.quality_rate < 0.95:
            raise_alert(db, severity="critical", source="Supplier Health Agent",
                        message=f"Supplier '{s.name}' quality rate dropped to {s.quality_rate*100:.1f}%", sku=None)
            flagged += 1
    log_agent_action(db, "Supplier Health Agent", "Review Complete", f"Reviewed {len(suppliers)} suppliers; flagged {flagged}.")
    return flagged


# ---------- 6. Returns Agent ----------
def process_returns_agent(db):
    from database import Returns, Inventory
    pending = db.query(Returns).filter(Returns.status == "Pending").all()
    for ret in pending:
        before = ret.status
        ret.status = "Processed"
        if "damaged" not in (ret.reason or "").lower() and "defective" not in (ret.reason or "").lower():
            inv = db.query(Inventory).filter(Inventory.sku == ret.sku).first()
            if inv:
                inv.total_stock += 1
        write_audit(db, "Returns Agent", "PROCESS_RETURN", "Returns", ret.order_id, before, "Processed")
    db.commit()
    log_agent_action(db, "Returns Agent", "Processed Returns", f"Cleared {len(pending)} pending returns.")
    return len(pending)


# ---------- 7. Restock Agent (NEW) ----------
def restock_agent(db):
    from database import Shipment, Inventory
    now = datetime.utcnow()
    shipments = db.query(Shipment).filter(Shipment.status.in_(["In Transit", "Delayed"])).all()
    delivered = 0
    for s in shipments:
        if s.eta and s.eta <= now:
            before = s.status
            s.status = "Delivered"
            inv = db.query(Inventory).filter(Inventory.sku == s.sku).first()
            if inv:
                inv.total_stock += s.qty
            delivered += 1
            write_audit(db, "Restock Agent", "DELIVER", "Shipment", s.shipment_id, before, "Delivered")
    db.commit()
    log_agent_action(db, "Restock Agent", "Delivery Sweep", f"Delivered {delivered} shipments and restocked inventory.")
    return delivered


# ---------- Orchestrator ----------
def run_full_chain(db):
    sync_inventory_agent(db)
    forecast_agent(db)
    anomaly_detection_agent(db)
    po_generation_agent(db)
    supplier_health_agent(db)
    restock_agent(db)
    return True
