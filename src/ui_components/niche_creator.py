# ui_components/niche_creator.py

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.sheets import read_sheet, write_sheet

def niche_creator_ui(spreadsheet_id: str, sheet_name_niches: str):
    """
    Renders the UI for 'Niche Creator' tab.
    """
    st.header("Niche Creator")
    
    # 1) Load existing niches from GSheet
    df_niches = read_sheet(spreadsheet_id, sheet_name_niches)
    if df_niches.empty:
        # Create a default structure if empty
        df_niches = pd.DataFrame(columns=["niche_name","platforms","target_profiles","active","date_created"])
    
    # Display existing niches
    st.subheader("Existing Niches")
    if df_niches.empty:
        st.info("No niches found yet.")
    else:
        st.dataframe(df_niches, use_container_width=True)
    
    # 2) Create a new niche
    st.subheader("Create a New Niche")
    col1, col2 = st.columns(2)
    with col1:
        new_niche_name = st.text_input("Niche Name")
        selected_platforms = st.multiselect("Platforms", ["twitter", "instagram", "tiktok"])
    with col2:
        new_targets = st.text_area("Target Profiles (comma-separated)")
    
    if st.button("Add Niche"):
        if new_niche_name.strip():
            row_dict = {
                "niche_name": new_niche_name.strip(),
                "platforms": ",".join(selected_platforms),
                "target_profiles": new_targets,
                "active": "True",
                "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            df_niches = df_niches.append(row_dict, ignore_index=True)
            write_sheet(spreadsheet_id, sheet_name_niches, df_niches)
            st.success(f"Niche '{new_niche_name}' added!")
            st.experimental_rerun()
        else:
            st.warning("Please provide a valid niche name.")
    
    # 3) Toggle or remove niches
    st.subheader("Toggle or Remove Niches")
    for i, row in df_niches.iterrows():
        c1, c2, c3 = st.columns([2,1,1])
        c1.write(f"**{row['niche_name']}** | Active: {row['active']}")
        
        if c2.button("Toggle Active", key=f"toggle_{i}"):
            df_niches.at[i, "active"] = "False" if row["active"] == "True" else "True"
            write_sheet(spreadsheet_id, sheet_name_niches, df_niches)
            st.experimental_rerun()
        
        if c3.button("Delete", key=f"delete_{i}"):
            df_niches = df_niches.drop(i)
            write_sheet(spreadsheet_id, sheet_name_niches, df_niches)
            st.experimental_rerun()

