import streamlit as st

from ui_components.niche_creator import niche_creator_ui
from ui_components.scraper_ui import scraper_ui
from ui_components.profile_management import profile_management_ui
from ui_components.database_editor import database_editor_ui

# Hardcode your Google Sheet ID (change if needed)
SPREADSHEET_ID = "10LBqtOn9DZ1_fV_03MPUZJZq7lTTMTOwcbg8GE7wiBg"

# Define sheet names
NICHES_SHEET = "Niches"
BURNER_SHEET = "BurnerAccounts"
PROFILES_SHEET = "Profiles"
VIDEO_DATABASE_SHEET = "VideoDatabase"
INVENTORY_SHEET = "Inventory"  # <-- Make sure this matches your sheet's tab name EXACTLY

def main():
    # Streamlit page config
    st.set_page_config(
        page_title="X_Scheduler_Pro",
        page_icon="📱",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Sidebar navigation
    st.sidebar.title("Navigation")
    tabs = [
        "Niche Creator",
        "Scraper",
        "Profile Management",
        "Database Editor",
    ]
    choice = st.sidebar.selectbox("Select a Section", tabs)

    if choice == "Niche Creator":
        niche_creator_ui(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name_niches=NICHES_SHEET
        )

    elif choice == "Scraper":
        scraper_ui(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_niches=NICHES_SHEET,
            sheet_burners=BURNER_SHEET,
            scraped_videos_sheet=VIDEO_DATABASE_SHEET
        )

    elif choice == "Profile Management":
        # IMPORTANT: Now we add the inventory_sheet parameter 
        profile_management_ui(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_profiles=PROFILES_SHEET,
            sheet_videos=VIDEO_DATABASE_SHEET,
            inventory_sheet=INVENTORY_SHEET
        )

    elif choice == "Database Editor":
        database_editor_ui(
            spreadsheet_id=SPREADSHEET_ID,
            sheet_name=VIDEO_DATABASE_SHEET
        )

if __name__ == "__main__":
    main()