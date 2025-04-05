import datetime
from fastapi import FastAPI
import requests
import os
from dotenv import find_dotenv, load_dotenv
import numpy as np
# from datetime import date
import math
from datetime import datetime, timezone

dotenv_path = find_dotenv()

load_dotenv(dotenv_path)

app = FastAPI()

items = []

api_key=os.getenv("YOUTUBE_DATA_API_KEY")

def get_video_data(video_id: str):
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&id={video_id}&key={api_key}"

    payload = {}
    headers = {}

    res = requests.request("GET", url, headers=headers, data=payload)
    res = res.json()
    today = datetime.now(timezone.utc)
    videoPublishDate_raw = ((res["items"][0]["snippet"]["publishedAt"]))

    videoPublishDate = datetime.strptime(videoPublishDate_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    difference = (today - videoPublishDate)
    hours = difference.total_seconds() / 3600
    res["items"][0]["snippet"]["hoursSinceUpload"] = hours
    return res

def get_channel_data(channel_id: str):
    url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id={channel_id}&key={api_key}"

    payload = {}
    headers = {}

    res = requests.request("GET", url, headers=headers, data=payload)
    return res.json()

def get_channel_subscribers_from_id(channel_id: str):
    url = f"https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics&id={channel_id}&key={api_key}"

    payload = {}
    headers = {}

    res = requests.request("GET", url, headers=headers, data=payload)
    return int(res.json()["items"][0]["statistics"]["subscriberCount"])

def generate_collect_ratio(video_data, channel_data):
    videoViewCount = float(video_data["items"][0]["statistics"]["viewCount"])
    if videoViewCount == 0:
        videoViewCount = 1
    hoursSinceUpload = float(video_data["items"][0]["snippet"]["hoursSinceUpload"])
    if hoursSinceUpload == 0:
        hoursSinceUpload = 1
    if "likeCount" in video_data["items"][0]["statistics"]:
        videoLikeCount = float(video_data["items"][0]["statistics"]["likeCount"])
    else:
        videoLikeCount = 1
    if "commentCount" in video_data["items"][0]["statistics"]:
        videoCommentCount = float(video_data["items"][0]["statistics"]["commentCount"])
    else:
        videoCommentCount = 1
    channelVideoCount = float(channel_data["items"][0]["statistics"]["videoCount"])
    channelViewCount = float(channel_data["items"][0]["statistics"]["viewCount"])
    if channelViewCount == 0:
        channelViewCount = 1
    channelSubCount = float(channel_data["items"][0]["statistics"]["subscriberCount"])
    if channelSubCount == 0:
        channelSubCount = 1
    print(hoursSinceUpload)
    v = channelViewCount / (2 * channelVideoCount)
    v_hat = v * min(1, channelVideoCount / 100)
    E = (videoLikeCount + videoCommentCount + 1) / (videoViewCount + 1)
    G_estimate = 1 - math.exp(-v / (v_hat + 1))
    S = channelSubCount
    small_channel_boost = 1 + (10000 / (S + 10000))
    outperformance = 1 + ((v - v_hat) / (v_hat + 1))
    anti_whale = 1 / (1 + (S / 100000))
    K = 1e7

    # time_component = 1 + ((1 / math.log(videoViewCount + S + 1)) * math.log(1 + hoursSinceUpload))
    half_life = min(48, max(6, 24 * (10000 / (S + 10000))))
    decay_start = max(0, hoursSinceUpload - 1)
    time_decay = math.exp(-decay_start / half_life)
    if hoursSinceUpload < 48:
        raw_price = ((videoViewCount ** 0.7) * (1 + E)) / (2 * S)
        price = K * raw_price * small_channel_boost * G_estimate * outperformance * anti_whale * time_decay
    else:
        days = hoursSinceUpload / 24
        raw_price = ((videoViewCount ** 0.7) * (1 + E)) / (2 * S)
        base_price = raw_price*0.2
        rebound = 1 + math.log1p(days - 2)/2
        price = base_price * rebound
        
    if price == 0:
        return [videoViewCount, channelSubCount, 0.9999]
    else:
        return [videoViewCount, channelSubCount, price]
    
@app.get("/")
def root():
    return {"Hello": "World"}

@app.get("/get_video_metadata/{video_id}")
def get_video_metadata(video_id):
    video_data = get_video_data(video_id)["items"][0]
    return video_data

@app.get("/get_channel_metadata/{channel_id}")
def get_channel_metadata(channel_id):
    return get_channel_data(channel_id)["items"][0]


@app.get("/video_viewcount/{video_id}")
def get_video_viewcount(video_id: str):
    return int(get_video_data(video_id)["items"][0]["statistics"]["viewCount"])

@app.get("/channel_subscribers/{channel_id}")
def get_channel_subscribers(channel_id: str):
    return get_channel_subscribers_from_id(channel_id)

@app.get("/collect_ratio/{video_id}")
def get_collect_ratio(video_id: str):
    video_data = get_video_data(video_id)
    channel_data = get_channel_data(video_data["items"][0]["snippet"]["channelId"])
    return generate_collect_ratio(video_data, channel_data)


@app.get("/collect_ratio_and_video_metadata/{video_id}")
def get_collect_ratio_and_video_metadata(video_id: str):
    res = []
    video_data = get_video_data(video_id)
    channel_data = get_channel_data(video_data["items"][0]["snippet"]["channelId"])
    collect_ratio = generate_collect_ratio(video_data, channel_data)
    res.extend(collect_ratio)
    res.append(video_data["items"][0])
    return res