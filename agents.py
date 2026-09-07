from datetime import datetime, timedelta
import random

def log_agent_action(db, agent_name, action, details):
    from database import AgentLog
    log = AgentLog(agent_name=agent_name, action=action, details=details, timestamp=datetime.utcnow())
    db.add(log)
    db.commit()

def sync_inventory_agent(db):
    from database import Inventory
    items = db.query(Inventory).all()
    updated_count = 0
    for item in items:
        delta = random.randint(-5, 2)
        if delta != 0:
            item.total_stock = max(0, item.total_stock + delta)
            item.amazon_stock = max(0, item.amazon_stock + delta)
            
            # Auto-update status
            if item.total_stock < item.reorder_point:
                item.status = "Critical" if item.total_stock < item.reorder_point/2 else "Low"
            else:
                item.status = "Healthy"
            
            updated_count += 1
    db.commit()
    log_agent_action(db, "Inventory Sync Agent", "Sync Complete", f"Updated {updated_count} items from channels.")
    return updated_count

def forecast_agent(db):
    from database import Product, SalesHistory
    products = db.query(Product).all()
    
    for p in products:
        # Generate dummy historical data for the last 7 days
        base_date = datetime.now() - timedelta(days=7)
        for i in range(7):
            date = base_date + timedelta(days=i)
            existing = db.query(SalesHistory).filter(SalesHistory.sku == p.sku, SalesHistory.date == date.date().isoformat()).first()
            if not existing:
                qty = random.randint(5, 50)
                # Simple forecast logic: Next day is 110% of average
                forecast = int(qty * 1.1)
                hist = SalesHistory(sku=p.sku, date=date.date().isoformat(), quantity=qty, forecasted_demand=forecast)
                db.add(hist)
    
    db.commit()
    log_agent_action(db, "Demand Forecast Agent", "Analysis Complete", "Generated 7-day forecast for all SKUs.")
    return True

def po_generation_agent(db):
    from database import Inventory, PurchaseOrder
    items = db.query(Inventory).all()
    created_pos = 0
    for item in items:
        if item.total_stock < item.reorder_point:
            existing = db.query(PurchaseOrder).filter(PurchaseOrder.sku == item.sku, PurchaseOrder.status == "Draft").first()
            if not existing:
                po = PurchaseOrder(po_id=f"PO-{random.randint(1000,9999)}", sku=item.sku, qty=50, status="Draft", created_at=datetime.utcnow())
                db.add(po)
                created_pos += 1
    db.commit()
    log_agent_action(db, "PO Generation Agent", "Check Complete", f"Created {created_pos} new POs.")
    return created_pos

def process_returns_agent(db):
    from database import Returns
    pending = db.query(Returns).filter(Returns.status == "Pending").all()
    for ret in pending:
        ret.status = "Processed"
        # Logic: Refund processed, maybe restock
    db.commit()
    log_agent_action(db, "Returns Agent", "Processed Returns", f"Cleared {len(pending)} pending returns.")
    return len(pending)

def run_full_chain(db):
    sync_inventory_agent(db)
    forecast_agent(db)
    po_generation_agent(db)
    return True
