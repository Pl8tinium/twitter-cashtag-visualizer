import tweepy
import os
import re
import schedule
import datetime
from influxdb_client import InfluxDBClient
from influxdb_client .client.write_api import SYNCHRONOUS
import time

consumer_key = 'szgPfe8ILks30ofFUywJFBhKF'
consumer_secret = 'ahQS70NpvxHCYuWWGZo5FK1rnGWcN4Rrw1609acUEkn2It8tnN'
access_token = '4450264233-ZCqjV6uAGThQ75730ab4iNQeqECH1HnSwXXAVGV'
access_token_secret = 'zz4ZFSr39t8PlRRFGw9NoHGdQ50ksKUnHGMmV350vYNRX'

ignores = ["cryptotrendin", "dexscreener"]
cash_tag_path = '/cashtag_grab/'

call_amount = 10
mentions_file_name = 'mentions.json'
since_id_file_name = 'since_id.txt'
since_id_path = cash_tag_path + since_id_file_name
mentions_path = cash_tag_path + mentions_file_name

cash_tag_reg = r"\$[a-zA-Z]{3,5}"

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# check if main dir exists, if not create
if not os.path.isdir(cash_tag_path):
    os.makedirs(cash_tag_path)

def main():
    # init stuff for influx
    client = InfluxDBClient(url="http://influxdb:8086", token="mytoken", org="myorg")
    write_api = client.write_api(write_options=SYNCHRONOUS)
    points = []

    # Get the current since_id if exists from previous run
    since_id = 1
    if os.path.isfile(since_id_path):
        with open(since_id_path, 'r') as f:
            since_id = int(f.read())

    latest_tweet_time = None
    for page in tweepy.Cursor(api.home_timeline, count=200, tweet_mode="extended", since_id=since_id).pages(call_amount):
        for status in page:
            if status.user.screen_name in ignores:
                continue
            matched = []
            for match in re.finditer(cash_tag_reg, status.full_text, re.MULTILINE):
                cash_tag = match.group().lower()
                if cash_tag not in matched:
                    matched.append(cash_tag)
                    point = {
                            "measurement": "cashtag_grab",
                            "tags": {
                                "cashtag": cash_tag,
                                "user": status.user.screen_name
                            },
                            "time": status.created_at,
                            "fields": {
                                "Retweet_count": status.retweet_count,
                                "Favorite_count": status.favorite_count,
                                "Status_id": status.id
                            }
                        }                    
                    points.append(point)

            # know when the latest tweet was posted so the tool only fetches tweets after that in the next run
            if latest_tweet_time == None or latest_tweet_time < status.created_at:
                latest_tweet_time = status.created_at
                since_id = status.id

    # influx db write and close
    write_api.write(bucket="mybucket", record=points)
    client.close()
    # print(points)

    #write current since_id to file
    with open(since_id_path, 'w') as f:
        f.write(str(since_id))

main()
time_one_min_before = datetime.datetime.now() - datetime.timedelta(minutes=1)
schedule.every().hour.at(time_one_min_before.strftime("%M:%S")).do(main)

while True:
    schedule.run_pending()
    time.sleep(10 * 1000)