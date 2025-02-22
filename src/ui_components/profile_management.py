# ui_components/profile_management.py

import streamlit as st
import pandas as pd
import requests
import traceback
from datetime import datetime
from utils.sheets import read_sheet, write_sheet

def profile_management_ui(spreadsheet_id: str, sheet_profiles: str, sheet_videos: str, zapier_webhook_url=None):
    st.header("Profile Management")
    
    # 1) Load profiles
    df_profiles = read_sheet(spreadsheet_id, sheet_profiles)
    if df_profiles.empty:
        df_profiles = pd.DataFrame(columns=["profile_id","profile_name","niche_name","active","date_created"])
    
    st.subheader("Managed Profiles")
    if not df_profiles.empty:
        st.dataframe(df_profiles, use_container_width=True)
    else:
        st.info("No profiles found.")
    
    st.subheader("Create New Profile")
    col1, col2 = st.columns(2)
    with col1:
        new_profile_name = st.text_input("Profile Name")
    with col2:
        # Optionally read from "Niches" sheet
        df_niches = read_sheet(spreadsheet_id, "Niches")
        niche_list = df_niches["niche_name"].tolist() if not df_niches.empty else []
        chosen_niche = st.selectbox("Link to Niche", ["(None)"] + niche_list)
    
    if st.button("Add Profile"):
        if new_profile_name.strip():
            new_id = str(len(df_profiles)+1)
            row_dict = {
                "profile_id": new_id,
                "profile_name": new_profile_name.strip(),
                "niche_name": chosen_niche if chosen_niche != "(None)" else "",
                "active": "True",
                "date_created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            df_profiles = df_profiles.append(row_dict, ignore_index=True)
            write_sheet(spreadsheet_id, sheet_profiles, df_profiles)
            st.success("Profile created!")
            st.experimental_rerun()
        else:
            st.warning("Please enter a valid profile name.")
    
    st.write("---")
    
    # 2) "Twitter-like" feed for chosen profile
    st.subheader("Manage Posts in a 'Twitter-Like' Feed")
    
    active_profiles = df_profiles[df_profiles["active"] == "True"]
    if active_profiles.empty:
        st.info("No active profiles.")
        return
    
    selected_profile = st.selectbox("Select Profile to Manage", active_profiles["profile_name"].tolist())
    row_profile = active_profiles[active_profiles["profile_name"] == selected_profile].iloc[0]
    profile_niche = row_profile["niche_name"]
    
    st.write(f"Linked Niche: **{profile_niche}**")
    
    # Load "VideoDatabase"
    df_videos = read_sheet(spreadsheet_id, sheet_videos)
    if df_videos.empty:
        st.info("No videos yet in the VideoDatabase sheet.")
        return
    
    # Filter unposted
    if "niche" in df_videos.columns:
        pending_videos = df_videos[(df_videos["niche"] == profile_niche) & (df_videos["uploaded_yn"] != "Y")]
    else:
        # fallback
        pending_videos = df_videos[df_videos["uploaded_yn"] != "Y"]
    
    if pending_videos.empty:
        st.info("No unposted videos for this niche!")
        return
    
    st.write(f"Found {len(pending_videos)} unposted videos.")
    
    for i, row in pending_videos.iterrows():
        st.markdown("---")
        st.write(f"**Video ID**: {row.get('id','')}")
        st.write(f"**Source URL**: {row.get('video_url','')}")
        
        # Attempt Google Drive embed
        if row.get("download_url","").startswith("https://drive.google.com"):
            try:
                file_id = row["download_url"].split("/d/")[1].split("/view")[0]
                embed_html = f"""
                    <iframe 
                        src="https://drive.google.com/file/d/{file_id}/preview" 
                        width="600" 
                        height="340"
                        allow="autoplay"
                    ></iframe>
                """
                st.components.v1.html(embed_html, height=340)
            except:
                st.write(f"[View Video]({row['download_url']})")
        else:
            if row.get("download_url"):
                st.write(f"[View Video]({row['download_url']})")
        
        # Edit caption
        default_caption = row.get("caption","")
        new_caption = st.text_area("Caption", default_caption, key=f"cap_{row.get('id','')}", max_chars=280)
        
        # Scheduling
        colA, colB = st.columns(2)
        with colA:
            schedule_date = st.date_input("Schedule Date", datetime.now().date(), key=f"date_{row.get('id','')}")
        with colB:
            schedule_time = st.time_input("Schedule Time", datetime.now().time(), key=f"time_{row.get('id','')}")
        
        if st.button("Schedule/Post", key=f"schedule_{row.get('id','')}"):
            post_data = {
                "caption": new_caption,
                "media_path": row.get("download_url",""),
                "schedule_date": schedule_date.strftime("%Y-%m-%d"),
                "schedule_time": schedule_time.strftime("%H:%M"),
                "platform": row.get("platform","twitter")
            }
            
            if zapier_webhook_url:
                try:
                    resp = requests.post(zapier_webhook_url, json={"post": post_data})
                    if resp.status_code == 200:
                        st.success("Post scheduled successfully!")
                        
                        # Mark in sheet
                        df_videos.at[i,"uploaded_yn"] = "Y"
                        df_videos.at[i,"time_uploaded"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df_videos.at[i,"caption"] = new_caption
                        write_sheet(spreadsheet_id, sheet_videos, df_videos)
                    else:
                        st.error(f"Failed to schedule: {resp.text}")
                except Exception as e:
                    st.error(f"Error scheduling: {e}")
                    st.code(traceback.format_exc())
            else:
                st.warning("No Zapier/Webhook URL configured.")
