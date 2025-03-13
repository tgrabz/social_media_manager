import requests

# Your user Access Token from the OAuth 2.0 callback
ACCESS_TOKEN = "c2UwWUZXWXJkT2dqMUUwY2N2dUhHSDRRSzgxWHFWWWZGV2V1bF..."

# The tweet text you want to post
TWEET_TEXT = "Hello from raw HTTP requests (no Tweepy)!"

def main():
    # 1) Construct the headers with "Bearer <user access token>"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # 2) Build the JSON body
    payload = {
        "text": TWEET_TEXT
    }

    # 3) POST to Twitter v2 create tweet endpoint
    url = "https://api.twitter.com/2/tweets"
    resp = requests.post(url, headers=headers, json=payload)

    # 4) Print the response
    print("Status code:", resp.status_code)
    print("Response JSON:", resp.json())

if __name__ == "__main__":
    main()
