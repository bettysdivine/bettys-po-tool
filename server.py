from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import anthropic
import requests
import base64
import os
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bettys-divine-secret-2026")
CORS(app, supports_credentials=True)

# Configuration - set these as environment variables in Railway
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "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")
SHOPIFY_STORE_URL = os.environ.get("SHOPIFY_STORE_URL", "bettys-divine.myshopify.com")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "Bettys1300!")

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
@app.route("/")
def index():
    return send_from_directory(".", "index.html")
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    if data.get("password") == APP_PASSWORD:
        session["authenticated"] = True
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Wrong password"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/parse-invoice", methods=["POST"])
def parse_invoice():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    file_bytes = file.read()
    file_b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    # Determine media type
    filename = file.filename.lower()
    if filename.endswith(".pdf"):
        media_type = "application/pdf"
    elif filename.endswith(".png"):
        media_type = "image/png"
    elif filename.endswith(".jpg") or filename.endswith(".jpeg"):
        media_type = "image/jpeg"
    else:
        media_type = "application/pdf"

    prompt = """You are an invoice parser for a retail boutique. Extract all information from this invoice and return ONLY valid JSON with no markdown, no explanation, just the raw JSON object.

Return this exact structure:
{
  "vendor": "vendor name",
  "invoice_number": "invoice number or order number",
  "invoice_date": "YYYY-MM-DD or empty string",
  "due_date": "YYYY-MM-DD or empty string",
  "payment_terms": "NET 30 or PREPAID or empty string",
  "already_paid": true or false,
  "subtotal": 0.00,
  "shipping": 0.00,
  "total": 0.00,
  "line_items": [
    {
      "sku": "SKU or style number",
      "description": "full product description",
      "size": "size or size range or empty string",
      "color": "color or empty string",
      "quantity": 1,
      "unit_cost": 0.00,
      "total_cost": 0.00
    }
  ]
}

Rules:
- already_paid is true if the invoice shows a credit card charge, payment confirmation, or says PAID
- Extract every line item, even if there are many
- Use empty string for missing fields, never null
- Return ONLY the JSON, nothing else"""

    if media_type == "application/pdf":
        content = [
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": file_b64
                }
            },
            {"type": "text", "text": prompt}
        ]
    else:
        content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": file_b64
                }
            },
            {"type": "text", "text": prompt}
        ]

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": content}]
    )

    raw = message.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)
    return jsonify(parsed)

@app.route("/api/push-to-shopify", methods=["POST"])
def push_to_shopify():
    if not session.get("authenticated"):
        return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    invoice = data.get("invoice")

    if not invoice:
        return jsonify({"error": "No invoice data"}), 400

    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

    # First, find or create supplier
    supplier_name = invoice.get("vendor", "Unknown Vendor")
    
    # Search for existing supplier
    supplier_response = requests.get(
        f"https://{SHOPIFY_STORE_URL}/api/2024-01/suppliers.json",
        headers=headers,
        params={"name": supplier_name}
    )

    supplier_id = None
    if supplier_response.status_code == 200:
        suppliers = supplier_response.json().get("suppliers", [])
        if suppliers:
            supplier_id = suppliers[0]["id"]

    # Build line items for PO
    line_items = []
    for item in invoice.get("line_items", []):
        line_item = {
            "quantity": item.get("quantity", 1),
            "unit_cost": str(item.get("unit_cost", 0))
        }
        # Try to match by SKU if available
        sku = item.get("sku", "")
        if sku:
            # Search for product variant by SKU
            variant_response = requests.get(
                f"https://{SHOPIFY_STORE_URL}/api/2024-01/variants.json",
                headers=headers,
                params={"sku": sku}
            )
            if variant_response.status_code == 200:
                variants = variant_response.json().get("variants", [])
                if variants:
                    line_item["variant_id"] = variants[0]["id"]

        if "variant_id" in line_item:
            line_items.append(line_item)
        else:
            # Add as a note item if we can't match SKU
            line_items.append({
                "quantity": item.get("quantity", 1),
                "unit_cost": str(item.get("unit_cost", 0)),
                "custom_item": {
                    "title": item.get("description", "Unknown Item"),
                    "sku": item.get("sku", ""),
                    "unit_cost": str(item.get("unit_cost", 0)),
                    "quantity": item.get("quantity", 1)
                }
            })

    # Build PO payload
    po_payload = {
        "purchase_order": {
            "note": f"Invoice #{invoice.get('invoice_number', '')} | Created by Betty's PO Tool",
            "line_items": []
        }
    }

    if supplier_id:
        po_payload["purchase_order"]["supplier_id"] = supplier_id

    # Add shipping cost as a note since Shopify PO API varies
    if invoice.get("shipping", 0) > 0:
        po_payload["purchase_order"]["note"] += f" | Freight: ${invoice.get('shipping', 0):.2f}"

    if invoice.get("due_date"):
        po_payload["purchase_order"]["note"] += f" | Due: {invoice.get('due_date')}"

    if invoice.get("already_paid"):
        po_payload["purchase_order"]["note"] += " | PAID"

    # For custom line items not matched to SKUs, add them as notes
    custom_items_text = []
    matched_items = []
    
    for i, item in enumerate(invoice.get("line_items", [])):
        li = line_items[i]
        if "variant_id" in li:
            matched_items.append(li)
        else:
            sku = item.get("sku", "N/A")
            desc = item.get("description", "")
            qty = item.get("quantity", 1)
            cost = item.get("unit_cost", 0)
            size = item.get("size", "")
            color = item.get("color", "")
            custom_items_text.append(f"{sku} | {desc} | {color} | {size} | Qty:{qty} | ${cost:.2f}")

    if custom_items_text:
        po_payload["purchase_order"]["note"] += "\n\nLINE ITEMS:\n" + "\n".join(custom_items_text)

    po_payload["purchase_order"]["line_items"] = matched_items

   response = requests.post(
        f"https://{SHOPIFY_STORE_URL}/api/2024-10/purchase_orders.json",
        headers={
            "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        json=po_payload
    )

    if response.status_code in [200, 201]:
        return jsonify({"success": True, "message": "Purchase order created in Shopify!"})
    else:
        return jsonify({"success": False, "error": f"Shopify API error {response.status_code}", "details": response.text}), 400

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "store": SHOPIFY_STORE_URL})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
