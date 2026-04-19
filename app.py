import streamlit as st
import pandas as pd
import time
from datetime import datetime
from db import fetch_data, insert_dataframe, get_all_filter_values, log_execution_time, TABLE_SCHEMAS, format_column, remove_zero_columns, apply_currency_format
from style_utils import inject_minimalist_theme, render_header

# -------------------------------
# UI SETTINGS (MINIMALIST THEME)
# -------------------------------
st.set_page_config(
    page_title="Living Liquid Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_minimalist_theme()

# -------------------------------
# SESSION STATE
# -------------------------------
if "page" not in st.session_state:
    st.session_state.page = "dashboard"

if "upload_done" not in st.session_state:
    st.session_state.upload_done = False

if "applied_filters" not in st.session_state:
    st.session_state.applied_filters = {}

if "temp_filters" not in st.session_state:
    st.session_state.temp_filters = {}

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
        "filters": ["month", "branch_name", "series_group", "item_code", "item_name", "pack_name"],
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
    from upload import upload_screen
    upload_screen(selected_table)
    st.stop()

# -------------------------------
# HEADER & NAVIGATION (SINGLE ROW)
# -------------------------------
display_name = TABLE_CONFIG[selected_table]["name"]
col_edit, col_upload = render_header(title=display_name)

with col_edit:
    if st.button("📝 Edit", use_container_width=True):
        st.session_state.page = "edit"
        st.rerun()

with col_upload:
    if st.button("📤 Upload", use_container_width=True):
        st.session_state.page = "upload"
        st.rerun()


# -------------------------------
# LOAD FILTERS + DATA TOGETHER
# -------------------------------
with st.spinner("Loading dashboard..."):
    _dash_start = time.perf_counter()

    # ✅ SYNC LIVE STATE
    # At the start of rerun, pull latest widget choices into temp_filters
    filters_config = TABLE_CONFIG[selected_table]["filters"]
    for col in filters_config:
        w_key = f"sb_filter_{col}_{selected_table}"
        if w_key in st.session_state:
            st.session_state.temp_filters[col] = st.session_state[w_key]

    # ✅ DYNAMIC CASCADING FILTERS
    all_filters = get_all_filter_values(selected_table, st.session_state.temp_filters)

    st.sidebar.subheader("🔍 Filters")

    for col in filters_config:
        values = all_filters.get(col, [])

        if col == "date":
            # Compact Date Range Picker
            prev_dates = st.session_state.temp_filters.get(col, [])
            d1_val = prev_dates[0] if isinstance(prev_dates, (list, tuple)) and len(prev_dates) >= 1 else None
            d2_val = prev_dates[1] if isinstance(prev_dates, (list, tuple)) and len(prev_dates) >= 2 else None
            
            st.sidebar.caption("📅 Select Date Range")
            selected = st.sidebar.date_input(
                "Range",
                value=(d1_val, d2_val) if d1_val and d2_val else (d1_val,) if d1_val else [],
                key=f"sb_filter_{col}_{selected_table}",
                label_visibility="collapsed"
            )
        else:
            selected = st.sidebar.multiselect(
                format_column(col),
                values,
                key=f"sb_filter_{col}_{selected_table}",
                default=[v for v in st.session_state.temp_filters.get(col, []) if v in values]
            )

        # Update temp state immediately for cascading effect next rerun
        st.session_state.temp_filters[col] = selected

    # -------------------------------
    # RESET
    # -------------------------------
    if st.sidebar.button("🔄 Reset Filters", use_container_width=True):
        st.session_state.applied_filters = {}
        st.session_state.temp_filters = {}
        st.rerun()

    # -------------------------------
    # FETCH DATA (LIVE)
    # -------------------------------
    # The dashboard now updates instantly based on temp_filters
    if st.session_state.temp_filters:
        df = fetch_data(selected_table, filters=st.session_state.temp_filters, limit=200)
    else:
        df = fetch_data(selected_table, limit=200)
    
    _dash_end = time.perf_counter()
    print(f"[LOG] Dashboard data loading block took {_dash_end - _dash_start:.4f} seconds")

# (Month derivation removed as requested)

# -------------------------------
# CLEAN DATA
# -------------------------------
# Drop system columns
df = df.drop(columns=['version', 'updated_at', 'is_active'], errors='ignore')

# Remove zero/empty columns
df = remove_zero_columns(df)

# Apply Indian Comma formatting (Lakhs/Crores) 
# Handles both Currency (Values) and Quantities (Qty)
df = apply_currency_format(df)

# Standardize Headers
df.columns = [format_column(c) for c in df.columns]

# Format Date/Month columns to show only the date (remove 00:00:00)
for col in ["Date", "Month"]:
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col]).dt.date
        except:
            pass

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