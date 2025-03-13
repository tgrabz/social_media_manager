import streamlit as st
import pandas as pd
import logging
import os
from pathlib import Path
from datetime import datetime

from utils.sheets import read_sheet, write_sheet
# Instead of old run_scraper_twitter, we import run_scraper_for_niche
from src.scrapers.scraper import run_scraper_for_niche

from yt_dlp import YoutubeDL
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SERVICE_ACCOUNT_FILE = "src/config/service-account-key.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

PLATFORM_LOCAL_DIRS = {
    "twitter": "/Users/tylergrabowski/scripts/social_media_manager/@downloads/twitter",
    "instagram": "/Users/tylergrabowski/scripts/social_media_manager/@downloads/instagram",
    "tiktok": "/Users/tylergrabowski/scripts/social_media_manager/@downloads/tiktok",
    "unknown": "/Users/tylergrabowski/scripts/social_media_manager/@downloads/other"
}

PLATFORM_DRIVE_FOLDERS = {
    "twitter": "1eVuW0TUv_aApUc8Cb7oV4l0QD4zkR7V8",
    "instagram": "1OFVnrUhwijo9o25GBUNNGiBmgpmMuESY",
    "tiktok": "1Qgc5JFMY_XGrrZt146HDPBrE-w8jhH4R",
    "unknown": "DEFAULT_FOLDER_ID"
}

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def scraper_ui(spreadsheet_id: str, sheet_niches: str, sheet_burners: str, scraped_videos_sheet: str):
    """
    Streamlit UI for:
    1) Scraping new tweets (incrementally writing each row to sheet with posted='N'),
    2) Download manager (same logic as before),
    3) Potential other sections (Niche Creator, Profile Management, etc.).
    """
    st.header("Scraper / Downloads (Local + Drive)")

    # 1) SCRAPING SECTION
    st.subheader("Scrape New Tweets")

    # ---------- BURNER LOADING ----------
    df_burners = read_sheet(spreadsheet_id, sheet_burners)
    if df_burners.empty:
        st.warning("No burner accounts found.")
        return
    active_burners = df_burners[df_burners["active"] == "True"]
    if active_burners.empty:
        st.warning("No active burners. Mark at least one as active.")
        return

    burner_choices = [f"{row['platform']} | {row['username']}" for _, row in active_burners.iterrows()]
    selected_burner = st.selectbox("Active Burner", burner_choices)

    # ---------- NICHE LOADING ----------
    df_niches = read_sheet(spreadsheet_id, sheet_niches)
    if df_niches.empty:
        st.warning("No niches found. Create them first.")
        return
    active_niches = df_niches[df_niches["active"] == "True"]
    if active_niches.empty:
        st.warning("No active niches.")
        return

    niche_choices = active_niches["niche_name"].tolist()
    selected_niche = st.selectbox("Active Niche", niche_choices)

    # ---------- SCRAPER PARAMS ----------
    max_scrolls = st.number_input("Max Scrolls", min_value=1, max_value=50, value=15)
    min_views = st.number_input("Minimum Views", min_value=0, max_value=1_000_000, value=100_000, step=50_000)
    max_videos = st.number_input("Max Videos", min_value=1, max_value=100, value=10)

    # ---------- SCRAPE NOW BUTTON ----------
    if st.button("Scrape Now"):
        burner_platform, burner_username = selected_burner.split(" | ", 1)
        burner_row = active_burners[
            (active_burners["platform"] == burner_platform) &
            (active_burners["username"] == burner_username)
        ].iloc[0]
        burner_password = burner_row["password"]

        niche_row = active_niches[active_niches["niche_name"] == selected_niche].iloc[0]
        target_profiles = niche_row.get("target_profiles", "")
        targets_list = [t.strip().lstrip("@") for t in target_profiles.split(",") if t.strip()]

        if not targets_list:
            st.warning(f"No target profiles in niche '{selected_niche}'.")
            return

        st.write(f"Scraping with {burner_username} on {burner_platform}, niche '{selected_niche}'...")

        try:
            run_scraper_for_niche(
                burner_username,
                burner_password,
                targets_list,
                spreadsheet_id,
                scraped_videos_sheet,  # e.g. "VideoDatabase"
                selected_niche,
                burner_platform,
                max_scrolls=max_scrolls,
                min_views=min_views,
                max_videos=max_videos
            )
            st.success("Scrape done! Each tweet is recorded incrementally with posted='N'.")
        except Exception as e:
            st.error(f"Scraper error: {e}")
            return

    st.write("---")

    # ---------- DOWNLOAD MANAGER ----------
    st.subheader("Download Manager: 'downloaded y/n/c' with local_path")

    df_videos = read_sheet(spreadsheet_id, scraped_videos_sheet)
    if df_videos.empty:
        st.info("No data in 'VideoDatabase' yet.")
        return

    needed_cols = [
        "ID",
        "niche",
        "video_url",
        "downloaded y/n/c",
        "download_url",
        "local_path",
        "caption",
        "views",
        "timestamp",
        "platform",
        "account uploaded to",
        "time uploaded",
        "posted"  # new column
    ]
    missing_cols = [c for c in needed_cols if c not in df_videos.columns]
    if missing_cols:
        st.warning(f"VideoDatabase missing columns: {missing_cols}")
        return

    # Filter to see which rows still need downloading
    needing_download = df_videos[df_videos["downloaded y/n/c"] == "N"]
    st.write(f"Found {len(needing_download)} rows => 'N' => need download.")
    st.dataframe(needing_download, use_container_width=True)

    # ---------- DOWNLOAD ALL MISSING BUTTON ----------
    if st.button("Download All Missing"):
        st.write("Downloading + uploading to Drive + storing local_path...")

        drive_service = get_drive_service()
        if not drive_service:
            st.error("Failed Drive auth.")
            return

        updated_count = 0
        for i, row in needing_download.iterrows():
            vid_id = row["ID"]
            vid_url = row["video_url"]
            platform = row.get("platform", "unknown")

            st.write(f"Downloading: ID={vid_id}, url={vid_url}")
            local_path = download_to_local(vid_url, platform)
            if not local_path:
                st.error(f"Download failed for {vid_url}")
                df_videos.at[i, "downloaded y/n/c"] = "C"
                continue

            file_id = upload_to_drive(drive_service, local_path, platform)
            if not file_id:
                st.error(f"Upload to Drive failed for {local_path}")
                df_videos.at[i, "downloaded y/n/c"] = "C"
                continue

            share_link = make_file_public(drive_service, file_id)
            df_videos.at[i, "download_url"] = share_link
            df_videos.at[i, "local_path"] = local_path
            df_videos.at[i, "downloaded y/n/c"] = "Y"
            st.success(f"Uploaded => {share_link}")
            updated_count += 1

        if updated_count > 0:
            write_sheet(spreadsheet_id, scraped_videos_sheet, df_videos)
            st.success(f"Updated {updated_count} rows in '{scraped_videos_sheet}'.")
        else:
            st.info("No videos updated.")

# ---------- BELOW: Helper functions for download ----------
def download_to_local(video_url, platform):
    from pathlib import Path

    local_folder = PLATFORM_LOCAL_DIRS.get(platform, PLATFORM_LOCAL_DIRS["unknown"])
    Path(local_folder).mkdir(parents=True, exist_ok=True)

    outtmpl = str(Path(local_folder) / '%(title)s.%(ext)s')
    cookie_file = "/Users/tylergrabowski/scripts/social_media_manager/src/scrapers/twitter_cookies.txt"

    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': outtmpl,
        'quiet': True,
        'no_warnings': True,
        'cookiefile': cookie_file,
        'http_headers': {
            'User-Agent': (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            )
        }
    }
    try:
        from yt_dlp import YoutubeDL
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            final_path = ydl.prepare_filename(info)
        logging.info(f"Downloaded {video_url} => {final_path}")
        return final_path
    except Exception as e:
        logging.error(f"Download error {video_url}: {e}")
        return None

def upload_to_drive(drive_service, local_path, platform):
    folder_id = PLATFORM_DRIVE_FOLDERS.get(platform, PLATFORM_DRIVE_FOLDERS["unknown"])
    filename = os.path.basename(local_path)
    file_metadata = {
        'name': filename,
        'parents': [folder_id]
    }
    try:
        media = MediaFileUpload(local_path, resumable=True)
        created = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        file_id = created.get('id')
        logging.info(f"Uploaded {local_path} => fileId={file_id}")
        return file_id
    except Exception as e:
        logging.error(f"Failed upload {local_path} to Drive: {e}")
        return None

def make_file_public(drive_service, file_id):
    try:
        drive_service.permissions().create(
            fileId=file_id,
            body={'role': 'reader', 'type': 'anyone'},
            fields='id'
        ).execute()
        return f"https://drive.google.com/file/d/{file_id}/view"
    except Exception as e:
        logging.error(f"Failed to make file public: {e}")
        return f"fileId={file_id}"