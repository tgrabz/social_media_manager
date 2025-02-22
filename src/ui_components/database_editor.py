# ui_components/database_editor.py

import streamlit as st
import pandas as pd
from utils.sheets import read_sheet, write_sheet

def database_editor_ui(spreadsheet_id: str, sheet_list: list):
    """
    Provide read/write access to the specified sheets in the same Google Spreadsheet.
    """
    st.header("Database Editor")
    st.write("""
    This page gives you direct read/write access to the Google Sheets tabs.
    Modify with caution: changes here are permanent.
    """)
    
    selected_sheet = st.selectbox("Select sheet to edit", sheet_list)
    
    df_current = read_sheet(spreadsheet_id, selected_sheet)
    if df_current.empty:
        st.info("Sheet is empty or not found.")
        return
    
    st.dataframe(df_current, use_container_width=True)
    
    st.write("Edit data below in real time. Press 'Save Changes' to commit updates to Google Sheets.")
    
    edited_df = st.experimental_data_editor(df_current, use_container_width=True, num_rows="dynamic")
    if st.button("Save Changes"):
        write_sheet(spreadsheet_id, selected_sheet, edited_df)
        st.success(f"Changes saved to {selected_sheet}!")
        st.experimental_rerun()
