import httpx

# Example 1: USER EXACT COMPLIANT PAYLOAD (Testing the exact user scenario)
user_exact_payload = {
    "data": {
        "product_name": "Nutri-Crunch Oat Cookies",
        "common_or_generic_name": "Baked Oat Cookies",
        "brand": "Nutri-Crunch",
        "mrp": {
            "value": 55.0,
            "inclusive_of_taxes": True
        },
        "net_quantity": {
            "value": 200.0,
            "unit": "g"
        },
        "dates": {
            "packing_date": "08/2026"
        },
        "manufacturer": {
            "name": "Organic Foods India Ltd",
            "address": "Plot 42, KIADB Area, Bengaluru",
            "pincode": "560066"
        },
        "consumer_care": {
            "phone": "1800-200-1122",
            "email": "care@nutricrunch.com"
        },
        "unit_sale_price": {
            "value": 0.50,
            "unit": "100 g"
        },
        "country_of_origin": "India"
    }
}

resp_c = httpx.post("http://127.0.0.1:8000/api/compliance/check", json=user_exact_payload, timeout=10.0)
print("=== TEST 1: USER'S EXACT COMPLIANT PAYLOAD ===")
print("Status Code:", resp_c.status_code)
data_c = resp_c.json()
print("Compliance Status:", data_c.get("compliance_status"))
print("Summary:", data_c.get("summary"))
print(f"Rules Passed: {data_c.get('rules_passed')} / {data_c.get('rules_checked')}")
print("Violations Count:", len(data_c.get("violations", [])))
print("Checks:")
for c in data_c.get("checks", []):
    if c["rule_id"] in ["LMR-06-1-D", "LMR-06-1-E", "LMR-06-11"]:
        print(f"  * {c['rule_id']} ({c['field_checked']}): status={c['status']}, extracted_value={c['extracted_value']}")

# Example 2: NON-COMPLIANT PRODUCT (Missing MRP tax clause, non-standard unit, missing consumer care)
non_compliant_payload = {
    "data": {
        "product_name": "Mystery Brand Snack",
        "common_or_generic_name": "Snack Mix",
        "mrp": {
            "raw_text": "Price: Rs. 100 plus taxes",
            "value": 100.0,
            "currency": "INR",
            "includes_taxes": False
        },
        "net_quantity": {
            "raw_text": "Net Wt: 500 gm",
            "value": 500.0,
            "unit": "gm"
        },
        "dates": {
            "raw_text": "Mfg: 01/2026",
            "manufacturing_date": "01/2026"
        },
        "manufacturer": {
            "name": "Unknown Food Works",
            "pincode": None,
            "address": None
        },
        "consumer_care": {},
        "country_of_origin": None,
        "extraction_method": "regex_heuristic",
        "extraction_confidence": 0.85
    }
}

resp_nc = httpx.post("http://127.0.0.1:8000/api/compliance/check", json=non_compliant_payload, timeout=10.0)
print("\n=== TEST 2: NON-COMPLIANT EXAMPLE ===")
print("Status Code:", resp_nc.status_code)
data_nc = resp_nc.json()
print("Compliance Status:", data_nc.get("compliance_status"))
print("Summary:", data_nc.get("summary"))
print("Rules Failed:", data_nc.get("rules_failed"))
print("Violations:")
for v in data_nc.get("violations", []):
    print(f"  * [{v['rule_id']}] ({v['legal_reference']}) on field '{v['field']}': {v['message']}")
print("Warnings:")
for w in data_nc.get("warnings", []):
    print(f"  ! [{w['rule_id']}] ({w['legal_reference']}) on field '{w['field']}': {w['message']}")
