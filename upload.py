import streamlit as st
import pandas as pd
from db import insert_dataframe


# -------------------------------
# REQUIRED SCHEMA
# -------------------------------
REQUIRED_COLUMNS = {
    "branch_wise_monthly_target": [
        "month", "branch_name", "series_group",
        "target_value1", "incentive_value1",
        "target_value2", "incentive_value2",
        "target_value3", "incentive_value3",
        "target_value4", "incentive_value4",
        "target_value5", "incentive_value5"
    ],
    "date_branch_wise_target": [
        "date", "branch_name", "series_group",
        "target_value1", "incentive_value1",
        "target_value2", "incentive_value2",
        "target_value3", "incentive_value3",
        "target_value4", "incentive_value4",
        "target_value5", "incentive_value5"
    ],
    "brand_wise_monthly_target": [
        "month", "year", "branch_name", "series",
        "item_code", "item_name", "pack_name"
    ]
}


# -------------------------------
# UPLOAD MODAL
# -------------------------------
def upload_modal(selected_table):

    # -------------------------------
    # HEADER WITH BACK BUTTON
    # -------------------------------
    col1, col2 = st.columns([2, 10])

    with col1:
        if st.button("⬅ Back", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()

    with col2:
        st.markdown("## 📤 Upload CSV")

    # -------------------------------
    # SAMPLE DOWNLOAD
    # -------------------------------
    expected_filename = f"{selected_table}_sample.csv"

    sample_df = pd.DataFrame(columns=REQUIRED_COLUMNS[selected_table])

    st.download_button(
        "📥 Download Sample CSV",
        sample_df.to_csv(index=False),
        file_name=expected_filename
    )

    st.info(f"⚠️ Upload ONLY this file name: `{expected_filename}`")

    # -------------------------------
    # FILE UPLOAD
    # -------------------------------
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded_file is not None:

        if uploaded_file.name != expected_filename:
            st.error("❌ Invalid file! Please upload the downloaded sample file only.")
            return

        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [c.strip().lower() for c in df.columns]

            required_cols = REQUIRED_COLUMNS[selected_table]

            # -------------------------------
            # VALIDATION
            # -------------------------------
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                st.error(f"❌ Missing columns: {missing}")
                return

            # -------------------------------
            # DATE CONVERSION
            # -------------------------------
            if "month" in df.columns:
                df["month"] = pd.to_datetime(df["month"])

            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])

            # -------------------------------
            # PREVIEW
            # -------------------------------
            st.dataframe(df.head())

            # -------------------------------
            # SESSION STATE INIT
            # -------------------------------
            if "upload_done" not in st.session_state:
                st.session_state.upload_done = False

            # -------------------------------
            # CONFIRM UPLOAD
            # -------------------------------
            if not st.session_state.upload_done:
                if st.button("🚀 Confirm Upload"):

                    success, msg = insert_dataframe(selected_table, df)

                    if success:
                        st.session_state.upload_done = True
                        st.session_state.upload_msg = msg
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

            else:
                st.success(f"✅ {st.session_state.upload_msg}")

        except Exception as e:
            st.error(f"❌ Error: {e}")