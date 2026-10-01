import os
import json
from datetime import datetime, timezone

from google import genai
from google.genai import types


# Use the current Gemini model explicitly.
MODEL_NAME = "gemini-3.8-flash"


def build_prompt(receiving_data):
    return f"""
You are a Receiving Manager inspecting a supplier delivery.

Your job is to compare the expected purchase-order information with the
photographs provided by the operator.

IMPORTANT RULES:
1. Evaluate ALL checks in ONE model call.
2. Never invent evidence.
3. If the photograph does not provide enough evidence, return UNCERTAIN.
4. UNCERTAIN is different from PASS.
5. Only return PASS when the visual evidence supports the condition.
6. Only return FAIL when the visual evidence shows the condition is not met.
7. For quantity, count visible units/cartons when possible. If the required
   quantity cannot be established from the photographs, return UNCERTAIN.
8. Give concise evidence for every decision.
9. Do not use outside assumptions about supplier requirements.

EXPECTED RECEIVING INFORMATION:

Unit ID: {receiving_data["unit_id"]}
PO Number: {receiving_data["po_number"]}
PO Line: {receiving_data["po_line"]}

Expected SKU: {receiving_data["sku"]}
Expected Product: {receiving_data["product_title"]}
Expected Colour: {receiving_data["spec_colour"]}
Expected Variant: {receiving_data["spec_variant"]}
Expected Components: {receiving_data["spec_components"]}

Cartons Ordered: {receiving_data["cartons_ordered"]}
Units Per Carton Ordered: {receiving_data["units_per_carton_ordered"]}
Quantity Ordered: {receiving_data["qty_ordered"]}

Inspect these five checks:

1. identity
   Does the photographed product appear to match the expected product/SKU?

2. quantity
   Can the received carton/unit quantity be established from the photos?
   Compare it with the expected quantity.

3. carton_damage
   Look for crushing, water damage, tears or other visible carton damage.

4. unit_damage
   Look for visible physical damage to the actual product.

5. quality
   Check expected colour, variant, components and obvious defects.

Return ONLY valid JSON using exactly this structure:

{{
  "identity": {{
    "verdict": "PASS|FAIL|UNCERTAIN",
    "evidence": "short evidence statement"
  }},
  "quantity": {{
    "verdict": "PASS|FAIL|UNCERTAIN",
    "evidence": "short evidence statement"
  }},
  "carton_damage": {{
    "verdict": "PASS|FAIL|UNCERTAIN",
    "evidence": "short evidence statement"
  }},
  "unit_damage": {{
    "verdict": "PASS|FAIL|UNCERTAIN",
    "evidence": "short evidence statement"
  }},
  "quality": {{
    "verdict": "PASS|FAIL|UNCERTAIN",
    "evidence": "short evidence statement"
  }},
  "overall_verdict": "PASS|FAIL|UNCERTAIN|REVIEW_REQUIRED",
  "summary": "one sentence explaining the overall result"
}}
"""


def inspect_receiving(receiving_data, images):
    """
    Performs exactly ONE Gemini model call for the complete receiving unit.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    # ---------------------------------------------------------
    # API KEY CHECK
    # ---------------------------------------------------------
    if not api_key:
        return {
            "status": "pending",
            "error": "GEMINI_API_KEY is not configured.",
            "identity": {
                "verdict": "UNCERTAIN",
                "evidence": "AI inspection unavailable."
            },
            "quantity": {
                "verdict": "UNCERTAIN",
                "evidence": "AI inspection unavailable."
            },
            "carton_damage": {
                "verdict": "UNCERTAIN",
                "evidence": "AI inspection unavailable."
            },
            "unit_damage": {
                "verdict": "UNCERTAIN",
                "evidence": "AI inspection unavailable."
            },
            "quality": {
                "verdict": "UNCERTAIN",
                "evidence": "AI inspection unavailable."
            },
            "overall_verdict": "REVIEW_REQUIRED",
            "summary": "Inspection is pending because the model service is unavailable."
        }

    try:
        # -----------------------------------------------------
        # CREATE GEMINI CLIENT
        # -----------------------------------------------------
        client = genai.Client(api_key=api_key)

        # -----------------------------------------------------
        # BUILD PROMPT
        # -----------------------------------------------------
        prompt = build_prompt(receiving_data)

        # -----------------------------------------------------
        # ONE GEMINI MODEL CALL
        # -----------------------------------------------------
        import time

response = None

for attempt in range(4):
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[prompt] + images,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=1500,
            ),
        )
        break

    except Exception as exc:
        error_text = str(exc)

        if "503" not in error_text and "UNAVAILABLE" not in error_text:
            raise

        if attempt == 3:
            raise

        time.sleep(2 ** attempt)

        # -----------------------------------------------------
        # READ MODEL RESPONSE
        # -----------------------------------------------------
        response_text = response.text

        if not response_text:
            raise ValueError("Gemini returned an empty response.")

        # -----------------------------------------------------
        # PARSE JSON
        # -----------------------------------------------------
        result = json.loads(response_text)

        # -----------------------------------------------------
        # ADD SYSTEM METADATA
        # -----------------------------------------------------
        result["status"] = "completed"
        result["model"] = MODEL_NAME
        result["inspected_at"] = datetime.now(timezone.utc).isoformat()

        return result

    except Exception as exc:
        # -----------------------------------------------------
        # FAIL-OPEN:
        # Preserve the receiving capture and request review.
        # -----------------------------------------------------
        return {
            "status": "pending",
            "error": str(exc),

            "identity": {
                "verdict": "UNCERTAIN",
                "evidence": "Inspection could not be completed."
            },

            "quantity": {
                "verdict": "UNCERTAIN",
                "evidence": "Inspection could not be completed."
            },

            "carton_damage": {
                "verdict": "UNCERTAIN",
                "evidence": "Inspection could not be completed."
            },

            "unit_damage": {
                "verdict": "UNCERTAIN",
                "evidence": "Inspection could not be completed."
            },

            "quality": {
                "verdict": "UNCERTAIN",
                "evidence": "Inspection could not be completed."
            },

            "overall_verdict": "REVIEW_REQUIRED",

            "summary": (
                "The receiving capture was preserved and requires human review."
            )
        }
