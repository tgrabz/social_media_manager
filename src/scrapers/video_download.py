#!/usr/bin/env python

import os
import logging
import tempfile
from pathlib import Path

import pandas as pd
from yt_dlp import YoutubeDL

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from utils.sheets import read_sheet, write_sheet

# Updated path to the new JSON location:
SERVICE_ACCOUNT_FILE = "src/config/service-account-key.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

SPREADSHEET_ID = "10LBqtOn9DZ1_fV_03MPUZJZq7lTTMTOwcbg8GE7wiBg"
VIDEO_SHEET_NAME = "VideoDatabase"

PLATFORM_DRIVE_FOLDERS = {
    "twitter": "1eVuW0TUv_aApUc8Cb7oV4l0QD4zkR7V8",
    "instagram": "1OFVnrUhwijo9o25GBUNNGiBmgpmMuESY",
    "tiktok": "1Qgc5JFMY_XGrrZt146HDPBrE-w8jhH4R",
    "unknown": "DefaultFolderIDIfDesired"
}

logging.basicConfig(
    filename="video_download.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def main():
    # 1) Read VideoDatabase
    df = read_sheet(SPREADSHEET_ID, VIDEO_SHEET_NAME)
    if df.empty:
        print("No data in VideoDatabase.")
        return

    required = ["video_url", "download_url", "platform"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        print(f"Missing columns: {missing} in VideoDatabase. Please fix and re-run.")
        return

    # We'll process rows where download_url is empty or NaN.
    to_download = df[(df["download_url"] == "") | (df["download_url"].isna())]
    if to_download.empty:
        print("No videos need downloading/uploading.")
        return

    print(f"Found {len(to_download)} videos to process...")

    drive_service = get_drive_service()
    if not drive_service:
        print("Failed to auth Drive service.")
        return

    for i, row in to_download.iterrows():
        video_url = row["video_url"]
        platform = row.get("platform","unknown")
        print(f"\nProcessing row index={i}, video_url={video_url}")
        print(f"DEBUG: platform from sheet => '{platform}'")

        local_path = download_temp(video_url)
        if not local_path:
            logging.error(f"Failed to download {video_url}")
            continue

        # Record local_path in the DataFrame
        df.at[i, "local_path"] = local_path
        print(f"Local path recorded => {local_path}")
        logging.info(f"Local path recorded => {local_path}")

        drive_id = upload_to_drive(drive_service, local_path, platform)
        if not drive_id:
            logging.error(f"Failed to upload {local_path}")
            continue

        share_link = make_file_public(drive_service, drive_id)
        df.at[i, "download_url"] = share_link

        print(f"Updated row {i} => download_url={share_link}")
        logging.info(f"Updated row {i} => download_url={share_link}")

    write_sheet(SPREADSHEET_ID, VIDEO_SHEET_NAME, df)
    print("\nAll done updating the sheet. Local paths + share links recorded.")

def download_temp(video_url):
    """
    Download using yt_dlp with the X cookies file.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, '%(title)s.%(ext)s')

            # Use the same absolute path as scraper.py
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
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                local_path = ydl.prepare_filename(info)
            return local_path
    except Exception as e:
        logging.error(f"Error downloading {video_url}: {e}")
        return None

def upload_to_drive(drive_service, local_path, platform):
    folder_id = PLATFORM_DRIVE_FOLDERS.get(platform, PLATFORM_DRIVE_FOLDERS["unknown"])
    print(f"DEBUG: Using folder_id={folder_id} for platform='{platform}'")

    filename = Path(local_path).name
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
        logging.error(f"Failed to upload {local_path} to Drive: {e}")
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

if __name__ == "__main__":
    main()