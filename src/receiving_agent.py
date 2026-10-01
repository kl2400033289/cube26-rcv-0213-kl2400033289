import os
import json
import time
from datetime import datetime, timezone

from google import genai
from google.genai import types


# ---------------------------------------------------------
# MODEL CONFIGURATION
# ---------------------------------------------------------
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.7-flash")


def build_prompt(receiving_data):
    return f"""
You are a Receiving Manager inspecting a supplier delivery.

Your job is to compare the expected purchase-order information with the
photographs provided by the operator.

IMPORTANT RULES:

1. Evaluate ALL five checks in ONE model call.
2. Never invent evidence.
3. If the photograph does not provide enough evidence, return UNCERTAIN.
4. UNCERTAIN is different from PASS.
5. Only return PASS when the visual evidence supports the condition.
6. Only return FAIL when the visual evidence shows the condition is not met.
7. For quantity, count visible units/cartons when possible.
8. If the required quantity cannot be established from the photographs,
   return UNCERTAIN.
9. Give concise evidence for every decision.
10. Do not use outside assumptions about supplier requirements.
11. Do not infer hidden information that is not visible in the photographs.

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
Look for crushing, water damage, tears, or other visible carton damage.

4. unit_damage
Look for visible physical damage to the actual product.

5. quality
Check expected colour, variant, components, and obvious defects.

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


def pending_result(error_message):
    """
    Fail-open result.
    The receiving capture is preserved even when the model is unavailable.
    """

    return {
        "status": "pending",
        "error": error_message,

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


def call_model(client, model_name, prompt, images):
    """
    Makes ONE Gemini call for the complete receiving inspection.
    """

    response = client.models.generate_content(
        model=model_name,
        contents=[prompt] + images,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1500,
        ),
    )

    if response is None:
        raise ValueError("Gemini returned no response.")

    response_text = response.text

    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    return json.loads(response_text)


def inspect_receiving(receiving_data, images):
    """
    Performs one complete receiving inspection.

    Primary model:
        GEMINI_MODEL

    Fallback model:
        GEMINI_FALLBACK_MODEL

    The system fails open if both models are unavailable.
    """

    api_key = os.getenv("GEMINI_API_KEY")

    # ---------------------------------------------------------
    # API KEY CHECK
    # ---------------------------------------------------------
    if not api_key:
        return pending_result(
            "GEMINI_API_KEY is not configured."
        )

    try:
        client = genai.Client(api_key=api_key)
        prompt = build_prompt(receiving_data)

        models_to_try = [
            MODEL_NAME,
            FALLBACK_MODEL
        ]

        last_error = None

        # -----------------------------------------------------
        # TRY PRIMARY THEN FALLBACK MODEL
        # -----------------------------------------------------
        for model_index, model_name in enumerate(models_to_try):

            # Avoid calling the same model twice if both secrets
            # contain the same value.
            if (
                model_index == 1
                and FALLBACK_MODEL == MODEL_NAME
            ):
                continue

            # -------------------------------------------------
            # RETRY TEMPORARY SERVER ERRORS
            # -------------------------------------------------
            for attempt in range(3):

                try:

                    result = call_model(
                        client,
                        model_name,
                        prompt,
                        images
                    )

                    # -----------------------------------------
                    # SUCCESS
                    # -----------------------------------------
                    result["status"] = "completed"
                    result["model"] = model_name
                    result["inspected_at"] = (
                        datetime.now(timezone.utc).isoformat()
                    )

                    return result

                except Exception as exc:

                    error_text = str(exc)
                    last_error = error_text

                    temporary_error = (
                        "500" in error_text
                        or "503" in error_text
                        or "INTERNAL" in error_text
                        or "UNAVAILABLE" in error_text
                        or "timeout" in error_text.lower()
                    )

                    # -----------------------------------------
                    # Non-temporary error:
                    # immediately move to fallback model.
                    # -----------------------------------------
                    if not temporary_error:
                        break

                    # -----------------------------------------
                    # Retry with exponential backoff.
                    # 1 sec → 2 sec → 4 sec
                    # -----------------------------------------
                    if attempt < 2:
                        time.sleep(2 ** attempt)

            # If primary failed, continue to fallback model.

        # -----------------------------------------------------
        # BOTH MODELS FAILED
        # -----------------------------------------------------
        return pending_result(
            last_error or "All Gemini inspection attempts failed."
        )

    except Exception as exc:

        # -----------------------------------------------------
        # FINAL FAIL-OPEN
        # -----------------------------------------------------
        return pending_result(str(exc))
