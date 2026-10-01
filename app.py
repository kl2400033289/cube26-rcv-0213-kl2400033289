import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

from src.receiving_agent import inspect_receiving


st.set_page_config(
    page_title="Receiving Manager",
    page_icon="📦",
    layout="wide",
)


# ---------------------------------------------------------
# Styling
# ---------------------------------------------------------

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 700;
        margin-bottom: 0;
    }

    .subtitle {
        color: #777;
        margin-bottom: 2rem;
    }

    .result-card {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #ddd;
        margin-bottom: 0.7rem;
    }

    .pass {
        color: #16803c;
        font-weight: 700;
    }

    .fail {
        color: #c62828;
        font-weight: 700;
    }

    .uncertain {
        color: #b26a00;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def save_evidence(record):
    Path("data").mkdir(exist_ok=True)

    file_path = Path("data/receiving_records.jsonl")

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def verdict_icon(verdict):
    if verdict == "PASS":
        return "✓"
    if verdict == "FAIL":
        return "✕"
    return "?"


def verdict_class(verdict):
    return verdict.lower()


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.markdown(
    '<div class="main-title">📦 Receiving Manager</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">AI-powered supplier receiving inspection with evidence-backed decisions</div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

with st.sidebar:
    st.header("Receiving Session")

    org_id = st.selectbox(
        "Organisation",
        [
            "org_demo_alpha",
            "org_demo_bravo",
        ],
    )

    operator_id = st.text_input(
        "Operator ID",
        value="operator_demo",
    )

    st.divider()

    st.caption(
        "Tenant isolation is enforced through the organisation context. "
        "Records must never cross organisations."
    )


# ---------------------------------------------------------
# Expected information
# ---------------------------------------------------------

st.subheader("1. Purchase Order / Expected Item")

col1, col2, col3 = st.columns(3)

with col1:
    unit_id = st.text_input("Unit ID", "UNIT-0007")
    po_number = st.text_input("PO Number", "PO-7001")
    po_line = st.number_input("PO Line", min_value=1, value=4)

with col2:
    sku = st.text_input("SKU", "SKU-CABLE-USBC")
    product_title = st.text_input("Product", "USB-C Cable")
    spec_colour = st.text_input("Expected Colour", "white")

with col3:
    spec_variant = st.text_input("Expected Variant", "2m")
    spec_components = st.text_input("Expected Components", "cable")
    qty_ordered = st.number_input("Quantity Ordered", min_value=1, value=24)


col1, col2, col3 = st.columns(3)

with col1:
    cartons_ordered = st.number_input(
        "Cartons Ordered",
        min_value=1,
        value=2,
    )

with col2:
    units_per_carton_ordered = st.number_input(
        "Units / Carton",
        min_value=1,
        value=12,
    )

with col3:
    st.metric(
        "Expected Total",
        qty_ordered,
    )


receiving_data = {
    "unit_id": unit_id,
    "po_number": po_number,
    "po_line": po_line,
    "sku": sku,
    "product_title": product_title,
    "spec_colour": spec_colour,
    "spec_variant": spec_variant,
    "spec_components": spec_components,
    "cartons_ordered": cartons_ordered,
    "units_per_carton_ordered": units_per_carton_ordered,
    "qty_ordered": qty_ordered,
}


# ---------------------------------------------------------
# Photos
# ---------------------------------------------------------

st.subheader("2. Receiving Evidence")

uploaded_files = st.file_uploader(
    "Upload receiving photographs",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    help="Recommended: pallet/carton photo, carton close-up, and product/unit photo.",
)


images = []

if uploaded_files:

    preview_cols = st.columns(min(len(uploaded_files), 3))

    for index, uploaded_file in enumerate(uploaded_files):

        image = Image.open(uploaded_file).convert("RGB")
        images.append(image)

        with preview_cols[index % 3]:
            st.image(
                image,
                caption=uploaded_file.name,
                use_container_width=True,
            )

else:
    st.info(
        "Upload at least one clear receiving photograph. "
        "Three views are recommended for the demo."
    )


# ---------------------------------------------------------
# Inspection
# ---------------------------------------------------------

st.subheader("3. Run Receiving Inspection")

run_inspection = st.button(
    "🔍 Run Receiving Inspection",
    type="primary",
    use_container_width=True,
)


if run_inspection:

    if not images:
        st.error("Please upload at least one receiving photograph.")
        st.stop()

    with st.spinner("Inspecting the complete receiving unit..."):

        result = inspect_receiving(
            receiving_data,
            images,
        )

    # Preserve capture metadata regardless of model success.
    record = {
        "record_id": f"RCV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "unit_id": unit_id,
        "org_id": org_id,
        "operator_id": operator_id,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "expected": receiving_data,
        "result": result,
        "photo_count": len(images),
    }

    save_evidence(record)

    st.session_state["last_result"] = result
    st.session_state["last_record"] = record


# ---------------------------------------------------------
# Results
# ---------------------------------------------------------

if "last_result" in st.session_state:

    result = st.session_state["last_result"]

    st.divider()

    st.subheader("4. Inspection Result")

    checks = [
        ("Identity", "identity"),
        ("Quantity", "quantity"),
        ("Carton Damage", "carton_damage"),
        ("Unit Damage", "unit_damage"),
        ("Quality", "quality"),
    ]

    for display_name, key in checks:

        check = result.get(
            key,
            {
                "verdict": "UNCERTAIN",
                "evidence": "No result available.",
            },
        )

        verdict = check.get("verdict", "UNCERTAIN")
        evidence = check.get("evidence", "")

        icon = verdict_icon(verdict)
        css_class = verdict_class(verdict)

        st.markdown(
            f"""
            <div class="result-card">
                <strong>{display_name}</strong>
                <br>
                <span class="{css_class}">
                    {icon} {verdict}
                </span>
                <br>
                <small>{evidence}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )

    overall = result.get(
        "overall_verdict",
        "REVIEW_REQUIRED",
    )

    if overall == "PASS":
        st.success("RECEIVING VERDICT: PASS")

    elif overall == "FAIL":
        st.error("RECEIVING VERDICT: FAIL")

    else:
        st.warning(
            f"RECEIVING VERDICT: {overall}"
        )

    st.info(
        result.get(
            "summary",
            "Review the evidence before accepting the delivery.",
        )
    )

    # -----------------------------------------------------
    # Evidence record
    # -----------------------------------------------------

    st.subheader("5. Evidence Record")

    record = st.session_state["last_record"]

    st.json(record)

    st.caption(
        "The original model verdict is retained as evidence. "
        "Operator overrides should create a new record rather than silently replacing it."
    )


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.divider()

st.caption(
    "CUBE Buildathon · 01 Receiving Manager · Round 2"
)
