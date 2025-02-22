# utils/sheets.py

import pandas as pd
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SERVICE_ACCOUNT_FILE = "config/service-account-key.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

@st.cache_resource
def get_sheets_service():
    """Authenticate and cache the Google Sheets service."""
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=creds)

def read_sheet(spreadsheet_id: str, sheet_name: str, start_cell="A1") -> pd.DataFrame:
    """
    Read the specified sheet (sheet_name) from a Google spreadsheet_id
    and return as a DataFrame. Headers are assumed in the first row.
    """
    service = get_sheets_service()
    range_ = f"{sheet_name}!{start_cell}:Z"  # Read a wide range (A1:Z?)
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_
        ).execute()
        values = result.get("values", [])
        if not values:
            return pd.DataFrame()  # No data found
        
        headers = values[0]
        rows = values[1:]
        df = pd.DataFrame(rows, columns=headers)
        return df

    except HttpError as err:
        st.error(f"Error reading sheet '{sheet_name}': {err}")
        return pd.DataFrame()

def write_sheet(spreadsheet_id: str, sheet_name: str, df: pd.DataFrame, start_cell="A1"):
    """
    Overwrite the entire sheet (starting at start_cell) with df.
    This REPLACES old data in that range.
    """
    service = get_sheets_service()
    header = list(df.columns)
    rows = df.values.tolist()
    data = [header] + rows
    body = {"values": data}
    range_ = f"{sheet_name}!{start_cell}"
    
    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_,
            valueInputOption="RAW",
            body=body
        ).execute()
    except HttpError as err:
        st.error(f"Error writing to sheet '{sheet_name}': {err}")
