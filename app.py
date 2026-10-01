import json
import os
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from PIL import Image

from src.database import init_db, save_receiving_record, get_receiving_records
from src.receiving_agent import inspect_receiving


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Receiving Manager",
    page_icon="📦",
    layout="wide"
)


# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================

if "last_record" not in st.session_state:
    st.session_state["last_record"] = None

if "last_images" not in st.session_state:
    st.session_state["last_images"] = []

if "inspection_done" not in st.session_state:
    st.session_state["inspection_done"] = False


# ============================================================
# HEADER
# ============================================================

st.title("📦 Receiving Manager")

st.write(
    "AI-assisted receiving inspection using purchase-order information "
    "and photographic evidence."
)

st.divider()


# ============================================================
# 1. EXPECTED RECEIVING INFORMATION
# ============================================================

st.header("1. Expected Receiving Information")

col1, col2, col3 = st.columns(3)

with col1:
    unit_id = st.text_input(
        "Unit ID",
        value="UNIT-0007"
    )

    org_id = st.text_input(
        "Organization ID",
        value="org_demo_alpha"
    )

    operator_id = st.text_input(
        "Operator ID",
        value="operator_demo"
    )

    po_number = st.text_input(
        "PO Number",
        value="PO-7001"
    )

with col2:
    po_line = st.number_input(
        "PO Line",
        min_value=1,
        value=4,
        step=1
    )

    sku = st.text_input(
        "SKU",
        value="SKU-CABLE-USBC"
    )

    product_title = st.text_input(
        "Product",
        value="USB-C Cable"
    )

    spec_colour = st.text_input(
        "Expected Colour",
        value="white"
    )

with col3:
    spec_variant = st.text_input(
        "Expected Variant",
        value="2m"
    )

    spec_components = st.text_input(
        "Expected Components",
        value="cable"
    )

    cartons_ordered = st.number_input(
        "Cartons Ordered",
        min_value=0,
        value=2,
        step=1
    )

    units_per_carton_ordered = st.number_input(
        "Units Per Carton",
        min_value=0,
        value=12,
        step=1
    )

    qty_ordered = st.number_input(
        "Quantity Ordered",
        min_value=0,
        value=24,
        step=1
    )


# ============================================================
# BUILD RECEIVING DATA
# ============================================================

receiving_data = {
    "unit_id": unit_id,
    "org_id": org_id,
    "operator_id": operator_id,

    "po_number": po_number,
    "po_line": int(po_line),

    "sku": sku,
    "product_title": product_title,

    "spec_colour": spec_colour,
    "spec_variant": spec_variant,
    "spec_components": spec_components,

    "cartons_ordered": int(cartons_ordered),
    "units_per_carton_ordered": int(units_per_carton_ordered),
    "qty_ordered": int(qty_ordered)
}


# ============================================================
# 2. PHOTO UPLOAD
# ============================================================

st.divider()

st.header("2. Receiving Evidence")

uploaded_files = st.file_uploader(
    "Upload receiving photographs",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True
)


images = []

if uploaded_files:

    st.write(f"📸 {len(uploaded_files)} photograph(s) uploaded.")

    preview_columns = st.columns(min(len(uploaded_files), 4))

    for index, uploaded_file in enumerate(uploaded_files):

        try:
            image = Image.open(uploaded_file).convert("RGB")

            images.append(image)

            with preview_columns[index % len(preview_columns)]:
                st.image(
                    image,
                    caption=uploaded_file.name,
                    use_container_width=True
                )

        except Exception as exc:
            st.error(
                f"Could not read {uploaded_file.name}: {exc}"
            )


# ============================================================
# 3. RUN INSPECTION
# ============================================================

st.divider()

st.header("3. AI Inspection")

inspect_button = st.button(
    "🔍 Run Receiving Inspection",
    type="primary",
    use_container_width=True
)


if inspect_button:

    if not images:
        st.warning(
            "Please upload at least one receiving photograph before "
            "running the inspection."
        )

    else:

        with st.spinner(
            "Inspecting receiving evidence with Gemini..."
        ):

            try:

                # ------------------------------------------------
                # CALL GEMINI
                # ------------------------------------------------

                result = inspect_receiving(
                    receiving_data,
                    images
                )

                # ------------------------------------------------
                # CREATE EVIDENCE RECORD
                # ------------------------------------------------

                record_id = (
                    "RCV-"
                    + datetime.now(timezone.utc)
                    .strftime("%Y%m%d%H%M%S")
                )

                captured_at = (
                    datetime.now(timezone.utc)
                    .isoformat()
                )

                record = {
                    "record_id": record_id,

                    "unit_id": unit_id,
                    "org_id": org_id,
                    "operator_id": operator_id,

                    "captured_at": captured_at,

                    "expected": {
                        "unit_id": unit_id,
                        "po_number": po_number,
                        "po_line": int(po_line),

                        "sku": sku,
                        "product_title": product_title,

                        "spec_colour": spec_colour,
                        "spec_variant": spec_variant,
                        "spec_components": spec_components,

                        "cartons_ordered": int(
                            cartons_ordered
                        ),

                        "units_per_carton_ordered": int(
                            units_per_carton_ordered
                        ),

                        "qty_ordered": int(
                            qty_ordered
                        )
                    },

                    "result": result,

                    "photo_count": len(images)
                }

                # ------------------------------------------------
                # SAVE TO SESSION STATE
                # ------------------------------------------------

                st.session_state["last_record"] = record
                st.session_state["last_images"] = images
                st.session_state["inspection_done"] = True

                # ------------------------------------------------
                # SAVE TO DATABASE
                # ------------------------------------------------

                save_receiving_record(record)

                st.success(
                    "Inspection completed and evidence record saved."
                )

            except Exception as exc:

                st.error(
                    f"Inspection failed unexpectedly: {exc}"
                )


# ============================================================
# 4. INSPECTION RESULT
# ============================================================

if st.session_state["inspection_done"]:

    record = st.session_state.get("last_record")

    if record:

        result = record.get("result", {})

        st.divider()

        st.header("4. Inspection Result")

        # --------------------------------------------------------
        # HELPER FUNCTION
        # --------------------------------------------------------

        def show_verdict(title, data):

            if not data:
                st.warning(
                    f"{title}: No result available."
                )
                return

            verdict = data.get(
                "verdict",
                "UNCERTAIN"
            )

            evidence = data.get(
                "evidence",
                "No evidence provided."
            )

            if verdict == "PASS":

                st.success(
                    f"✓ {title}\n\n"
                    f"**PASS**\n\n"
                    f"{evidence}"
                )

            elif verdict == "FAIL":

                st.error(
                    f"✕ {title}\n\n"
                    f"**FAIL**\n\n"
                    f"{evidence}"
                )

            else:

                st.warning(
                    f"? {title}\n\n"
                    f"**UNCERTAIN**\n\n"
                    f"{evidence}"
                )

        # --------------------------------------------------------
        # FIVE INSPECTION CHECKS
        # --------------------------------------------------------

        show_verdict(
            "Identity",
            result.get("identity")
        )

        show_verdict(
            "Quantity",
            result.get("quantity")
        )

        show_verdict(
            "Carton Damage",
            result.get("carton_damage")
        )

        show_verdict(
            "Unit Damage",
            result.get("unit_damage")
        )

        show_verdict(
            "Quality",
            result.get("quality")
        )

        # --------------------------------------------------------
        # OVERALL RESULT
        # --------------------------------------------------------

        overall_verdict = result.get(
            "overall_verdict",
            "REVIEW_REQUIRED"
        )

        summary = result.get(
            "summary",
            "No summary available."
        )

        st.subheader("Receiving Verdict")

        if overall_verdict == "PASS":

            st.success(
                f"✓ RECEIVING VERDICT: PASS\n\n"
                f"{summary}"
            )

        elif overall_verdict == "FAIL":

            st.error(
                f"✕ RECEIVING VERDICT: FAIL\n\n"
                f"{summary}"
            )

        else:

            st.warning(
                f"? RECEIVING VERDICT: {overall_verdict}\n\n"
                f"{summary}"
            )


# ============================================================
# 5. EVIDENCE RECORD
# ============================================================

if st.session_state.get("last_record") is not None:

    record = st.session_state["last_record"]

    st.divider()

    st.header("5. Evidence Record")

    with st.expander(
        "View complete evidence JSON",
        expanded=False
    ):

        st.json(record)

    # --------------------------------------------------------
    # RECORD INFORMATION
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Record ID",
            record.get("record_id", "N/A")
        )

    with col2:

        st.metric(
            "Unit ID",
            record.get("unit_id", "N/A")
        )

    with col3:

        result = record.get("result", {})

        st.metric(
            "Verdict",
            result.get(
                "overall_verdict",
                "REVIEW_REQUIRED"
            )
        )

    st.caption(
        f"Captured at: "
        f"{record.get('captured_at', 'N/A')}"
    )


# ============================================================
# 6. RECEIVING HISTORY
# ============================================================

st.divider()

st.header("6. Receiving History")

try:

    records = get_receiving_records()

    if records:

        history = []

        for record in records:

            history.append({
                "Record ID": record.get(
                    "record_id"
                ),

                "Unit ID": record.get(
                    "unit_id"
                ),

                "PO Number": record.get(
                    "po_number"
                ),

                "PO Line": record.get(
                    "po_line"
                ),

                "SKU": record.get(
                    "sku"
                ),

                "Product": record.get(
                    "product_title"
                ),

                "Verdict": record.get(
                    "overall_verdict"
                ),

                "Captured At": record.get(
                    "captured_at"
                )
            })

        history_df = pd.DataFrame(history)

        st.dataframe(
            history_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No receiving records yet."
        )

except Exception as exc:

    st.error(
        f"Could not load receiving history: {exc}"
    )


# ============================================================
# 7. SYSTEM INFORMATION
# ============================================================

st.divider()

st.header("7. System Information")

col1, col2, col3 = st.columns(3)

with col1:

    st.write(
        "**AI Model**"
    )

    st.code(
        os.getenv(
            "GEMINI_MODEL",
            "gemini-3.8-flash"
        )
    )

with col2:

    st.write(
        "**Inspection Mode**"
    )

    st.write(
        "Single model call with temporary-error retry"
    )

with col3:

    st.write(
        "**Evidence Policy**"
    )

    st.write(
        "Original AI result is preserved"
    )
