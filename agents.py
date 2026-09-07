from datetime import datetime
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
            updated_count += 1
    db.commit()
    log_agent_action(db, "Inventory Sync Agent", "Sync Complete", f"Updated {updated_count} items.")
    return updated_count

def po_generation_agent(db):
    from database import Inventory, PurchaseOrder
    items = db.query(Inventory).all()
    created_pos = 0
    for item in items:
        if item.total_stock < 20:
            existing = db.query(PurchaseOrder).filter(PurchaseOrder.sku == item.sku, PurchaseOrder.status == "Draft").first()
            if not existing:
                po = PurchaseOrder(po_id=f"PO-{random.randint(1000,9999)}", sku=item.sku, qty=50, status="Draft", created_at=datetime.utcnow())
                db.add(po)
                created_pos += 1
    db.commit()
    log_agent_action(db, "PO Generation Agent", "Check Complete", f"Created {created_pos} new POs.")
    return created_pos

def run_full_chain(db):
    sync_inventory_agent(db)
    po_generation_agent(db)
    return True
