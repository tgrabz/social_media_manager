#!/usr/bin/env python3
"""
scheduled_poster.py
-------------------
1) Reads the "VideoDatabase" in Google Sheets
2) Finds rows where posted='S' && schedule_date_time <= now
3) Posts them to Twitter
4) Updates posted='Y'
"""

import os
import sys
from datetime import datetime
import traceback

# If your project structure has a "utils" folder for sheets:
from utils.sheets import read_sheet, write_sheet

# If you have a chunked upload function or a direct post function:
# from src.ui_components.profile_management_ui import upload_media_chunked_1_1, post_tweet_v2
import tweepy

############################
# CONFIGURATIONS
############################
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"
VIDEO_SHEET_NAME = "VideoDatabase"
PROFILES_SHEET_NAME = "Profiles"

CONSUMER_KEY = "YOUR_TWITTER_APP_CONSUMER_KEY"
CONSUMER_SECRET = "YOUR_TWITTER_APP_CONSUMER_SECRET"

def main():
    print("[INFO] scheduled_poster.py starting...")

    # 1) Read the video sheet
    df_videos = read_sheet(SPREADSHEET_ID, VIDEO_SHEET_NAME)
    if df_videos.empty:
        print("[INFO] No rows in VideoDatabase, exiting.")
        return

    # 2) Find rows posted='S' && schedule_date_time <= now
    now_utc = datetime.utcnow()
    rows_to_post = []
    for idx, row in df_videos.iterrows():
        if row.get("posted") == "S":
            sched_str = str(row.get("schedule_date_time", ""))
            if sched_str:
                try:
                    sched_dt = datetime.strptime(sched_str, "%Y-%m-%d %H:%M:%S")
                    if sched_dt <= now_utc:
                        rows_to_post.append(idx)
                except Exception as e:
                    print(f"[WARN] Could not parse schedule_date_time='{sched_str}' for row ID={row.get('ID')}")
    
    if not rows_to_post:
        print("[INFO] No scheduled posts are due right now.")
        return

    print(f"[INFO] Found {len(rows_to_post)} items to post...")

    # 3) For each due row, post to Twitter
    #    We might need the profile info (access tokens) from the "Profiles" sheet:
    df_profiles = read_sheet(SPREADSHEET_ID, PROFILES_SHEET_NAME)

    for idx in rows_to_post:
        row_data = df_videos.loc[idx]
        video_id = row_data.get("ID", "")
        niche = row_data.get("niche", "")
        local_path = row_data.get("local_path", "")
        caption = row_data.get("caption", "")
        print(f"[INFO] Attempting to post row ID={video_id}, niche={niche}")

        # (A) Decide which profile to post from. 
        #     For simplicity, let's just pick the first profile in 'Profiles' that matches the same niche
        matching_profiles = df_profiles[df_profiles["niche_name"] == niche]
        if matching_profiles.empty:
            print(f"[WARN] No matching profile for niche={niche}. Skipping ID={video_id}.")
            continue

        prof = matching_profiles.iloc[0]
        access_token = prof["access_token"]
        access_secret = prof["access_token_secret"]
        profile_name = prof["profile_name"]

        # 4) Post the video (chunked upload or normal)
        posted_ok = False
        try:
            # We'll do a quick example with Tweepy v2 chunked approach
            posted_ok = post_video_v2(caption, local_path, access_token, access_secret, profile_name)
        except Exception as e:
            print(f"[ERROR] Could not post ID={video_id}. Reason: {e}")
            traceback.print_exc()
            continue

        # 5) Update the row if posted
        if posted_ok:
            df_videos.at[idx, "posted"] = "Y"
            now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            df_videos.at[idx, "time_uploaded"] = now_str
            print(f"[INFO] Posted ID={video_id} successfully => posted='Y'")
        else:
            print(f"[ERROR] ID={video_id} failed to post => remains 'S'")

    # 6) Write updated df_videos back
    write_sheet(SPREADSHEET_ID, VIDEO_SHEET_NAME, df_videos)
    print("[INFO] Done updating GSheet. Exiting scheduled_poster.py.")

def post_video_v2(text, local_path, access_token, access_secret, profile_name):
    """
    Example function using Tweepy 4.x or 2.x (Client) chunked upload logic.
    If local_path is big or if you want a simpler approach, adapt accordingly.
    Returns True if success, else False.
    """
    if not os.path.isfile(local_path):
        print(f"[ERROR] local_path not found => {local_path}")
        return False

    print(f"[INFO] Posting as profile='{profile_name}', caption='{text[:30]}...'")
    try:
        # Create a Tweepy Client with user authentication
        import tweepy
        client = tweepy.Client(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=access_token,
            access_token_secret=access_secret
        )

        # 1) Upload media (chunked) - Tweepy auto-chunks if you call client.upload_file?
        #    If not, do a manual chunk approach. For brevity, let's do a naive approach:
        media_id = None
        with open(local_path, "rb") as f:
            media_id = client.upload_media(file=f, media_category="tweet_video")

        if not media_id:
            print("[ERROR] No media_id returned.")
            return False

        # 2) Create the tweet
        resp = client.create_tweet(text=text, media_ids=[media_id])
        tweet_id = resp.data.get("id")
        print(f"[INFO] Tweet posted => id={tweet_id}")
        return True
    except Exception as e:
        print(f"[ERROR] post_video_v2 => {e}")
        return False

if __name__ == "__main__":
    main()