import streamlit as st
import pandas as pd
from datetime import datetime
from db import (
    fetch_data,
    get_all_filter_values,
    insert_dataframe,
    execute_query,
    log_execution_time,
    format_sql_values
)


@log_execution_time
def edit_screen(selected_table):
    c1, c2 = st.columns([1, 6])
    with c1:
        if st.button("⬅ Back", key="top_back"):
            st.session_state.page = "dashboard"
            st.rerun()
    with c2:
        st.markdown("## ✏️ Edit Data (Excel Mode)")

    # -------------------------------
    # SESSION STATE INIT
    # -------------------------------
    if "edit_applied_filters" not in st.session_state:
        st.session_state.edit_applied_filters = {}

    if "edit_temp_filters" not in st.session_state:
        st.session_state.edit_temp_filters = {}

    if "edit_current_table" not in st.session_state:
        st.session_state.edit_current_table = selected_table

    if st.session_state.edit_current_table != selected_table:
        st.session_state.edit_applied_filters = {}
        st.session_state.edit_temp_filters = {}
        st.session_state.edit_confirmed_df = None
        st.session_state.edit_current_table = selected_table

    if "edit_confirmed_df" not in st.session_state:
        st.session_state.edit_confirmed_df = None

    if "edit_original_df" not in st.session_state:
        st.session_state.edit_original_df = None

    # -------------------------------
    # FILTERS (FAST - SINGLE CALL)
    # -------------------------------
    st.sidebar.subheader("🔍 Edit Filters")

    all_filters = get_all_filter_values(selected_table)

    TABLE_FILTERS = {
        "branch_wise_monthly_target": ["month", "branch_name", "series_group"],
        "date_branch_wise_target": ["date", "branch_name", "series_group"],
        "brand_wise_monthly_target": ["month", "branch_name", "series_group", "item_code", "item_name"]
    }

    filter_cols = TABLE_FILTERS.get(selected_table, [])

    for col in filter_cols:
        try:
            values = all_filters.get(col, [])

            selected = st.sidebar.multiselect(
                col.replace("_", " ").title(),
                values,
                default=st.session_state.edit_temp_filters.get(col, [])
            )

            if selected:
                st.session_state.edit_temp_filters[col] = selected
            else:
                st.session_state.edit_temp_filters.pop(col, None)

        except Exception as e:
            st.warning(f"{col} error: {e}")

    # -------------------------------
    # APPLY / RESET
    # -------------------------------
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("🚀 Apply"):
            st.session_state.edit_applied_filters = st.session_state.edit_temp_filters.copy()
            st.session_state.edit_confirmed_df = None
            st.rerun()

    with col2:
        if st.button("🔄 Reset"):
            st.session_state.edit_temp_filters = {}
            st.session_state.edit_applied_filters = {}
            st.session_state.edit_confirmed_df = None
            st.rerun()

    # -------------------------------
    # LOAD DATA
    # -------------------------------
    applied_filters = st.session_state.edit_applied_filters

    with st.spinner("Loading records..."):
        if not applied_filters:
            st.info("ℹ️ Showing first 200 records. Use filters to narrow down.")
            df = fetch_data(selected_table, limit=200)
        else:
            df = fetch_data(selected_table, filters=applied_filters, limit=200)

    if df.empty:
        st.warning("No data available")
        return

    st.info("✏️ Edit cells directly")

    # -------------------------------
    # REMOVE SYSTEM COLS
    # -------------------------------
    display_df = df.drop(
        columns=["is_active", "version", "updated_at"],
        errors="ignore"
    )

    # Store original snapshot
    st.session_state.edit_original_df = display_df.copy()

    # -------------------------------
    # DATA EDITOR
    # -------------------------------
    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        width="stretch",
        key="editor"
    )

    # -------------------------------
    # CONFIRM CHANGES
    # -------------------------------
    if st.button("✅ Confirm Changes"):

        original_df = st.session_state.edit_original_df

        # detect diff
        diff_mask = (edited_df != original_df)

        if not diff_mask.any().any():
            st.warning("No changes detected")
            return

        changed_rows = edited_df[diff_mask.any(axis=1)]
        original_rows = original_df.loc[changed_rows.index]

        st.session_state.edit_confirmed_df = edited_df.copy()

        st.subheader("🔍 Changes Summary")

        st.markdown("### 🟥 Before")
        st.dataframe(original_rows, use_container_width=True)

        st.markdown("### 🟩 After")
        st.dataframe(changed_rows, use_container_width=True)

        st.info("👉 Review changes and click Final Save")

    # -------------------------------
    # FINAL SAVE
    # -------------------------------
    if st.session_state.edit_confirmed_df is not None:

        if st.button("💾 Final Save"):

            try:
                MAX_ROWS = 200

                with st.spinner("Loading data..."):

                    if applied_filters:
                        df = fetch_data(selected_table, filters=applied_filters, limit=MAX_ROWS)
                    else:
                        df = fetch_data(selected_table, limit=MAX_ROWS)
                        st.info(f"Showing first {MAX_ROWS} rows. Apply filters to refine.")

                edited_df = st.session_state.edit_confirmed_df.copy()

                # -------------------------------
                # BUILD WHERE CONDITION
                # -------------------------------
                # We identify columns that uniquely define a row in this table
                key_cols = TABLE_FILTERS.get(selected_table, [])
                
                if applied_filters:
                    # Case 1: Filtered replacement (standard)
                    condition_parts = []
                    for k, vals in applied_filters.items():
                        val_str = format_sql_values(vals)
                        condition_parts.append(f"{k} IN ({val_str})")
                    condition = " AND ".join(condition_parts)
                else:
                    # Case 2: Direct replacement (replace ONLY the 200 shown records)
                    # We use a multi-column IN clause for precision
                    keys_to_deactivate = []
                    
                    # Convert dates to string for SQL if they are objects
                    tmp_df = original_df.copy()
                    for col in key_cols:
                        if "month" in col or "date" in col:
                             tmp_df[col] = pd.to_datetime(tmp_df[col]).dt.strftime('%Y-%m-%d')
                    
                    for _, row in tmp_df.iterrows():
                        key_vals = [f"'{row[c]}'" if isinstance(row[c], str) else str(row[c]) for c in key_cols]
                        keys_to_deactivate.append(f"({', '.join(key_vals)})")
                    
                    condition = f"({', '.join(key_cols)}) IN ({', '.join(keys_to_deactivate)})"

                # -------------------------------
                # DEACTIVATE OLD DATA
                # -------------------------------
                query = f"""
                    ALTER TABLE {selected_table}
                    UPDATE is_active = 0
                    WHERE is_active = 1 AND {condition}
                """

                execute_query(query)

                # -------------------------------
                # ADD SYSTEM COLS
                # -------------------------------
                now_dt = datetime.now()
                version_val = int(now_dt.timestamp())

                edited_df["is_active"] = 1
                edited_df["version"] = version_val
                edited_df["updated_at"] = now_dt

                # Fix nulls
                edited_df = edited_df.fillna("")

                # -------------------------------
                # INSERT
                # -------------------------------
                success, msg = insert_dataframe(selected_table, edited_df)

                if success:
                    st.success(f"✅ {msg}")

                    # clear state
                    st.session_state.edit_confirmed_df = None
                    st.session_state.edit_applied_filters = {}
                    st.session_state.edit_temp_filters = {}

                    st.session_state.page = "dashboard"
                    st.rerun()

                else:
                    st.error(msg)

            except Exception as e:
                st.error(f"❌ Error: {e}")

    # -------------------------------
    # BACK BUTTON
    # -------------------------------
    if st.button("⬅ Back"):
        st.session_state.page = "dashboard"
        st.rerun()