import streamlit as st
import pandas as pd
import time
from datetime import datetime
from db import fetch_data, insert_dataframe, get_all_filter_values
from edit import edit_screen

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
# REQUIRED COLUMNS
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
        "month", "branch_name", "series_group",
        "item_code", "item_name", "pack_name"
    ]
}

# -------------------------------
# FORMAT COLUMN
# -------------------------------
def format_column(col):
    if col == "series_group":
        return "Series"
    return col.replace("_", " ").title()

# -------------------------------
# ₹ FORMAT
# -------------------------------
def format_inr(x):
    try:
        x = float(x)
        s = f"{x:.2f}"
        parts = s.split(".")
        num = parts[0]
        dec = parts[1]

        if len(num) > 3:
            last3 = num[-3:]
            rest = num[:-3]
            rest = ",".join(
                [rest[max(i-2, 0):i] for i in range(len(rest), 0, -2)][::-1]
            )
            num = rest + "," + last3

        return f"₹{num}.{dec}"
    except:
        return x

def apply_currency_format(df):
    for col in df.columns:
        if "value" in col.lower():
            df[col] = df[col].apply(format_inr)
    return df

# -------------------------------
# REMOVE ZERO COLUMNS
# -------------------------------
def remove_zero_columns(df):
    protected_cols = ["month", "date", "branch_name", "series_group"]

    cols_to_keep = []

    for col in df.columns:
        if col in protected_cols:
            cols_to_keep.append(col)
            continue

        try:
            numeric_col = pd.to_numeric(df[col], errors='coerce')
            if not ((numeric_col.fillna(0) == 0).all()):
                cols_to_keep.append(col)
        except:
            cols_to_keep.append(col)

    return df[cols_to_keep]

# -------------------------------
# SIDEBAR TABLE SELECT
# -------------------------------
st.sidebar.title("📂 Tables")

table_keys = list(TABLE_CONFIG.keys())
table_display = [TABLE_CONFIG[t]["name"] for t in table_keys]

selected_display = st.sidebar.radio("Select Table", table_display)
selected_table = table_keys[table_display.index(selected_display)]

# -------------------------------
# EDIT PAGE
# -------------------------------
if st.session_state.page == "edit":
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

# -------------------------------
# DERIVE MONTH
# -------------------------------
if selected_table == "date_branch_wise_target":
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M").astype(str)

# -------------------------------
# CLEAN DATA
# -------------------------------
df = remove_zero_columns(df)
df.columns = [format_column(c) for c in df.columns]

if TABLE_CONFIG[selected_table]["currency"]:
    df = apply_currency_format(df)

# -------------------------------
# DISPLAY
# -------------------------------
st.dataframe(df, use_container_width=True)