import os

#############################################################################
# Bypass the requirement for HTTPS during local dev:
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
#############################################################################

import tweepy
from flask import Flask, request

#############################################################################
# Your OAuth 2.0 credentials from the Dev Portal:
CLIENT_ID = "dUpjeFZENWFDQjhTdDdVNUdKdWw6MTpjaQ"
CLIENT_SECRET = "Oup5JXo_FRnOczGKcculo_Le-1l5PFLHgxSn38SkbOLKFF63ei"

# Must match your Developer Portal "Callback URI / Redirect URL"
CALLBACK_URI = "http://127.0.0.1:1410/callback"

# Scopes you want. For posting tweets, ensure "tweet.write" is included:
SCOPES = ["tweet.read", "tweet.write", "users.read"]
# If you want offline refresh tokens, add "offline.access" as well:
# SCOPES = ["tweet.read", "tweet.write", "users.read", "offline.access"]
#############################################################################

app = Flask(__name__)
oauth_store = {}

@app.route("/")
def index():
    return (
        "Hello! This is the OAuth 2.0 demo. "
        "Go to <a href='/login'>/login</a> to start the authorization flow."
    )

@app.route("/login")
def login():
    """
    Step 1: Get the authorization URL from Tweepy for OAuth 2.0 user context,
    then show the link to the user.
    """
    try:
        auth = tweepy.OAuth2UserHandler(
            client_id=CLIENT_ID,
            redirect_uri=CALLBACK_URI,
            scope=SCOPES,
            client_secret=CLIENT_SECRET  # needed if your app is "Confidential client"
        )
        authorization_url = auth.get_authorization_url()
        # Store the auth object in memory for callback usage
        oauth_store["auth"] = auth

        return (
            "<h2>Authorize with Twitter OAuth 2.0</h2>"
            f"<p>Click here to authorize: "
            f"<a href='{authorization_url}'>{authorization_url}</a></p>"
        )
    except Exception as e:
        return f"Error during login: {e}"

@app.route("/callback")
def callback():
    """
    Step 2: Twitter redirects to /callback with ?code=..., we exchange it for the final token.
    """
    if "auth" not in oauth_store:
        return "No OAuth session found. Go to /login first."
    
    auth = oauth_store["auth"]
    full_url = request.url  # e.g. http://127.0.0.1:1410/callback?code=abc123&state=xyz

    try:
        token_info = auth.fetch_token(full_url)
        # token_info might look like:
        # {
        #   'access_token': 'YOUR_USER_ACCESS_TOKEN',
        #   'refresh_token': 'SOME_REFRESH_TOKEN_IF_OFFLINE.ACCESS_SCOPE_WAS_INCLUDED',
        #   'expires_in': 7200,
        #   ...
        # }

        access_token = token_info["access_token"]
        refresh_token = token_info.get("refresh_token", "No refresh token")

        return (
            "<h3>Success!</h3>"
            f"<p>Access Token: {access_token}</p>"
            f"<p>Refresh Token: {refresh_token}</p>"
            "<p>Use this <strong>Access Token</strong> with tweepy.Client to post tweets via v2!</p>"
        )
    except Exception as e:
        return f"Error fetching token: {e}"

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=1410, debug=True)