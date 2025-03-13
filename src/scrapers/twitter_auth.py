# /Users/tylergrabowski/scripts/social_media_manager/src/scrapers/twitter_auth.py

import os
import tweepy
from dotenv import load_dotenv

# Points to your .env file path:
ENV_PATH = "/Users/tylergrabowski/scripts/social_media_manager/src/config/twitter_api.env"

def get_twitter_api():
    """
    Loads Twitter API credentials from twitter_api.env 
    and returns a Tweepy API object.
    """
    load_dotenv(dotenv_path=ENV_PATH)

    API_KEY = os.getenv("TWITTER_API_KEY", "")
    API_SECRET = os.getenv("TWITTER_API_KEY_SECRET", "")
    ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
    ACCESS_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

    auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
    api = tweepy.API(auth)
    return api