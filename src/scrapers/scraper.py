import logging
import time
import random
import re
import os
import pandas as pd
from datetime import datetime

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

# For reading/writing your Google Sheet
from utils.sheets import read_sheet, write_sheet

def init_driver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def login_to_twitter(driver, username, password):
    """
    Logs into X (Twitter) once.
    """
    logging.info("Starting X login once...")
    driver.delete_all_cookies()
    driver.get("https://x.com/i/flow/login")
    time.sleep(5)

    try:
        user_field = driver.find_element(By.CSS_SELECTOR, "input[autocomplete='username']")
        for c in username:
            user_field.send_keys(c)
            time.sleep(0.04)
        time.sleep(1)

        next_btn = driver.find_element(By.XPATH, "//span[text()='Next']")
        next_btn.click()
        time.sleep(3)

        pwd_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        for c in password:
            pwd_field.send_keys(c)
            time.sleep(0.04)

        login_btn = driver.find_element(By.XPATH, "//span[text()='Log in']")
        login_btn.click()
        time.sleep(5)
        logging.info("X login complete.")
    except Exception as e:
        logging.error("X login failed.", exc_info=True)
        raise

def parse_view_count(text):
    pattern = r"(\d+(?:\.\d+)?)([KM]?)"
    matches = re.findall(pattern, text)
    if not matches:
        return None
    max_val = 0
    for (num_str, suffix) in matches:
        val = float(num_str)
        if suffix.upper() == 'K':
            val *= 1_000
        elif suffix.upper() == 'M':
            val *= 1_000_000
        if val > max_val:
            max_val = int(val)
    return max_val if max_val > 0 else None

def get_tweet_url(article):
    links = article.find_elements(By.TAG_NAME, "a")
    for link in links:
        href = link.get_attribute("href")
        if href and "/status/" in href:
            return href
    return None

def scrape_twitter(driver, handle, min_views=100000, max_videos=10, max_scrolls=15):
    """
    Scrapes tweets from a single handle (already logged in).
    Returns a list of (tweet_url, views).
    """
    logging.info(f"Scraping X user @{handle}, min_views={min_views}")
    driver.get(f"https://x.com/{handle}")
    time.sleep(3)

    scraped = []
    seen_urls = set()
    scroll_count = 0

    while len(scraped) < max_videos and scroll_count < max_scrolls:
        time.sleep(random.uniform(2, 4))
        articles = driver.find_elements(By.CSS_SELECTOR, "article")
        for art in articles:
            if len(scraped) >= max_videos:
                break
            try:
                videos = art.find_elements(By.TAG_NAME, "video")
                if not videos:
                    continue

                raw_text = art.text
                views = parse_view_count(raw_text)
                if not views or views < min_views:
                    continue

                tweet_url = get_tweet_url(art)
                if not tweet_url or tweet_url in seen_urls:
                    continue

                scraped.append((tweet_url, views))
                seen_urls.add(tweet_url)
                logging.info(f"Found tweet: {tweet_url} (views={views})")
            except StaleElementReferenceException:
                logging.warning("Stale tweet, skipping...")

        scroll_count += 1
        driver.execute_script("window.scrollBy(0, 3000)")
        logging.info(f"Scrolling {scroll_count}/{max_scrolls}")

    logging.info(f"Scraped {len(scraped)} tweets from @{handle}.")
    return scraped

def export_selenium_cookies_to_netscape(driver, cookie_file_path):
    cookies = driver.get_cookies()
    with open(cookie_file_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in cookies:
            domain = c.get("domain", "")
            domain_flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure_flag = "TRUE" if c.get("secure", False) else "FALSE"
            expiry = c.get("expiry", "0")
            name = c.get("name", "")
            value = c.get("value", "")
            line = f"{domain}\t{domain_flag}\t{path}\t{secure_flag}\t{expiry}\t{name}\t{value}\n"
            f.write(line)
    logging.info(f"Exported cookies => {cookie_file_path}")

def add_single_video_to_sheet(
    spreadsheet_id,
    sheet_name,
    tweet_url,
    tweet_views,
    niche_name,
    platform="twitter"
):
    """
    Immediately appends one row for (tweet_url, tweet_views) to the sheet.
    by default => posted='N' since not posted yet.
    """
    df = read_sheet(spreadsheet_id, sheet_name)
    if df.empty:
        # columns per your new layout (13 columns)
        df = pd.DataFrame(columns=[
            "ID",
            "niche",
            "video_url",
            "downloaded y/n/c",
            "download_url",
            "local_path",
            "caption",
            "views",
            "timestamp",
            "platform",
            "account uploaded to",
            "time uploaded",
            "posted"
        ])

    # Skip duplicates
    if "video_url" in df.columns and tweet_url in df["video_url"].values:
        logging.info(f"Skipping duplicate: {tweet_url}")
        return

    next_id = len(df) + 1
    row_dict = {
        "ID": str(next_id),
        "niche": niche_name,
        "video_url": tweet_url,
        "downloaded y/n/c": "N",
        "download_url": "",
        "local_path": "",
        "caption": "",
        "views": str(tweet_views),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform,
        "account uploaded to": "",
        "time uploaded": "",
        # posted => 'N' by default
        "posted": "N"
    }

    new_df = pd.DataFrame([row_dict])
    df = pd.concat([df, new_df], ignore_index=True)
    write_sheet(spreadsheet_id, sheet_name, df)
    logging.info(f"Added tweet => {tweet_url} with ID={next_id}, posted='N'.")

def run_scraper_for_niche(
    burner_username,
    burner_password,
    handles_list,
    spreadsheet_id,
    sheet_name,       # e.g. "VideoDatabase"
    niche_name,
    platform="twitter",
    max_scrolls=15,
    min_views=100000,
    max_videos=10
):
    """
    1) Logs in once
    2) Exports cookies for the video downloader
    3) For each handle => scrape => for each tweet => add_single_video_to_sheet with posted='N'
    4) Quits at the end
    """
    driver = init_driver()
    try:
        # Login
        login_to_twitter(driver, burner_username, burner_password)
        # Export cookies for downloader
        cookie_file = "/Users/tylergrabowski/scripts/social_media_manager/src/scrapers/twitter_cookies.txt"
        export_selenium_cookies_to_netscape(driver, cookie_file)

        for handle in handles_list:
            results = scrape_twitter(
                driver,
                handle,
                min_views=min_views,
                max_videos=max_videos,
                max_scrolls=max_scrolls
            )
            logging.info(f"@{handle} => {len(results)} tweets found.")
            # Immediately record each tweet => posted='N'
            for (tweet_url, tweet_views) in results:
                add_single_video_to_sheet(
                    spreadsheet_id,
                    sheet_name,
                    tweet_url,
                    tweet_views,
                    niche_name,
                    platform
                )
    finally:
        driver.quit()