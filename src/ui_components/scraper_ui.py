# ui_components/scraper_ui.py

import streamlit as st
import pandas as pd
import json
import subprocess
import traceback
from datetime import datetime
from utils.sheets import read_sheet, write_sheet

def scraper_ui(spreadsheet_id: str, sheet_niches: str, sheet_burners: str, twitter_scraper_script_path=None):
    st.header("Scraper")

    # 1) Load burner accounts
    df_burners = read_sheet(spreadsheet_id, sheet_burners)
    if df_burners.empty:
        df_burners = pd.DataFrame(columns=["id","platform","username","password","active","date_added"])
    
    # Show existing burner accounts
    st.subheader("Burner Accounts")
    if not df_burners.empty:
        st.dataframe(df_burners, use_container_width=True)
    else:
        st.info("No burner accounts found.")
    
    # Add a new burner account
    st.subheader("Add Burner Account")
    col1, col2, col3 = st.columns(3)
    with col1:
        ba_platform = st.selectbox("Platform", ["twitter","instagram","tiktok"])
    with col2:
        ba_username = st.text_input("Username")
    with col3:
        ba_password = st.text_input("Password", type="password")
    
    if st.button("Add Burner Account"):
        if ba_username.strip():
            new_id = str(len(df_burners)+1)
            new_row = {
                "id": new_id,
                "platform": ba_platform,
                "username": ba_username.strip(),
                "password": ba_password,
                "active": "True",
                "date_added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            df_burners = df_burners.append(new_row, ignore_index=True)
            write_sheet(spreadsheet_id, sheet_burners, df_burners)
            st.success("Burner account added!")
            st.experimental_rerun()
        else:
            st.warning("Please provide a username.")
    
    st.write("---")
    
    # 2) Choose a niche to scrape
    df_niches = read_sheet(spreadsheet_id, sheet_niches)
    if df_niches.empty:
        st.info("No niches found. Create one in Niche Creator tab.")
        return
    
    active_niches = df_niches[df_niches["active"] == "True"]
    if active_niches.empty:
        st.info("No active niches found. Activate a niche in Niche Creator tab.")
        return
    
    niche_choices = active_niches["niche_name"].tolist()
    selected_niche = st.selectbox("Select Niche to Scrape", niche_choices)
    
    if st.button("Scrape Now"):
        niche_row = active_niches[active_niches["niche_name"] == selected_niche].iloc[0]
        target_profiles = niche_row["target_profiles"]
        platforms = niche_row["platforms"]
        
        st.write(f"Scraping niche: **{selected_niche}**")
        st.write(f"**Platforms**: {platforms}")
        st.write(f"**Targets**: {target_profiles}")
        
        # If you have a separate script (e.g. twitter_scraper.py)
        if twitter_scraper_script_path:
            try:
                # Build JSON for targets
                targets_list = [t.strip() for t in target_profiles.split(",") if t.strip()]
                data_for_scraper = []
                for t in targets_list:
                    data_for_scraper.append({
                        "platform": "twitter",  # or parse from `platforms`
                        "username": t,
                        "min_views": 100000,
                        "active": True
                    })
                
                # Write to temp file
                temp_file = "temp_targets.json"
                with open(temp_file, "w") as f:
                    json.dump(data_for_scraper, f, indent=2)
                
                cmd = [
                    "python", str(twitter_scraper_script_path),
                    "--targets", temp_file,
                    "--max-scrolls", "10"
                ]
                subprocess.run(cmd, check=True)
                st.success("Scrape complete!")
            except Exception as e:
                st.error(f"Scraper error: {str(e)}")
                st.code(traceback.format_exc())
        else:
            st.warning("No scraper script path provided.")
