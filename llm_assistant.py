"""
llm_assistant.py — NL chat over your inventory.
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
    if key in _st_secrets:
        return _st_secrets[key]
    return os.getenv(key, default)


def _snapshot(db) -> dict:
    from database import (Product, Inventory, PurchaseOrder, Returns, Supplier, Shipment, Alert)
    return {
        "products": [{"sku": p.sku, "name": p.name, "price": p.price, "supplier": p.supplier,
                      "lead_time_days": p.lead_time_days} for p in db.query(Product).all()],
        "inventory": [{"sku": i.sku, "total_stock": i.total_stock, "reorder_point": i.reorder_point,
                       "status": i.status} for i in db.query(Inventory).all()],
        "purchase_orders": [{"po_id": p.po_id, "sku": p.sku, "qty": p.qty, "status": p.status}
                            for p in db.query(PurchaseOrder).all()],
        "returns": [{"order_id": r.order_id, "sku": r.sku, "status": r.status}
                    for r in db.query(Returns).all()],
        "suppliers": [{"name": s.name, "on_time_rate": s.on_time_rate, "quality_rate": s.quality_rate}
                      for s in db.query(Supplier).all()],
        "shipments": [{"shipment_id": s.shipment_id, "sku": s.sku, "status": s.status}
                      for s in db.query(Shipment).all()],
        "unresolved_alerts": db.query(Alert).filter(Alert.resolved == False).count(),
    }


def _rule_based_answer(question: str, snap: dict) -> str:
    q = question.lower()
    inv = snap["inventory"]
    pos = snap["purchase_orders"]
    sup = snap["suppliers"]
    rets = snap["returns"]

    if "critical" in q or "low stock" in q or "reorder" in q:
        critical = [i for i in inv if i["status"] in ("Critical", "Low")]
        if not critical:
            return "All SKUs are currently Healthy. No reorders needed."
        lines = [f"• {i['sku']}: {i['total_stock']} units ({i['status']})" for i in critical]
        return "SKUs needing attention:\n" + "\n".join(lines)
    if "total" in q and "value" in q:
        prod_by_sku = {p["sku"]: p["price"] for p in snap["products"]}
        total_val = sum(i["total_stock"] * prod_by_sku.get(i["sku"], 0) for i in inv)
        return f"Total inventory value: ${total_val:,.2f} across {len(inv)} SKUs."
    if "pending" in q and "po" in q:
        pending = [p for p in pos if p["status"] == "Draft"]
        if not pending:
            return "No pending (Draft) purchase orders."
        return "Pending POs:\n" + "\n".join(f"• {p['po_id']}: {p['sku']} x{p['qty']}" for p in pending)
    if "supplier" in q and ("worst" in q or "best" in q or "on-time" in q or "performance" in q):
        if not sup:
            return "No suppliers found."
        worst = sorted(sup, key=lambda s: s["on_time_rate"])[0]
        return (f"Worst-performing supplier: {worst['name']} "
                f"(on-time rate: {worst['on_time_rate']*100:.1f}%, quality: {worst['quality_rate']*100:.1f}%).")
    if "return" in q:
        pending = [r for r in rets if r["status"] == "Pending"]
        return f"There are {len(pending)} pending returns out of {len(rets)} total."
    if "alert" in q:
        return f"There are {snap['unresolved_alerts']} unresolved alerts."
    total_units = sum(i["total_stock"] for i in inv)
    return (f"Inventory snapshot: {len(inv)} SKUs, {total_units} total units, "
            f"{len(pos)} POs, {len(rets)} returns, {snap['unresolved_alerts']} unresolved alerts.")


SYSTEM_PROMPT = """You are an inventory operations assistant. You answer the user's
question strictly based on the JSON snapshot of the inventory database provided
to you in the user message. Be concise, professional, and use bullet points when
listing multiple items. If the answer is not in the snapshot, say so explicitly."""


def _llm_answer(question: str, snap: dict) -> Optional[str]:
    api_key = _get_secret("LLM_API_KEY") or _get_secret("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=_get_secret("LLM_BASE_URL") or None)
        model = _get_secret("LLM_MODEL", "gpt-4o-mini")
        user_msg = f"Question: {question}\n\nDatabase snapshot (JSON):\n{json.dumps(snap, default=str)}"
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": user_msg}],
            temperature=0.2, max_tokens=512,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"(LLM call failed, falling back to rules. Error: {e})"


def ask(question: str, db) -> dict:
    snap = _
