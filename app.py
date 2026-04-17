import streamlit as st
import pandas as pd
import time
from datetime import datetime
from db import fetch_data, insert_dataframe, get_all_filter_values, log_execution_time, TABLE_SCHEMAS, format_column, remove_zero_columns, apply_currency_format
# from edit import edit_screen (Moved to conditional block)

st.set_page_config(layout="wide")

# -------------------------------
# SESSION STATE
# -------------------------------
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

if "upload_done" not in st.session_state:
    st.session_state.upload_done = False

if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {}

if "current_table" not in st.session_state:
    st.session_state.current_table = None
# -------------------------------
# TABLE CONFIG
# -------------------------------
TABLE_CONFIG = {
    "branch_wise_monthly_target": {
        "name": "Branch Wise Monthly Target",
        "filters": ["month", "branch_name", "series_group"],
        "currency": True
    },
    "brand_wise_monthly_target": {
        "name": "Brand Wise Monthly Target",
        "filters": ["month", "branch_name", "series_group", "item_code", "item_name"],
        "currency": False
    },
    "date_branch_wise_target": {
        "name": "Date & Branch Wise Target",
        "filters": ["date", "branch_name", "series_group"],
        "currency": True
    }
}

# -------------------------------
# REQUIRED COLUMNS (REPLACED BY db.TABLE_SCHEMAS)
# -------------------------------
REQUIRED_COLUMNS = TABLE_SCHEMAS

# -------------------------------
# ₹ FORMAT
# (apply_currency_format moved to db.py)
# -------------------------------
# REMOVE ZERO COLUMNS
# -------------------------------
# SIDEBAR TABLE SELECT
# -------------------------------
# SIDEBAR TABLE SELECT
# -------------------------------
st.sidebar.title("📂 Tables")

table_keys = list(TABLE_CONFIG.keys())
table_display = [TABLE_CONFIG[t]["name"] for t in table_keys]

selected_display = st.sidebar.radio("Select Table", table_display)
selected_table = table_keys[table_display.index(selected_display)]

# RESET FILTERS ON TABLE SWITCH
if st.session_state.current_table != selected_table:
    st.session_state.applied_filters = {}
    st.session_state.upload_done = False
    st.session_state.upload_msg = ""
    st.session_state.current_table = selected_table

# -------------------------------
# EDIT PAGE
# -------------------------------
if st.session_state.page == "edit":
    from edit import edit_screen
    edit_screen(selected_table)
    st.stop()

# -------------------------------
# UPLOAD PAGE
# -------------------------------
if st.session_state.page == "upload":
    from upload import upload_modal
    upload_modal(selected_table)
    st.stop()

# -------------------------------
# HEADER
# -------------------------------
col1, col2, col3 = st.columns([7, 2, 2])

with col1:
    st.markdown(f"## 📊 {selected_display}")

with col2:
    if st.button("✏️ Edit"):
        st.session_state.page = "edit"

with col3:
    if st.button("📤 Upload"):
        st.session_state.page = "upload"

# -------------------------------
# LOAD FILTERS + DATA TOGETHER
# -------------------------------
with st.spinner("Loading dashboard..."):
    _dash_start = time.perf_counter()

    # ✅ ONE CALL ONLY
    all_filters = get_all_filter_values(selected_table)

    filters_config = TABLE_CONFIG[selected_table]["filters"]
    current_filters = {}

    st.sidebar.subheader("🔍 Filters")

    for col in filters_config:
        values = all_filters.get(col, [])

        selected = st.sidebar.multiselect(
            format_column(col),
            values,
            default=st.session_state.applied_filters.get(col, [])
        )

        current_filters[col] = selected

    if st.sidebar.button("🚀 Apply Filters"):
        st.session_state.applied_filters = current_filters
        st.rerun()

    if st.sidebar.button("🔄 Reset Filters"):
        st.session_state.applied_filters = {}
        st.rerun()

    # -------------------------------
    # FETCH DATA
    # -------------------------------
    if st.session_state.applied_filters:
        df = fetch_data(selected_table, filters=st.session_state.applied_filters, limit=200)
    else:
        df = fetch_data(selected_table, limit=200)
    
    _dash_end = time.perf_counter()
    print(f"[LOG] Dashboard data loading block took {_dash_end - _dash_start:.4f} seconds")

# -------------------------------
# DERIVE MONTH
# -------------------------------
if selected_table == "date_branch_wise_target":
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

# -------------------------------
# CLEAN DATA
# -------------------------------
# Drop system columns
df = df.drop(columns=['version', 'updated_at', 'is_active'], errors='ignore')

# Remove zero/empty columns
df = remove_zero_columns(df)

# Apply Indian Comma formatting (₹ and Lakhs/Crores) for currency tables
if TABLE_CONFIG[selected_table].get("currency"):
    df = apply_currency_format(df)

# Standardize Headers
df.columns = [format_column(c) for c in df.columns]

# -------------------------------
# DISPLAY
# -------------------------------
# Use native formatting ONLY for columns that are still numeric (e.g. Qty in non-currency tables)
# Formatted currency columns are now strings and will be handled as Text automatically
numeric_cols = [
    c for c in df.columns 
    if any(x in c for x in ["Qty", "Value"]) and pd.api.types.is_numeric_dtype(df[c])
]
config = {c: st.column_config.NumberColumn(format="%.2f") for c in numeric_cols}

st.dataframe(df, column_config=config, width="stretch")