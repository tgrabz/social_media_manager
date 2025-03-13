import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP instead of HTTPS in local dev

import streamlit as st
import requests
import json

st.set_page_config(page_title="X OAuth 2.0 Demo", layout="centered")

st.title("X (Twitter) OAuth 2.0 Demo - Raw HTTP Approach")

# We store important data in session_state
if "client_id" not in st.session_state:
    # This is your OAuth 2.0 CLIENT_ID & SECRET from the Dev Portal
    st.session_state.client_id = "dUpjeFZENWFDQjhTdDdVNUdKdWw6MTpjaQ"
if "client_secret" not in st.session_state:
    st.session_state.client_secret = "Oup5JXo_FRnOczGKcculo_Le-1l5PFLHgxSn38SkbOLKFF63ei"

if "access_token" not in st.session_state:
    st.session_state.access_token = None

# The redirect URI we set in the Dev Portal (can just do http://localhost:8501)
REDIRECT_URI = "http://localhost:8501"
# The scopes we want (must match your app settings in Dev Portal):
SCOPES = ["tweet.read", "tweet.write", "users.read"]

st.write("""
This example does:
1. Generate an OAuth 2.0 link for user context.
2. You sign in, get redirected back to `http://localhost:8501?code=xxx&state=yyy`.
3. You copy the `?code=...&state=...` query string, paste it here.
4. We exchange code for a user Access Token.
5. We use that Access Token to POST a tweet via `POST /2/tweets`.
""")

# Section A: Input client credentials (optional if you want to override)
st.subheader("Step A: Input OAuth 2.0 Client Credentials (Optional)")

col1, col2 = st.columns(2)
with col1:
    client_id = st.text_input("Client ID", value=st.session_state.client_id)
with col2:
    client_secret = st.text_input("Client Secret", value=st.session_state.client_secret)

if st.button("Save Credentials"):
    st.session_state.client_id = client_id
    st.session_state.client_secret = client_secret
    st.success("Credentials updated in session.")

# Section B: Generate Auth URL
st.subheader("Step B: Generate Auth URL & Sign In")

if st.button("Generate Auth URL"):
    try:
        # We'll build the URL manually for the "authorization code" flow
        # Typically: https://twitter.com/i/oauth2/authorize?response_type=code&client_id=...&redirect_uri=...&scope=...
        base_auth_url = "https://twitter.com/i/oauth2/authorize"
        response_type = "code"
        # We must join scopes with a space
        scope_str = " ".join(SCOPES)
        state_str = "xyz123"  # you can randomize this for security
        code_challenge = "challenge"  # for PKCE if desired, or just skip in dev
        code_challenge_method = "plain"

        params = {
            "response_type": response_type,
            "client_id": st.session_state.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": scope_str,
            "state": state_str,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method
        }
        from urllib.parse import urlencode
        full_url = base_auth_url + "?" + urlencode(params)

        st.write("**Open this URL in your browser:**")
        st.code(full_url, language="bash")
        st.info("""
1) Login & authorize.
2) You get redirected to something like `http://localhost:8501?code=ABCD&state=xyz123`.
3) Copy that entire `?code=...&state=...` from your URL bar.
""")
    except Exception as e:
        st.error(f"Error generating auth URL: {e}")

# Section C: Paste code + state, exchange for Access Token
st.subheader("Step C: Paste `?code=...&state=...` here, fetch token")

raw_code = st.text_input("Your `code=xxx&state=yyy` query:")
if st.button("Fetch Access Token"):
    if not raw_code:
        st.error("No code query provided.")
    else:
        try:
            # We'll parse out code & state from `raw_code`
            # e.g., raw_code="code=abc123&state=xyz"
            from urllib.parse import parse_qs
            parsed = parse_qs(raw_code)
            code = parsed.get("code",[None])[0]
            state = parsed.get("state",[None])[0]

            if not code:
                st.error("No code param found. Make sure you pasted it correctly.")
            else:
                # Now do a POST to https://api.twitter.com/2/oauth2/token
                token_url = "https://api.twitter.com/2/oauth2/token"
                headers = {
                    "Content-Type": "application/x-www-form-urlencoded"
                }
                data = {
                    "grant_type": "authorization_code",
                    "client_id": st.session_state.client_id,
                    "redirect_uri": REDIRECT_URI,
                    "code": code,
                    "code_verifier": "challenge"  # we used code_challenge_method=plain
                }
                if st.session_state.client_secret:
                    data["client_secret"] = st.session_state.client_secret

                resp = requests.post(token_url, data=data, headers=headers)
                st.write("Status code:", resp.status_code)
                st.json(resp.json())

                if resp.status_code == 200:
                    token_info = resp.json()
                    st.session_state.access_token = token_info["access_token"]
                    st.success("Access token saved!")
                else:
                    st.error(f"Failed to get token. See response above.")
        except Exception as e:
            st.error(f"Error fetching token: {e}")

# Section D: Post a tweet
st.subheader("Step D: Post a Tweet (v2)")

if not st.session_state.access_token:
    st.warning("No user access token found. Please do Steps B/C.")
else:
    tweet_text = st.text_area("Tweet Text", "Hello from Streamlit + raw HTTP v2!")
    if st.button("Create Tweet"):
        # We'll do a POST /2/tweets with Bearer <access_token>
        url = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {st.session_state.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "text": tweet_text
        }
        resp = requests.post(url, headers=headers, json=payload)
        st.write("Status code:", resp.status_code)
        st.json(resp.json())
        if resp.status_code == 201:
            st.success("Tweet posted successfully!")
        else:
            st.error("Could not post tweet (check response).")