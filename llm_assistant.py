"""
llm_assistant.py
----------------
Natural-language chat over your inventory.
Works with any OpenAI-compatible LLM. Falls back to rule-based if no API key.
"""
import os
import json
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Streamlit Cloud secrets support
try:
    import streamlit as st
    _st_secrets = getattr(st, "secrets", {})
except Exception:
    _st_secrets = {}


def _get_secret(key, default=None):
    """Read a secret from Streamlit secrets, falling back to env vars."""
    if key in _st_secrets:
        return _st_secrets[key]
    return os.getenv(key, default)


def _snapshot(db):
    """Build a compact JSON-serializable snapshot of the current DB state."""
    from database import (
        Product, Inventory, PurchaseOrder, Returns,
        Supplier, Shipment, Alert,
    )

    products_list = []
    for p in db.query(Product).all():
        products_list.append({
            "sku": p.sku,
            "name": p.name,
            "price": p.price,
            "supplier": p.supplier,
            "lead_time_days": p.lead_time_days,
        })

    inventory_list = []
    for i in db.query(Inventory).all():
        inventory_list.append({
            "sku": i.sku,
            "total_stock": i.total_stock,
            "reorder_point": i.reorder_point,
            "status": i.status,
        })

    po_list = []
    for p in db.query(PurchaseOrder).all():
        po_list.append({
            "po_id": p.po_id,
            "sku": p.sku,
            "qty": p.qty,
            "status": p.status,
        })

    returns_list = []
    for r in db.query(Returns).all():
        returns_list.append({
            "order_id": r.order_id,
            "sku": r.sku,
            "status": r.status,
        })

    suppliers_list = []
    for s in db.query(Supplier).all():
        suppliers_list.append({
            "name": s.name,
            "on_time_rate": s.on_time_rate,
            "quality_rate": s.quality_rate,
        })

    shipments_list = []
    for s in db.query(Shipment).all():
        shipments_list.append({
            "shipment_id": s.shipment_id,
            "sku": s.sku,
            "status": s.status,
        })

    unresolved_count = (
        db.query(Alert).filter(Alert.resolved == False).count()
    )

    return {
        "products": products_list,
        "inventory": inventory_list,
        "purchase_orders": po_list,
        "returns": returns_list,
        "suppliers": suppliers_list,
        "shipments": shipments_list,
        "unresolved_alerts": unresolved_count,
    }


def _rule_based_answer(question, snap):
    """Deterministic fallback when no LLM API key is configured."""
    q = question.lower()
    inv = snap["inventory"]
    pos = snap["purchase_orders"]
    sup = snap["suppliers"]
    rets = snap["returns"]

    if "critical" in q or "low stock" in q or "reorder" in q:
        critical = [i for i in inv if i["status"] in ("Critical", "Low")]
        if not critical:
            return "All SKUs are currently Healthy. No reorders needed."
        lines = [
            f"- {i['sku']}: {i['total_stock']} units ({i['status']})"
            for i in critical
        ]
        return "SKUs needing attention:\n" + "\n".join(lines)

    if "total" in q and "value" in q:
        prod_by_sku = {p["sku"]: p["price"] for p in snap["products"]}
        total_val = sum(
            i["total_stock"] * prod_by_sku.get(i["sku"], 0)
            for i in inv
        )
        return (
            f"Total inventory value: ${total_val:,.2f} "
            f"across {len(inv)} SKUs."
        )

    if "pending" in q and "po" in q:
        pending = [p for p in pos if p["status"] == "Draft"]
        if not pending:
            return "No pending (Draft) purchase orders."
        lines = [
            f"- {p['po_id']}: {p['sku']} x{p['qty']}"
            for p in pending
        ]
        return "Pending POs:\n" + "\n".join(lines)

    if "supplier" in q and (
        "worst" in q or "best" in q or "on-time" in q or "performance" in q
    ):
        if not sup:
            return "No suppliers found."
        worst = sorted(sup, key=lambda s: s["on_time_rate"])[0]
        return (
            f"Worst-performing supplier: {worst['name']} "
            f"(on-time rate: {worst['on_time_rate']*100:.1f}%, "
            f"quality: {worst['quality_rate']*100:.1f}%)."
        )

    if "return" in q:
        pending = [r for r in rets if r["status"] == "Pending"]
        return (
            f"There are {len(pending)} pending returns "
            f"out of {len(rets)} total."
        )

    if "alert" in q:
        return f"There are {snap['unresolved_alerts']} unresolved alerts."

    # Default fallback: compact summary
    total_units = sum(i["total_stock"] for i in inv)
    return (
        f"Inventory snapshot: {len(inv)} SKUs, {total_units} total units, "
        f"{len(pos)} POs, {len(rets)} returns, "
        f"{snap['unresolved_alerts']} unresolved alerts."
    )


SYSTEM_PROMPT = (
    "You are an inventory operations assistant. You answer the user's "
    "question strictly based on the JSON snapshot of the inventory database "
    "provided to you in the user message. Be concise, professional, and use "
    "bullet points when listing multiple items. If the answer is not in the "
    "snapshot, say so explicitly."
)


def _llm_answer(question, snap):
    """Call the LLM. Returns None if no API key is configured."""
    api_key = _get_secret("LLM_API_KEY") or _get_secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=_get_secret("LLM_BASE_URL") or None,
        )
        model = _get_secret("LLM_MODEL", "gpt-4o-mini")
        user_msg = (
            f"Question: {question}\n\n"
            f"Database snapshot (JSON):\n{json.dumps(snap, default=str)}"
        )
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return (
            f"(LLM call failed, falling back to rules. Error: {e})"
        )


def ask(question, db):
    """Main entrypoint. Returns dict with 'answer' and 'mode'."""
    snap = _snapshot(db)
    llm_ans = _llm_answer(question, snap)
    if llm_ans:
        return {"answer": llm_ans, "mode": "llm"}
    answer = _rule_based_answer(question, snap)
    return {"answer": answer, "mode": "rules"}
