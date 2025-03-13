#!/usr/bin/env python3
"""
scheduled_poster.py
A background/cron script that:
1) Reads the "VideoDatabase" in Google Sheets
2) Finds rows with posted='S' && schedule_date_time <= now
3) Posts them to Twitter
4) Updates posted='Y' on success
"""

import os
import time
import mimetypes
import requests
from requests_oauthlib import OAuth1
from datetime import datetime
import tweepy

# Import from your local "utils.sheets" module
from utils.sheets import read_sheet, write_sheet

###############################################################################
# CONFIGURE THESE AS NEEDED
###############################################################################
SPREADSHEET_ID = "10LBqtOn9DZ1_fV_03MPUZJZq7lTTMTOwcbg8GE7wiBg"  # your real GSheet ID
PROFILES_SHEET_NAME = "Profiles"
VIDEO_SHEET_NAME = "VideoDatabase"

CONSUMER_KEY = "iJWS5YljBzHoGDP9ln9sMo3hC"
CONSUMER_SECRET = "0Z3EPje9jLY7spaj9IH2SKPkl5b2BaaLJlcbxwpKmaN61IYW0m"

def upload_media_chunked_1_1(access_token, access_secret, file_path):
    """
    Performs chunked video upload to Twitter (v1.1).
    Returns a media_id string if successful, else None.
    """
    if not file_path or not os.path.isfile(file_path):
        print(f"[ERROR] File not found => {file_path}")
        return None

    with open(file_path, "rb") as f:
        data = f.read()

    total_bytes = len(data)
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    oauth = OAuth1(CONSUMER_KEY, CONSUMER_SECRET, access_token, access_secret)
    upload_url = "https://upload.twitter.com/1.1/media/upload.json"

    # 1) INIT
    init_data = {
        "command": "INIT",
        "total_bytes": total_bytes,
        "media_type": mime_type,
        "media_category": "tweet_video"
    }
    r_init = requests.post(upload_url, data=init_data, auth=oauth)
    if r_init.status_code not in (200, 201, 202):
        print(f"[ERROR] INIT => {r_init.status_code} {r_init.text}")
        return None
    media_id = r_init.json().get("media_id_string")
    if not media_id:
        print(f"[ERROR] No media_id in INIT => {r_init.text}")
        return None

    # 2) APPEND (send in chunks)
    chunk_size = 4 * 1024 * 1024  # 4MB
    segment_index = 0
    index = 0
    while index < total_bytes:
        chunk = data[index:index+chunk_size]
        files = {"media": ("filename", chunk)}
        append_data = {
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": segment_index
        }
        r_append = requests.post(upload_url, data=append_data, files=files, auth=oauth)
        if r_append.status_code not in (200, 201, 202, 204):
            print(f"[ERROR] APPEND => {r_append.status_code} {r_append.text}")
            return None

        index += chunk_size
        segment_index += 1

    # 3) FINALIZE
    fin_data = {"command": "FINALIZE", "media_id": media_id}
    r_fin = requests.post(upload_url, data=fin_data, auth=oauth)
    if r_fin.status_code not in (200, 201, 202):
        print(f"[ERROR] FINALIZE => {r_fin.status_code} {r_fin.text}")
        return None

    # Poll if Twitter is still processing the video
    fin_json = r_fin.json()
    proc_info = fin_json.get("processing_info")
    while proc_info and proc_info.get("state") in ["pending", "in_progress"]:
        secs = proc_info.get("check_after_secs", 5)
        time.sleep(secs)
        r_check = requests.get(upload_url, params={"command":"STATUS","media_id":media_id}, auth=oauth)
        if r_check.status_code not in (200, 201, 202):
            print(f"[ERROR] STATUS => {r_check.status_code} {r_check.text}")
            return None
        proc_info = r_check.json().get("processing_info", {})
        if proc_info.get("state") == "failed":
            error_msg = proc_info.get("error", {}).get("message", "Unknown error")
            print(f"[ERROR] Video processing failed => {error_msg}")
            return None

    print(f"[INFO] Chunked upload complete => media_id={media_id}")
    return media_id

def post_tweet_v2(profile_name, text, access_token, access_secret, media_ids=None):
    """
    Posts a Tweet using Twitter API v2 (Tweepy.Client).
    Returns True if success, False if error.
    """
    print(f"[INFO] Posting tweet => {profile_name}, text={text[:30]}..., media_ids={media_ids or 'none'}")
    try:
        client = tweepy.Client(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=access_token,
            access_token_secret=access_secret
        )
        if media_ids:
            response = client.create_tweet(text=text, media_ids=media_ids)
        else:
            response = client.create_tweet(text=text)
        tweet_id = response.data.get("id")
        print(f"[INFO] Posted tweet => tweet_id={tweet_id}")
        return True
    except Exception as e:
        print(f"[ERROR] Tweet error => {e}")
        return False

def main():
    print("[INFO] scheduled_poster.py starting...")
    # 1) Load Profiles + Videos from Google Sheets
    df_profiles = read_sheet(SPREADSHEET_ID, PROFILES_SHEET_NAME)
    df_videos = read_sheet(SPREADSHEET_ID, VIDEO_SHEET_NAME)

    if df_videos.empty:
        print("[INFO] No rows in VideoDatabase, exiting.")
        return

    # 2) Filter rows => posted='S' AND schedule_date_time <= now
    now_utc = datetime.utcnow()
    rows_to_post = []
    for idx, row in df_videos.iterrows():
        if row.get("posted") == "S":
            sched_str = row.get("schedule_date_time", "")
            if sched_str:
                try:
                    sched_dt = datetime.strptime(sched_str, "%Y-%m-%d %H:%M:%S")
                    if sched_dt <= now_utc:
                        rows_to_post.append(idx)
                except:
                    # If parse fails, ignore or log
                    pass

    if not rows_to_post:
        print("[INFO] No scheduled posts due right now.")
        return

    print(f"[INFO] Found {len(rows_to_post)} video(s) to post...")

    # 3) For each due row, upload + post
    for idx in rows_to_post:
        row_data = df_videos.loc[idx]
        video_id = row_data.get("ID", "")
        local_path = row_data.get("local_path", "")
        caption = row_data.get("caption", "")
        niche = row_data.get("niche", "")

        # Match a profile by niche (or pick your own logic)
        matching_profiles = df_profiles[df_profiles["niche_name"] == niche]
        if matching_profiles.empty:
            print(f"[WARNING] No profile with niche='{niche}', skipping video ID={video_id}.")
            continue

        # Use the first matched profile
        prof = matching_profiles.iloc[0]
        prof_name = prof["profile_name"]
        acc_tok = prof["access_token"]
        acc_sec = prof["access_token_secret"]

        # 4) Chunked upload
        if local_path:
            media_id = upload_media_chunked_1_1(acc_tok, acc_sec, local_path)
            if not media_id:
                print(f"[ERROR] Chunk upload failed => skipping ID={video_id}")
                continue
            posted_ok = post_tweet_v2(prof_name, caption, acc_tok, acc_sec, [media_id])
        else:
            # If no local_path => maybe do text-only post or skip
            posted_ok = post_tweet_v2(prof_name, caption, acc_tok, acc_sec, media_ids=None)

        # 5) Update row
        if posted_ok:
            df_videos.at[idx, "posted"] = "Y"
            df_videos.at[idx, "time_uploaded"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[INFO] Video ID={video_id} posted successfully. Marked posted='Y'.")
        else:
            print(f"[ERROR] Posting failed. ID={video_id} remains posted='S'")

    # 6) Write updates back to Google Sheets
    write_sheet(SPREADSHEET_ID, VIDEO_SHEET_NAME, df_videos)
    print("[INFO] Done updating GSheet. Exiting scheduled_poster.py.")

if __name__ == "__main__":
    main()