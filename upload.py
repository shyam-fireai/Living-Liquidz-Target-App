import streamlit as st
import pandas as pd
import io
from db import TABLE_SCHEMAS, insert_dataframe, get_client, format_column, remove_zero_columns, apply_currency_format, log_audit_action
from style_utils import inject_minimalist_theme, render_header
import logging

logger = logging.getLogger(__name__)

# -------------------------------
# REQUIRED SCHEMA (REPLACED BY db.TABLE_SCHEMAS)
# -------------------------------
REQUIRED_COLUMNS = TABLE_SCHEMAS


# -------------------------------
# UPLOAD SCREEN
# -------------------------------
def upload_screen(selected_table):
    
    # -------------------------------
    # UI THEME & HEADER
    # -------------------------------
    inject_minimalist_theme()
    display_name = selected_table.replace("_", " ").title()
    col_edit, col_upload = render_header(title=f"Uploading: {display_name}", hide_upload=True)
    
    with col_edit:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()
            
    st.divider()

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

    if selected_table == "date_branch_wise_target":
        st.info(f"""
-  **Upload ONLY this file name:** `{expected_filename}`
-  **Format Hint:** The 'date' column must use the standard format (e.g., **2026-04-17**).
""")
    else:
        st.info(f"""
-  **Upload ONLY this file name:** `{expected_filename}`
-  **Format Hint:** The 'month' column must always be the **1st day** of the month (e.g., **2026-03-01**).
""")

    # -------------------------------
    # FILE UPLOAD
    # -------------------------------
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"], key=f"uploader_{selected_table}")

    if uploaded_file is not None:
        logger.info(f"File uploaded: {uploaded_file.name} for table: {selected_table}")

        if uploaded_file.name != expected_filename:
            logger.warning(f"File Rejected: Name mismatch. Expected {expected_filename}, got {uploaded_file.name}")
            st.error("❌ Invalid file! Please upload the downloaded sample file only.")
            return

        try:
            df = pd.read_csv(uploaded_file)
            df.columns = [c.strip().lower() for c in df.columns]

            required_cols = REQUIRED_COLUMNS[selected_table]

            logger.info("Verifying column schema...")
            missing = [col for col in required_cols if col not in df.columns]
            if missing:
                logger.error(f"Validation Failed: Missing columns {missing}")
                st.error(f"❌ Missing columns: {missing}")
                return
            logger.info("Column validation successful.")

            # -------------------------------
            # DATE CONVERSION
            # -------------------------------
            if "month" in df.columns:
                try:
                    df["month"] = pd.to_datetime(df["month"])
                except Exception:
                    st.error("❌ **Invalid Month Format:** Some dates in the 'month' column are not recognized. Please use the format **YYYY-MM-DD** (e.g., **2026-03-01**).")
                    return
                
                # Strict Validation: Must be 1st of the month
                invalid_rows = df[df["month"].dt.day != 1]
                if not invalid_rows.empty:
                    # Row numbers are 2-indexed (+2) because header is Row 1
                    err_row_indices = [i + 2 for i in invalid_rows.index.tolist()]
                    st.error(f"❌ **Data Format Error:** Invalid dates found in 'month' column at **Row(s): {err_row_indices}**")
                    st.warning("All records must use the 1st day of the month (e.g. 2026-03-01). Entire data must be fixed before upload.")
                    return

            if "date" in df.columns:
                try:
                    df["date"] = pd.to_datetime(df["date"])
                except Exception:
                    st.error("❌ **Invalid Date Format:** Some dates in the 'date' column are not recognized. Please use the format **YYYY-MM-DD** (e.g., **2026-04-17**).")
                    return

            # -------------------------------
            # PREVIEW (Hide zero columns, format currency, and rename headers for display)
            # -------------------------------
            preview_df = remove_zero_columns(df).head().copy()
            
            # Show only the date part in preview (remove 00:00:00)
            for col in ["month", "date"]:
                if col in preview_df.columns:
                    preview_df[col] = pd.to_datetime(preview_df[col]).dt.date

            # Apply Indian Rupee formatting for currency tables
            if selected_table in ["branch_wise_monthly_target", "date_branch_wise_target"]:
                preview_df = apply_currency_format(preview_df)
                
            preview_df = preview_df.rename(columns=format_column)
            st.dataframe(preview_df, width="stretch")

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
                    logger.info(f"Initiating database insert for {len(df)} records into {selected_table}...")
                    success, msg = insert_dataframe(selected_table, df)

                    if success:
                        logger.info(f"Upload Complete: {msg}")
                        log_audit_action(
                            action_type="UPLOAD",
                            target_table=selected_table,
                            record_count=len(df),
                            metadata={"file_name": uploaded_file.name}
                        )
                        st.session_state.upload_done = True
                        st.session_state.upload_msg = msg
                        # Clear cache to show new data immediately
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        logger.error(f"Upload Failed: {msg}")
                        log_audit_action(action_type="ERROR", target_table=selected_table, error_message=f"DB Insert Failed: {msg}")
                        st.error(f"❌ {msg}")

            else:
                st.success(f"✅ {st.session_state.upload_msg}")

        except Exception as e:
            st.error(f"❌ Error: {e}")