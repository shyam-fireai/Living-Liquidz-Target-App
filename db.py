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
                values_str = ", ".join(
                    [f"'{v}'" if isinstance(v, str) else str(v) for v in values]
                )
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

    table_columns = {
        "branch_wise_monthly_target": ["month", "branch_name", "series_group"],
        "date_branch_wise_target": ["date", "branch_name", "series_group"],
        "brand_wise_monthly_target": ["month", "branch_name", "series_group", "item_code", "item_name"]
    }

    cols = table_columns.get(table, [])
    result_dict = {}

    for col in cols:
        query = f"""
            SELECT DISTINCT {col}
            FROM {table}
            WHERE is_active = 1
            LIMIT 1000
        """

        result = client.query(query)

        result_dict[col] = sorted([
            row[0] for row in result.result_rows if row[0] is not None
        ])

    return result_dict


# -------------------------------
# INSERT DATAFRAME
# -------------------------------
def insert_dataframe(table, df):
    try:
        client = get_client()

        df = df.copy()

        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].fillna("")
            else:
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