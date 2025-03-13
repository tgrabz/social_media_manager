import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta, date, time
import tweepy
import requests
from requests_oauthlib import OAuth1

from utils.sheets import read_sheet, write_sheet

CONSUMER_KEY = "iJWS5YljBzHoGDP9ln9sMo3hC"
CONSUMER_SECRET = "0Z3EPje9jLY7spaj9IH2SKPkl5b2BaaLJlcbxwpKmaN61IYW0m"
CALLBACK_URL = "http://localhost:8501/?twitter_callback=1"

def load_profiles_once(spreadsheet_id, sheet_profiles):
    if "profiles_df" not in st.session_state:
        st.session_state["profiles_df"] = read_sheet(spreadsheet_id, sheet_profiles)
    return st.session_state["profiles_df"]

def refresh_profiles(spreadsheet_id, sheet_profiles):
    df = read_sheet(spreadsheet_id, sheet_profiles)
    st.session_state["profiles_df"] = df
    return df

def load_videos_once(spreadsheet_id, sheet_videos):
    if "videos_df" not in st.session_state:
        st.session_state["videos_df"] = read_sheet(spreadsheet_id, sheet_videos)
    return st.session_state["videos_df"]

def refresh_videos(spreadsheet_id, sheet_videos):
    df = read_sheet(spreadsheet_id, sheet_videos)
    st.session_state["videos_df"] = df
    return df

def save_videos(spreadsheet_id, sheet_videos, df):
    write_sheet(spreadsheet_id, sheet_videos, df)
    st.session_state["videos_df"] = df.copy()

def create_new_profile(spreadsheet_id, sheet_profiles):
    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, callback=CALLBACK_URL)
    try:
        redirect_url = auth.get_authorization_url()
    except Exception as e:
        st.error(f"Error obtaining request token: {e}")
        return

    oauth_token = auth.request_token["oauth_token"]
    oauth_token_secret = auth.request_token["oauth_token_secret"]

    df_profiles = load_profiles_once(spreadsheet_id, sheet_profiles)
    if df_profiles.empty:
        df_profiles = pd.DataFrame(columns=["profile_id","profile_name","niche_name","access_token","access_token_secret"])

    new_row = {
        "profile_id": oauth_token,
        "profile_name": "PENDING",
        "niche_name": "",
        "access_token": oauth_token,
        "access_token_secret": oauth_token_secret
    }
    df_profiles = pd.concat([df_profiles, pd.DataFrame([new_row])], ignore_index=True)
    write_sheet(spreadsheet_id, sheet_profiles, df_profiles)
    st.session_state["profiles_df"] = df_profiles.copy()

    st.info(f"Inserted ephemeral row => {oauth_token} = 'PENDING'")
    st.markdown(f"[**Authorize with X**]({redirect_url})", unsafe_allow_html=True)

def finalize_profile_oauth(spreadsheet_id, sheet_profiles):
    q = st.experimental_get_query_params()
    oauth_token = q.get("oauth_token",[None])[0]
    oauth_verifier = q.get("oauth_verifier",[None])[0]
    if not oauth_token or not oauth_verifier:
        st.warning("No oauth_token/verifier => cannot finalize.")
        return

    if "profiles_df" in st.session_state:
        df_profiles = st.session_state["profiles_df"]
    else:
        df_profiles = read_sheet(spreadsheet_id, sheet_profiles)

    match_idx = df_profiles.index[df_profiles["profile_id"] == oauth_token]
    if match_idx.empty:
        st.error(f"No ephemeral row found for {oauth_token}")
        return

    rownum = match_idx[0]
    ephemeral_secret = df_profiles.at[rownum, "access_token_secret"]

    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.request_token = {
        "oauth_token": oauth_token,
        "oauth_token_secret": ephemeral_secret
    }
    try:
        access_token, access_secret = auth.get_access_token(oauth_verifier)
        st.success("Tokens obtained; verifying…")
    except Exception as e:
        st.error(f"Error obtaining final tokens: {e}")
        return

    api = tweepy.API(auth)
    try:
        user_info = api.verify_credentials()
        screen_name = user_info.screen_name
        st.success(f"Authorized as @{screen_name}")
    except Exception as e:
        st.error(f"Verify credentials error => {e}")
        return

    df_profiles.at[rownum, "profile_name"] = screen_name
    df_profiles.at[rownum, "access_token"] = access_token
    df_profiles.at[rownum, "access_token_secret"] = access_secret

    write_sheet(spreadsheet_id, sheet_profiles, df_profiles)
    st.session_state["profiles_df"] = df_profiles.copy()
    st.info(f"Ephemeral row => {oauth_token} updated to '@{screen_name}'")

def upload_media_chunked_1_1(access_token, access_secret, file_path):
    import time, mimetypes
    from requests_oauthlib import OAuth1

    if not file_path:
        st.error("No local file path for chunked upload!")
        return None
    if not os.path.isfile(file_path):
        st.error(f"File not found => {file_path}")
        return None

    st.write(f"DEBUG: chunked upload => {file_path}")
    try:
        with open(file_path,"rb") as f:
            data = f.read()
    except Exception as e:
        st.error(f"Error reading file => {e}")
        return None

    total_bytes = len(data)
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    oauth = OAuth1(CONSUMER_KEY, CONSUMER_SECRET, access_token, access_secret)
    url = "https://upload.twitter.com/1.1/media/upload.json"

    # INIT
    init_data = {
        "command": "INIT",
        "total_bytes": total_bytes,
        "media_type": mime_type,
        "media_category": "tweet_video"
    }
    r_init = requests.post(url, data=init_data, auth=oauth)
    if r_init.status_code not in (200,201,202):
        st.error(f"INIT error => {r_init.status_code}, {r_init.text}")
        return None
    media_id = r_init.json().get("media_id_string")
    if not media_id:
        st.error(f"No media_id in INIT => {r_init.text}")
        return None

    # APPEND
    seg_size = 4*1024*1024
    idx = 0
    seg_idx = 0
    while idx < total_bytes:
        chunk = data[idx:idx+seg_size]
        files = {"media":("filename", chunk)}
        append_data = {
            "command":"APPEND",
            "media_id": media_id,
            "segment_index": seg_idx
        }
        r_append = requests.post(url, data=append_data, files=files, auth=oauth)
        if r_append.status_code not in (200,201,202,204):
            st.error(f"APPEND error => {r_append.status_code}, {r_append.text}")
            return None
        idx += seg_size
        seg_idx += 1

    # FINALIZE
    fin_data = {"command":"FINALIZE","media_id":media_id}
    r_fin = requests.post(url, data=fin_data, auth=oauth)
    if r_fin.status_code not in (200,201,202):
        st.error(f"FINALIZE error => {r_fin.status_code}, {r_fin.text}")
        return None

    fin_json = r_fin.json()
    proc = fin_json.get("processing_info")
    if proc:
        state = proc.get("state")
        wait_sec = proc.get("check_after_secs",5)
        while state in ["pending","in_progress"]:
            time.sleep(wait_sec)
            r_stat = requests.get(url, params={"command":"STATUS","media_id":media_id}, auth=oauth)
            if r_stat.status_code not in (200,201,202):
                st.error(f"STATUS error => {r_stat.status_code}, {r_stat.text}")
                return None
            proc = r_stat.json().get("processing_info",{})
            state = proc.get("state")
            wait_sec = proc.get("check_after_secs",5)
            if state == "failed":
                err_msg = proc.get("error",{}).get("message","Unknown error")
                st.error(f"Video processing failed => {err_msg}")
                return None
        if state != "succeeded":
            st.error(f"Unexpected final state => {state}")
            return None

    st.write(f"Chunked upload => media_id={media_id}")
    return media_id

def post_tweet_v2(screen_name, text, access_token, access_secret, media_ids=None):
    st.write(f"Tweet => user={screen_name}, text={text[:30]}..., media_ids={media_ids}")
    try:
        import tweepy
        client = tweepy.Client(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=access_token,
            access_token_secret=access_secret
        )
        if media_ids:
            resp = client.create_tweet(text=text, media_ids=media_ids)
        else:
            resp = client.create_tweet(text=text)
        tid = resp.data.get("id")
        st.write(f"Posted tweet => ID={tid}")
        return True
    except Exception as e:
        st.error(f"Tweet error => {e}")
        return False

def profile_management_ui(spreadsheet_id: str, sheet_profiles: str, sheet_videos: str, inventory_sheet: str):
    # Handle Twitter callback if present
    q = st.experimental_get_query_params()
    if "twitter_callback" in q:
        finalize_profile_oauth(spreadsheet_id, sheet_profiles)

    st.title("Profile Management — Append new account/time if already posted")

    if st.button("Create New Profile"):
        create_new_profile(spreadsheet_id, sheet_profiles)

    st.write("---")
    st.subheader("Profiles")

    df_profiles = load_profiles_once(spreadsheet_id, sheet_profiles)
    if st.button("Refresh Profiles"):
        df_profiles = refresh_profiles(spreadsheet_id, sheet_profiles)
        st.success("Profiles reloaded.")

    if df_profiles.empty:
        st.info("No profiles found.")
        return

    st.dataframe(df_profiles, use_container_width=True)

    prof_names = df_profiles["profile_name"].tolist()
    selected_profile = st.selectbox("Select Profile", prof_names)
    rowp = df_profiles[df_profiles["profile_name"] == selected_profile].iloc[0]

    prof_id = rowp["profile_id"]
    niche = rowp["niche_name"]
    acc_tok = rowp["access_token"]
    acc_sec = rowp["access_token_secret"]

    st.write(f"**Profile ID**: {prof_id}")
    st.write(f"**Niche**: {niche}")

    if selected_profile == "PENDING":
        st.warning("Profile is 'PENDING'. Finish or remove.")
        return
    if not acc_tok or not acc_sec:
        st.warning("No tokens. Provide them or re-run OAuth.")
        return

    # Simple text tweet
    st.write("### Quick Text Tweet")
    quick_txt = st.text_area("Compose text", value="Hello from appended approach!")
    if st.button("Post Quick Tweet"):
        posted = post_tweet_v2(selected_profile, quick_txt, acc_tok, acc_sec)
        if posted:
            st.success("Text tweet posted!")

    st.write("---")
    st.subheader("Videos (Append Profile in 'account uploaded to')")

    df_videos = load_videos_once(spreadsheet_id, sheet_videos)
    if st.button("Refresh Videos"):
        df_videos = refresh_videos(spreadsheet_id, sheet_videos)
        st.success("Videos reloaded from Sheets.")

    if df_videos.empty:
        st.info("No data in 'VideoDatabase'.")
        return

    # Ensure columns for scheduling
    needed_cols = ["posted","schedule_date_time"]
    for c in needed_cols:
        if c not in df_videos.columns:
            st.warning(f"Missing column '{c}' in VideoDatabase. Please add it.")
            return

    # ------------------------------
    # FILTER: show only unscheduled (posted != 'S') + niche + downloaded='Y'
    # ------------------------------
    mask_niche = (df_videos["niche"] == niche)
    mask_dl = (df_videos["downloaded y/n/c"] == "Y")
    mask_not_scheduled = (df_videos["posted"] != "S")
    filter_vids = df_videos[mask_niche & mask_dl & mask_not_scheduled]

    if filter_vids.empty:
        st.info(f"No downloaded, unscheduled videos for niche={niche}.")
        return

    import streamlit.components.v1 as components

    for i, row in filter_vids.iterrows():
        st.markdown("---")
        vid_id = row.get("ID","")
        local_path = row.get("local_path","")
        db_caption = row.get("caption","")
        dl_url = row.get("download_url","")
        acct_list = row.get("account uploaded to","")
        time_list = row.get("time uploaded","")

        st.write(f"**Video ID**: {vid_id}")
        st.write(f"Local Path => {local_path}")
        st.write(f"Caption => {db_caption or '(none)'}")
        st.write(f"Already posted to => {acct_list or '(none)'}")
        st.write(f"Times => {time_list or '(none)'}")

        # Possibly embed Google Drive preview
        if isinstance(dl_url, str) and "drive.google.com/file/d/" in dl_url:
            try:
                file_id = dl_url.split("/d/")[1].split("/view")[0]
                embed_html = f"""
                <iframe 
                    src="https://drive.google.com/file/d/{file_id}/preview"
                    width="600"
                    height="340"
                    allow="autoplay"
                ></iframe>
                """
                components.html(embed_html, height=340)
            except:
                st.write(f"[View on Drive]({dl_url})")
        elif isinstance(dl_url, str) and dl_url.startswith("http"):
            st.write(f"[View/Download Link]({dl_url})")

        cap_key = f"typed_cap_{vid_id}"
        if cap_key not in st.session_state:
            st.session_state[cap_key] = db_caption
        typed_cap = st.text_area(f"Type new caption for ID={vid_id}", key=cap_key)

        if st.button(f"Save Caption {vid_id}"):
            df_videos.at[i,"caption"] = typed_cap
            save_videos(spreadsheet_id, sheet_videos, df_videos)
            st.success(f"Caption saved => {typed_cap}")

        # CHUNK & POST
        if st.button(f"Chunk & Post {vid_id}"):
            final_cap = df_videos.at[i,"caption"]
            if not local_path:
                st.error("No local_path => can't chunk upload.")
                continue

            media_id = upload_media_chunked_1_1(acc_tok, acc_sec, local_path)
            if media_id:
                posted_ok = post_tweet_v2(selected_profile, final_cap, acc_tok, acc_sec, media_ids=[media_id])
                if posted_ok:
                    old_accts = df_videos.at[i,"account uploaded to"] or ""
                    old_times = df_videos.at[i,"time uploaded"] or ""
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    acct_list_clean = [a.strip() for a in old_accts.split(",") if a.strip()]
                    if selected_profile not in acct_list_clean:
                        acct_list_clean.append(selected_profile)
                    new_accts = ", ".join(acct_list_clean)

                    time_list_clean = [t.strip() for t in old_times.split(",") if t.strip()]
                    time_list_clean.append(now_str)
                    new_times = ", ".join(time_list_clean)

                    df_videos.at[i,"account uploaded to"] = new_accts
                    df_videos.at[i,"time uploaded"] = new_times
                    df_videos.at[i,"posted"] = "Y"  # Mark as posted

                    save_videos(spreadsheet_id, sheet_videos, df_videos)
                    st.success(f"Uploaded & posted video ID={vid_id}. Appended '{selected_profile}' => {new_accts}")
                else:
                    st.error(f"Tweet post failed for ID={vid_id}")

        # --------
        # SCHEDULING
        # --------
        posted_val = row.get("posted","N")
        sched_str  = row.get("schedule_date_time","")

        st.write("**Scheduling** (set `posted='S'` + choose date/time)")

        # default
        default_dt = datetime.now()
        if sched_str:
            try:
                default_dt = datetime.strptime(sched_str, "%Y-%m-%d %H:%M:%S")
            except:
                pass

        date_val = st.date_input(f"Date for {vid_id}:", value=default_dt.date())
        time_val = st.time_input(f"Time for {vid_id}:", value=default_dt.time())

        if st.button(f"Save Schedule for {vid_id}"):
            df_videos.at[i,"posted"] = "S"
            combined_dt = datetime.combine(date_val, time_val)
            df_videos.at[i,"schedule_date_time"] = combined_dt.strftime("%Y-%m-%d %H:%M:%S")
            save_videos(spreadsheet_id, sheet_videos, df_videos)
            st.success(f"ID={vid_id} => posted='S', scheduled time set to {combined_dt}")

    # ----------------------------
    # SCHEDULED VIDEOS SECTION
    # ----------------------------
    st.write("### Currently Scheduled (posted='S')")
    df_s = df_videos[df_videos["posted"]=="S"].copy()
    if df_s.empty:
        st.info("No scheduled videos found (posted='S').")
    else:
        st.dataframe(df_s, use_container_width=True)
        if st.button("Unschedule All (posted='S')"):
            df_videos.loc[df_videos["posted"]=="S", ["posted","schedule_date_time"]] = ["N",""]
            save_videos(spreadsheet_id, sheet_videos, df_videos)
            st.success("All scheduled => now posted='N' + cleared schedule_date_time.")