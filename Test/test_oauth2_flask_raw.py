import os
import time
import threading
from datetime import datetime
from flask import Flask, request, session, redirect

###############################################################################
# 1) GOOGLE SHEETS AUTH + SCOPES
###############################################################################
import gspread
from google.oauth2.service_account import Credentials

# Inline service account JSON (for demo). For production, store securely.
SERVICE_ACCOUNT_DICT = {
    "type": "service_account",
    "project_id": "twitter-448800",
    "private_key_id": "15bfd852669d0de07880935ef9550cc4d0a9cf59",
    "private_key": """-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC4gNKwhQzCOTPy
6qC8OYCTRistDTtE76G+nRUoWhxtHMveUXru+CMRZ03UYL3dsACm6zFAPLW81Cq7
0tVW1LJ8EXFmcJKLChiY2qVZUnq9vdbAEeF5Oe6Ix08klNni1e4judHF9+/in0/Z
S7j8pLmMeDByBLPCw7peGE2xF4N8+LfkdbmNeKDOzUhCRBkuqgO3LIU5RmtOzr1h
P8I52MjE9G/4mn/pUf/GPs93S4XUa+IRlf2pH84P1wyyUmC29l+UpBz5s1/Ynr43
gBJefWKeR/jCHcp56NI4dGeg6w6TLMOQh32A7OvQUptYluWq+q3bimNT3cgooU+1
lgd7AquTAgMBAAECggEALm0kFwzzv++69bY6igKCKwzuEmEQ9/DAp4FJcKT0IDSt
zBx+raE82cU/3WAWhrEiCN6Hvx1HseNFeYu86SOOYg/VlCxhg6EfvV7PWqGZhyM8
5YnaTbHZJwvYC2F1TlH8oXrBoWoZL9JculYGj3Q3yHP55MbwIOM1gzXkXtqG2Kwj
tkdteQJMQTm/UdMKhZjRUqPlSQ3ehlPZSYWju/ypF1v6jXs8Cqg+EG16BoWH88dP
LDfSqtvrmCOGCvc4Y98eZkApSw46C1gQyvvp+ICExowJ77ffMcJ93PEf6qqdSTBF
CNOqQeO5U9sEurtPY1oU/P3yEsyyv689wwqFcq8E2QKBgQDlyZW6oOJygU2gN93V
GuOyItSquOnJUT1UsuUW+OPwWl4cxecK2hKJCtFag+D7wuWYIsz/9kXKOheCirgu
i21fiNwaGd9owgSBcqFA9B4OJZwrKuSOAVc/s4tkfiNX4DbsCw2d4Q2jZbM6hBoq
ZfQxwHUt17w0tU210wyUnwjnXQKBgQDNjNDxFfnmh2bXWQVgrWgbaRNRYc8YTvfS
/x/scXYr4vTNmDqRFNT92tbHDiecEjAiKygTMDIavzTBdS9vPRGmgANxVkfY8rXO
IaTidDjnmmweIYrAiT7yK0LxWVpZuy3g8Va+BdTk6qfwLdM2NNepB63p63xRi/pt
MCKU4kVfrwKBgQDEuxLK5qUZHaUFD++HXO8mevWSeKAHsNsOYd8LDOmxxNygS7sk
KlIGLFHS6ee8BD+nQdw7JHDZ02R/ah6IEu0ABt9SJWaFfN54qVhvkNEOkZqjxqRJ
A9LcAe7MicXenWLIMiplSeHwS8jnx2PTethXpAtuxS4n/jVa/ybdM09fLQKBgBJA
+x0t0m+CfsOJCE05mRE2F50WjomeGawHNBKPUOs80HihmDHiI7gXgxNSUnots1CV
fI2Xrhtp94lmmrvKNJMQsz2RZ/gANd0EZ9wkbhlDQW67k9LdXVWsOdmtEbT+Rmi/
hfCCHBHoNNnDeApMTwqXv/4SB4xGXgrsR2XpYjfJAoGBAM30ROTz8LRCVCSGS0CU
H89rFuxXaya76/RIDRLELVid155WdaH93SCkTXwlIB0QGGyKfAI8kits/CFX1xC/
ZYL/9vdlXkELpQ6lIZZxEVMfvoqruoG8DcytYGOet+HpjR+8+MMyPzIgZhYIkoAF
09osOCJKNTnwwfNaBCTmuyWM
-----END PRIVATE KEY-----
""",
    "client_email": "storage-access@twitter-448800.iam.gserviceaccount.com",
    "client_id": "101529350631397405718",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/storage-access@twitter-448800.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com"
}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds = Credentials.from_service_account_info(SERVICE_ACCOUNT_DICT, scopes=SCOPES)
gc = gspread.authorize(creds)

###############################################################################
# 2) OPEN THE SPREADSHEET + GET WORKSHEETS
###############################################################################
SPREADSHEET_NAME = "SocialPilot"
USERS_WORKSHEET_NAME = "Users"
SCHEDULED_WORKSHEET_NAME = "ScheduledTweets"

sh = gc.open(SPREADSHEET_NAME)
users_sheet = sh.worksheet(USERS_WORKSHEET_NAME)
tweets_sheet = sh.worksheet(SCHEDULED_WORKSHEET_NAME)

###############################################################################
# 3) TWITTER SETTINGS
###############################################################################
import tweepy

# Your consumer (API) key/secret from the dev portal
CONSUMER_KEY = "iJWS5YljBzHoGDP9ln9sMo3hC"
CONSUMER_SECRET = "0Z3EPje9jLY7spaj9IH2SKPkl5b2BaaLJlcbxwpKmaN61IYW0m"
CALLBACK_URL = "http://127.0.0.1:5000/callback"

###############################################################################
# 4) FLASK SETUP
###############################################################################
from flask import Flask, request, session, redirect

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

###############################################################################
# 5) HELPER FUNCTIONS
###############################################################################
def store_user_tokens(screen_name, access_token, access_secret):
    all_rows = users_sheet.get_all_values()
    data_rows = all_rows[1:] if len(all_rows) > 1 else []
    existing_idx = None
    for i, row in enumerate(data_rows, start=2):
        if row and row[0] == screen_name:
            existing_idx = i
            break
    if existing_idx:
        users_sheet.update_cell(existing_idx, 2, access_token)
        users_sheet.update_cell(existing_idx, 3, access_secret)
    else:
        users_sheet.append_row([screen_name, access_token, access_secret])

def get_user_tokens(screen_name):
    all_rows = users_sheet.get_all_values()
    data_rows = all_rows[1:] if len(all_rows) > 1 else []
    for row in data_rows:
        if row and row[0] == screen_name:
            return (row[1], row[2])
    return None

def schedule_tweet(time_utc, owner, text, media_id=""):
    tweets_sheet.append_row([time_utc, owner, text, media_id, "FALSE"])

def list_scheduled_tweets():
    all_rows = tweets_sheet.get_all_values()
    return all_rows[1:] if len(all_rows) > 1 else []

def mark_as_posted(row_idx):
    tweets_sheet.update_cell(row_idx, 5, "TRUE")

###############################################################################
# 6) ROUTES
###############################################################################
@app.route("/")
def home():
    return """
    <h2>Twitter OAuth (v2 Posting) + Google Sheets Scheduling Demo</h2>
    <p><a href='/login'>Sign in with Twitter</a></p>
    <p><a href='/schedule_list'>View scheduled tweets</a></p>
    """

@app.route("/login")
def login():
    print("DEBUG: CONSUMER_KEY =", CONSUMER_KEY)
    print("DEBUG: CONSUMER_SECRET =", CONSUMER_SECRET)

    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, callback=CALLBACK_URL)
    try:
        redirect_url = auth.get_authorization_url()
        session["request_token"] = (
            auth.request_token["oauth_token"],
            auth.request_token["oauth_token_secret"]
        )
        return redirect(redirect_url)
    except Exception as e:
        return f"Error getting authorization URL: {e}"

@app.route("/callback")
def callback():
    if "request_token" not in session:
        return "No request token in session. Go /login first."

    request_token, request_token_secret = session.pop("request_token")
    oauth_verifier = request.args.get("oauth_verifier")
    if not oauth_verifier:
        return "Missing oauth_verifier"

    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET)
    auth.request_token = {
        "oauth_token": request_token,
        "oauth_token_secret": request_token_secret
    }
    try:
        access_token, access_secret = auth.get_access_token(oauth_verifier)
        api = tweepy.API(auth)
        user_info = api.verify_credentials()
        screen_name = user_info.screen_name

        store_user_tokens(screen_name, access_token, access_secret)

        return f"""
        <h3>Welcome, {screen_name}!</h3>
        <p>Tokens stored in 'Users' tab. Now you can upload media or schedule tweets.</p>
        <ul>
          <li><a href='/upload_form'>Upload media</a></li>
          <li><a href='/schedule_form'>Schedule a tweet</a></li>
          <li><a href='/schedule_list'>List scheduled tweets</a></li>
        </ul>
        """
    except Exception as e:
        return f"Error fetching access token: {e}"

@app.route("/upload_form")
def upload_form():
    return """
    <h3>Upload Media (Chunked for video/images)</h3>
    <form method='POST' action='/upload_media' enctype='multipart/form-data'>
      <p>Owner (screen_name): <input name='owner'/></p>
      <p>Select file: <input type='file' name='media_file'/></p>
      <button type='submit'>Upload</button>
    </form>
    """

import requests
from requests_oauthlib import OAuth1

@app.route("/upload_media", methods=["POST"])
def upload_media():
    owner = request.form.get("owner", "").strip()
    if not owner:
        return "Must provide owner (screen_name)."

    tokens = get_user_tokens(owner)
    if not tokens:
        return f"No tokens found for '{owner}'. Please /login with that user first."

    access_token, access_secret = tokens
    oauth = OAuth1(CONSUMER_KEY, CONSUMER_SECRET, access_token, access_secret)

    media_file = request.files.get("media_file")
    if not media_file:
        return "No file uploaded."

    file_bytes = media_file.read()
    total_bytes = len(file_bytes)

    import mimetypes
    mime_type = mimetypes.guess_type(media_file.filename)[0] or "application/octet-stream"

    init_url = "https://upload.twitter.com/1.1/media/upload.json"
    init_data = {
        "command": "INIT",
        "media_type": mime_type,
        "total_bytes": total_bytes,
        "media_category": "tweet_video"  # or 'tweet_image'
    }
    resp_init = requests.post(init_url, data=init_data, auth=oauth)
    if resp_init.status_code not in [200, 201, 202]:
        return f"INIT error: {resp_init.status_code}, {resp_init.text}"

    init_json = resp_init.json()
    media_id = init_json.get("media_id_string")
    if not media_id:
        return "No media_id in INIT response"

    # APPEND
    segment_size = 4 * 1024 * 1024
    idx = 0
    segment_index = 0
    while idx < total_bytes:
        chunk = file_bytes[idx : idx + segment_size]
        files = {"media": (media_file.filename, chunk)}
        append_data = {
            "command": "APPEND",
            "media_id": media_id,
            "segment_index": segment_index
        }
        resp_append = requests.post(init_url, data=append_data, files=files, auth=oauth)
        if resp_append.status_code not in [200, 201, 202, 204]:
            return f"APPEND error: {resp_append.status_code}, {resp_append.text}"
        idx += segment_size
        segment_index += 1

    # FINALIZE
    finalize_data = {
        "command": "FINALIZE",
        "media_id": media_id
    }
    resp_fin = requests.post(init_url, data=finalize_data, auth=oauth)
    if resp_fin.status_code not in [200, 201, 202]:
        return f"FINALIZE error: {resp_fin.status_code}, {resp_fin.text}"

    fin_json = resp_fin.json()
    processing_info = fin_json.get("processing_info")
    if processing_info:
        # Poll for completion if it's video
        state = processing_info.get("state")
        check_after_secs = processing_info.get("check_after_secs", 5)
        while state in ["pending", "in_progress"]:
            time.sleep(check_after_secs)
            resp_stat = requests.get(
                init_url,
                params={"command": "STATUS", "media_id": media_id},
                auth=oauth
            )
            if resp_stat.status_code not in [200, 201, 202]:
                return f"STATUS poll error: {resp_stat.status_code}, {resp_stat.text}"

            stat_json = resp_stat.json()
            processing_info = stat_json.get("processing_info", {})
            state = processing_info.get("state")
            check_after_secs = processing_info.get("check_after_secs", 5)
            if state == "failed":
                err_msg = processing_info.get("error", {}).get("message", "Unknown error")
                return f"Video processing failed: {err_msg}"
        if state != "succeeded":
            return f"Unexpected final state: {state}"

    return f"""
    <h3>Upload Success!</h3>
    <p>media_id: {media_id}</p>
    <p><a href='/schedule_form'>Schedule a tweet with this media</a></p>
    """

@app.route("/schedule_form")
def schedule_form():
    # ADDED a "Post Now?" checkbox
    return """
    <h3>Schedule a Tweet</h3>
    <form method="POST" action="/schedule_create">
      <p>Owner (screen_name): <input name="owner" /></p>
      <p>Tweet text: <input name="text" /></p>
      <p>Media ID (optional): <input name="media_id" /></p>
      <p>Schedule (UTC, e.g. 2025-03-07 13:30): <input name="utc_time" /></p>
      <p>Post Now? <input type="checkbox" name="post_now" value="yes"></p>
      <button type="submit">Schedule</button>
    </form>
    """

@app.route("/schedule_create", methods=["POST"])
def schedule_create():
    owner = request.form.get("owner", "").strip()
    text = request.form.get("text", "")
    media_id = request.form.get("media_id", "").strip()
    utc_str = request.form.get("utc_time", "").strip()
    post_now = request.form.get("post_now")

    if not owner:
        return "Owner (screen_name) is required."

    # If "Post Now?" is checked, we attempt to post immediately
    if post_now == "yes":
        from datetime import datetime
        dt_iso = datetime.utcnow().isoformat()

        # Schedule a row in the sheet (with posted=FALSE initially)
        schedule_tweet(dt_iso, owner, text, media_id)

        # We'll retrieve the row index for the new entry (the last row)
        new_row_index = tweets_sheet.row_count

        # Attempt to post immediately
        success = post_tweet(owner, text, media_id)
        if success:
            # Mark the newly appended row as posted
            mark_as_posted(new_row_index)

        return f"""
        <h3>Post Now Attempted</h3>
        <p>Tweet for {owner}: "{text}"</p>
        <p>Posted right away? { 'Success' if success else 'Failed / Will Retry' }</p>
        <p><a href='/schedule_list'>View all scheduled</a></p>
        """

    # Otherwise, normal scheduling in the future
    if not utc_str:
        return "UTC time is required if not posting now."

    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M")
    except ValueError:
        return "Invalid datetime format. Use YYYY-MM-DD HH:MM (24h) in UTC."

    dt_iso = dt.isoformat()
    schedule_tweet(dt_iso, owner, text, media_id)

    return f"""
    <h3>Scheduled!</h3>
    <p>{owner} => "{text}" at {dt_iso}, media: {media_id or 'None'}</p>
    <p><a href='/schedule_list'>View all scheduled</a></p>
    """

@app.route("/schedule_list")
def schedule_list():
    all_rows = tweets_sheet.get_all_values()
    if not all_rows:
        return "<h3>No data found in 'ScheduledTweets'</h3>"

    header = all_rows[0]
    data = all_rows[1:]
    rows_html = []
    for row in data:
        row_html = "".join(f"<td>{col}</td>" for col in row)
        rows_html.append(f"<tr>{row_html}</tr>")

    return f"""
    <h3>All Scheduled Tweets</h3>
    <table border='1' cellpadding='5'>
      <tr>{"".join(f"<th>{h}</th>" for h in header)}</tr>
      {"".join(rows_html)}
    </table>
    <p><a href='/'>Home</a> | <a href='/schedule_form'>Schedule new</a></p>
    """

###############################################################################
# 7) POSTING TWEETS VIA API v2
###############################################################################
def post_tweet(owner, text, media_id=None):
    """
    Same v2 approach as before,
    tries to post via client.create_tweet().
    """
    from tweepy import Client
    tokens = get_user_tokens(owner)
    if not tokens:
        print(f"[post_tweet] No tokens for user {owner}")
        return False

    access_token, access_secret = tokens
    try:
        client = Client(
            consumer_key=CONSUMER_KEY,
            consumer_secret=CONSUMER_SECRET,
            access_token=access_token,
            access_token_secret=access_secret
        )
        if media_id:
            resp = client.create_tweet(text=text, media_ids=[media_id])
        else:
            resp = client.create_tweet(text=text)

        tweet_id = resp.data.get("id")
        print(f"[{owner}] v2 Tweet posted. ID = {tweet_id}")
        return True
    except Exception as e:
        print(f"[{owner}] ERROR posting v2 tweet: {e}")
        return False

def check_scheduled_tweets():
    """
    Background thread: checks the 'ScheduledTweets' sheet every 60s.
    If time_utc <= now and posted=FALSE, tries to post, then marks as posted if successful.
    """
    while True:
        now = datetime.utcnow()
        data = list_scheduled_tweets()
        for i, row in enumerate(data, start=2):
            if len(row) < 5:
                continue
            dt_str, owner, text, media_id, posted = row
            if posted.strip().upper() == "TRUE":
                continue

            try:
                dt_scheduled = datetime.fromisoformat(dt_str)
            except ValueError:
                print(f"Row {i}: invalid date {dt_str}")
                continue

            if dt_scheduled <= now:
                print(f"Posting v2 tweet for {owner} (row {i})")
                success = post_tweet(owner, text, media_id)
                if success:
                    mark_as_posted(i)
        time.sleep(60)

threading.Thread(target=check_scheduled_tweets, daemon=True).start()

###############################################################################
# 8) RUN FLASK
###############################################################################
if __name__ == "__main__":
    # Ensure you have Tweepy >=4.12 for v2 client
    app.run(debug=True, port=5000)