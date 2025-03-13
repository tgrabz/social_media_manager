import os
import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 1) Use an absolute path to your JSON file:
SERVICE_ACCOUNT_FILE = "/Users/tylergrabowski/scripts/social_media_manager/src/config/service-account-key.json"

# 2) Include both Sheets & Drive scopes:
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_sheets_service():
    """
    Builds and returns a Sheets service client using your service account JSON.
    """
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)

def read_sheet(spreadsheet_id: str, sheet_name: str):
    """
    Reads values from a specific sheet within a Google Spreadsheet.
    Returns a pandas DataFrame of the results.
    """
    service = get_sheets_service()
    range_ = f"{sheet_name}!A1:Z"
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_
        ).execute()
        values = result.get("values", [])
        if not values:
            return pd.DataFrame()

        headers = values[0]
        data_rows = values[1:]
        if not data_rows:
            return pd.DataFrame(columns=headers)

        # Normalize rows so each row has len(headers) columns
        num_cols = len(headers)
        trimmed_rows = []
        for row in data_rows:
            row_sliced = row[:num_cols]
            if len(row_sliced) < num_cols:
                row_sliced += [""] * (num_cols - len(row_sliced))
            trimmed_rows.append(row_sliced)

        df = pd.DataFrame(trimmed_rows, columns=headers)
        return df

    except HttpError as err:
        st.error(f"Error reading sheet '{sheet_name}': {err}")
        return pd.DataFrame()

def write_sheet(spreadsheet_id: str, sheet_name: str, df: pd.DataFrame, start_cell="A1"):
    """
    Writes a pandas DataFrame to a specific sheet within a Google Spreadsheet.
    Overwrites existing data starting at `start_cell`.

    Added debug statements so we see exactly what's being written.
    """
    service = get_sheets_service()
    df = df.fillna("").astype(str)

    header = list(df.columns)
    rows = df.values.tolist()
    data = [header] + rows
    body = {"values": data}
    range_ = f"{sheet_name}!{start_cell}"

    # Debug logs
    st.write(f"[write_sheet] Attempting to overwrite '{sheet_name}' from {start_cell}.")
    st.write(f"[write_sheet] DataFrame shape: {df.shape} (that's {len(df)} rows, plus 1 header row).")
    if rows:
        st.write(f"[write_sheet] First row's data => {rows[0]}")
    else:
        st.write("[write_sheet] No rows in DataFrame to write.")

    try:
        response = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="RAW",
            body=body
        ).execute()

        st.write("[write_sheet] API response:", response)
        st.success(f"[write_sheet] Successfully wrote {len(df)} rows to '{sheet_name}'.")
    except HttpError as err:
        st.error(f"[write_sheet] Error writing to sheet '{sheet_name}': {err}")