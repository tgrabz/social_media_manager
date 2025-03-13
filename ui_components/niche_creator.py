# niche_creator.py

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.sheets import read_sheet, write_sheet

# Define the columns we expect in the Google Sheet
COLUMNS = ["niche_name", "platforms", "target_profiles", "active", "date_created"]

def load_niches_once(spreadsheet_id, sheet_name):
    """Load the Niches sheet into session_state if not already done."""
    if "niches_df" not in st.session_state:
        df = read_sheet(spreadsheet_id, sheet_name)
        if df.empty:
            # create a blank DataFrame with the columns we need
            df = pd.DataFrame(columns=COLUMNS)
        else:
            # ensure all columns exist
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = ""
        st.session_state["niches_df"] = df
    return st.session_state["niches_df"]

def refresh_niches(spreadsheet_id, sheet_name):
    """Force a fresh read from Google Sheets."""
    df = read_sheet(spreadsheet_id, sheet_name)
    if df.empty:
        df = pd.DataFrame(columns=COLUMNS)
    else:
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
    st.session_state["niches_df"] = df
    return df

def save_niches(spreadsheet_id, sheet_name, df):
    """Write the DataFrame back to Sheets, update session state."""
    write_sheet(spreadsheet_id, sheet_name, df)
    st.session_state["niches_df"] = df.copy()

def niche_creator_ui(spreadsheet_id, sheet_name_niches):
    st.title("Niche Creator / Manager (Hybrid)")

    df_niches = load_niches_once(spreadsheet_id, sheet_name_niches)

    # Top buttons: Refresh from Sheets & Save All Changes
    col1, col2 = st.columns([0.3, 0.7])
    with col1:
        if st.button("Refresh from Sheets"):
            df_niches = refresh_niches(spreadsheet_id, sheet_name_niches)
            st.success("Data reloaded from Google Sheets.")

    with col2:
        if st.button("Save All Changes to Sheets"):
            save_niches(spreadsheet_id, sheet_name_niches, df_niches)
            st.success("Saved to Google Sheets!")

    st.write("---")

    # 1) Full Editable Table
    st.subheader("Editable Table of Niches")
    edited_df = st.data_editor(
        df_niches,
        use_container_width=True,
        num_rows="dynamic",
        key="niches_editor"
    )
    # Keep this updated in session state
    st.session_state["niches_df"] = edited_df

    st.write("---")

    # 2) Itemize Target Profiles for one row
    st.subheader("Itemize 'target_profiles' for a Selected Row")

    if edited_df.empty:
        st.info("No rows found. Use the table above to add a new row, or create one below.")
    else:
        # Let the user pick a row by index
        row_labels = [f"{i}: {row['niche_name']}" for i, row in edited_df.iterrows()]
        choice = st.selectbox("Select a niche row to itemize", ["(None)"] + row_labels)

        if choice != "(None)":
            # Extract the numeric index from "X: Niche Name"
            row_idx = int(choice.split(":")[0])
            # For convenience, store a local DataFrame reference
            df_item = st.session_state["niches_df"]
            
            # Parse the existing target_profiles string
            current_str = df_item.at[row_idx, "target_profiles"] or ""
            profile_list = [p.strip() for p in current_str.split(",") if p.strip()]

            st.write(f"**Niche Name**: {df_item.at[row_idx, 'niche_name']}")
            st.write(f"**Platforms**: {df_item.at[row_idx, 'platforms']}")

            st.markdown("**Current Profiles**:")
            if not profile_list:
                st.write("(none)")
            else:
                for i, prof in enumerate(profile_list):
                    c1, c2 = st.columns([0.95, 0.05])
                    with c1:
                        st.markdown(f"- {prof}")
                    with c2:
                        # Remove a profile from the list
                        if st.button("❌", key=f"remove_{row_idx}_{i}"):
                            profile_list.pop(i)
                            new_val = ",".join(profile_list)
                            df_item.at[row_idx, "target_profiles"] = new_val
                            st.session_state["niches_df"] = df_item
                            st.experimental_rerun()

            # Add a new profile
            new_profile_input = st.text_input("Add new profile (e.g. @someuser)")
            if st.button("Add Profile"):
                p = new_profile_input.strip()
                if p and p not in profile_list:
                    profile_list.append(p)
                    new_val = ",".join(profile_list)
                    df_item.at[row_idx, "target_profiles"] = new_val
                    st.session_state["niches_df"] = df_item
                # Clear the local text_input by re-running
                st.experimental_rerun()

    st.write("---")

    # 3) Quick "Create Niche" form
    st.subheader("Create a New Niche")

    new_niche_name = st.text_input("Niche Name", placeholder="e.g. Cooking Enthusiasts")
    new_platforms = st.multiselect("Platforms", ["twitter","instagram","tiktok"])
    
    # We'll store new profiles in a local variable (no session key needed).
    # This means each run the text area is reset if we re-run. 
    # Alternatively, we can store them in st.session_state if you prefer to keep them across runs.
    new_profiles_raw = st.text_area("Target Profiles (comma-separated or one per line)", "")
    
    if st.button("Create Niche"):
        # Merge lines with commas
        combined_profiles_str = ",".join(
            p.strip() for p in new_profiles_raw.replace("\n", ",").split(",") if p.strip()
        )
        if not new_niche_name.strip():
            st.warning("Please enter a niche name.")
            return
        # Append to the in-memory DataFrame
        df_new = st.session_state["niches_df"]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = {
            "niche_name": new_niche_name.strip(),
            "platforms": ",".join(new_platforms),
            "target_profiles": combined_profiles_str,
            "active": "True",
            "date_created": now_str
        }
        df_new = pd.concat([df_new, pd.DataFrame([row_data])], ignore_index=True)
        st.session_state["niches_df"] = df_new

        st.success(f"Created new niche '{new_niche_name}'.")
        st.experimental_rerun()

    st.markdown("""
    ---
    **Tip:** Don't forget to click "Save All Changes to Sheets" to persist your latest edits.
    """)