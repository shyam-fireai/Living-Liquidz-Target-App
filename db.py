import clickhouse_connect
import json
import pandas as pd
from datetime import datetime
import streamlit as st
import time
import functools


# -------------------------------
# LOGGING DECORATOR
# -------------------------------
def log_execution_time(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"[LOG] {func.__name__} executed in {duration:.4f} seconds")
        return result
    return wrapper


# -------------------------------
# SQL VALUE FORMATTER
# -------------------------------
def format_sql_values(values):
    if not values:
        return ""
    
    formatted = []
    for v in values:
        if isinstance(v, (int, float)):
            formatted.append(str(v))
        else:
            # Wrap strings and dates in quotes
            formatted.append(f"'{v}'")
            
    return ", ".join(formatted)


# -------------------------------
# TABLE SCHEMAS
# -------------------------------
TABLE_SCHEMAS = {
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
        "item_code", "item_name", "pack_name",
        "target_qty1", "incentive_value1",
        "target_qty2", "incentive_value2",
        "target_qty3", "incentive_value3",
        "target_qty4", "incentive_value4",
        "target_qty5", "incentive_value5"
    ]
}


# -------------------------------
# CONNECT CLIENT
# -------------------------------
@log_execution_time
@st.cache_resource
def get_client():
    with open('secrets.json', 'r') as f:
        creds = json.load(f)

    conf = creds['data_clickhouse']

    return clickhouse_connect.get_client(
        host=conf['host'],
        port=conf['port'],
        username=conf['username'],
        password=conf['password'],
        database=conf['database'],
        secure=True,
        connect_timeout=30,
        send_receive_timeout=60
    )


# -------------------------------
# FETCH DATA
# -------------------------------
@log_execution_time
@st.cache_data(ttl=60, show_spinner=False)
def fetch_data(table, filters=None, limit=200):
    client = get_client()

    query = f"SELECT * FROM {table}"
    conditions = ["is_active = 1"]

    if filters:
        for col, values in filters.items():
            if values:
                values_str = format_sql_values(values)
                conditions.append(f"{col} IN ({values_str})")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += f" LIMIT {limit}"
    query += " SETTINGS max_execution_time=60"

    result = client.query(query)

    return pd.DataFrame(result.result_rows, columns=result.column_names)


# -------------------------------
# FILTER VALUES (CACHED)
# -------------------------------
@log_execution_time
@st.cache_data(ttl=300)
def get_all_filter_values(table):
    client = get_client()

    # Get filter columns from schemas (first 5 columns are typically the filter indices)
    all_cols = TABLE_SCHEMAS.get(table, [])
    
    # Define which columns should be filters based on table type
    if table == "brand_wise_monthly_target":
        cols = ["month", "branch_name", "series_group", "item_code", "item_name"]
    elif table == "date_branch_wise_target":
        cols = ["date", "branch_name", "series_group"]
    else:
        cols = ["month", "branch_name", "series_group"]

    if not cols:
        return {}

    # SINGLE QUERY OPTIMIZATION: Fetch all unique values in one scan
    col_queries = [f"groupUniqArray({col}) as {col}" for col in cols]
    query = f"""
        SELECT {', '.join(col_queries)}
        FROM {table}
        WHERE is_active = 1
    """

    result = client.query(query)
    
    # ClickHouse groupUniqArray returns a list for each column in one row
    row = result.result_rows[0]
    result_dict = {}
    for i, col in enumerate(cols):
        result_dict[col] = sorted([v for v in row[i] if v is not None])

    return result_dict


# -------------------------------
# INSERT DATAFRAME
# -------------------------------
def insert_dataframe(table, df):
    try:
        client = get_client()

        df = df.copy()

        # Identify columns that should be strings to avoid numpy numeric type issues
        string_cols = ["branch_name", "series_group", "item_code", "item_name", "pack_name", "series"]
        
        for col in df.columns:
            if col in string_cols:
                # Force to string, uppercase, and fill nulls with empty string
                df[col] = df[col].astype(str).str.upper().replace(["NONE", "NAN", "<NA>"], "")
            elif df[col].dtype == "object":
                # For other object types, fill with empty string
                df[col] = df[col].fillna("")
            elif "target" in col.lower() or "incentive" in col.lower():
                # Ensure targets and incentives are numeric
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            else:
                # For integers and others
                df[col] = df[col].fillna(0)

        now_dt = datetime.now()
        version_val = int(now_dt.timestamp())

        df["version"] = version_val
        df["updated_at"] = now_dt
        df["is_active"] = 1

        client.insert_df(table, df)

        return True, f"{len(df)} rows inserted"

    except Exception as e:
        return False, str(e)


# -------------------------------
# EXECUTE QUERY
# -------------------------------
def execute_query(query):
    client = get_client()
    client.command(query)


# -------------------------------
# UI FORMATTING HELPERS
# -------------------------------
def format_column(col):
    if col == "series_group":
        return "Series"
    return col.replace("_", " ").title()


def remove_zero_columns(df):
    # Columns that should ALWAYS be shown regardless of being zero
    protected_cols = [
        "month", "date", "branch_name", "series_group", "series",
        "item_code", "item_name", "pack_name"
    ]
    
    # Identify non-protected columns
    other_cols = [c for c in df.columns if c not in protected_cols]
    if not other_cols:
        return df

    # Check which of these columns have at least one non-zero value
    num_df = df[other_cols].apply(pd.to_numeric, errors='coerce').fillna(0)
    non_zero_cols = set(num_df.columns[(num_df != 0).any()].tolist())

    # Build final column list
    cols_to_keep = [c for c in df.columns if c in protected_cols or c in non_zero_cols]
    
    return df[cols_to_keep]


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