import streamlit as st
import pandas as pd
from utils.sheets import read_sheet, write_sheet

def database_editor_ui(spreadsheet_id: str, sheet_name: str):
    st.title("Database Editor")
    
    df = read_sheet(spreadsheet_id, sheet_name)
    if df.empty:
        st.warning(f"No data found in '{sheet_name}'.")
        return

    st.subheader(f"Viewing: {sheet_name}")
    st.dataframe(df, use_container_width=True)

    if st.button("Refresh Data"):
        st.warning("Manually reload or switch tabs to see changes.")