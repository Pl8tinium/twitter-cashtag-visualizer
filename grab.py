import tweepy
import os
import re
import schedule
import datetime
from influxdb_client import InfluxDBClient
from influxdb_client .client.write_api import SYNCHRONOUS
import time
import requests

consumer_key = ''
consumer_secret = ''
access_token = ''
access_token_secret = ''

# this variable controls how far behind tweets data gets updated, this is useful because maybe a tweet is fetched but it is relatively fresh
# so the metrics arround this tweet e.g. the 'like' count will probably change in the future
tweet_update_timeframe = "1"
# ignore certain accounts
ignores = ["cryptotrendin", "dexscreener"]

admin_token = "mytoken"
org = "myorg"
bucket = "mybucket"
call_amount = 10
cashtag_reg_precise = r"\$[a-zA-Z]{3,5}"
do_prefetch_extraction = True
most_common_words_path = '/most_common_words'
reduce_prefetched_cashtags_by = 100000

auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth)

# get tickers from coingecko
def get_tickers():    
    data = requests.get('https://api.coingecko.com/api/v3/coins/list').json()
    tickers = []
    for coin in data:
        tickers.append(coin['symbol'].replace('$', '').lower())

    f = open(most_common_words_path + '/mostcommon' + str(reduce_prefetched_cashtags_by) + '.txt', "r")
    common_words = f.read().lower().split('\n')

    f = open(most_common_words_path + '/cryptocommon.txt', "r")
    crypto_words = f.read().lower().split('\n')

    cleaned_tickers = []
    for ticker in set(tickers):
        if len(ticker) != 1 and len(ticker) <= 7:
            if not ticker in common_words + crypto_words:            
                cleaned_tickers.append(ticker)

    print("found " + str(len(cleaned_tickers)) + " tickers on coingecko without ambiguity")
    
    return cleaned_tickers

# fetch all tweets after the found tweet id
def get_tweet_id_to_fetch_since(client):
    query_latest_tweet = """from(bucket: "{0}")
        |> range(start: -{1}d, stop: now())
        |> filter(fn: (r) => r["_measurement"] == "cashtag_grab")
        |> group()
        |> sort(columns:["_time"])
        |> first()
        |> keep(columns: ["status_id"])""".format(bucket, tweet_update_timeframe)

    since_id = 1
    try:
        found = False
        result = client.query_api().query(org=org, query=query_latest_tweet)
        for table in result:
            for record in table.records:
                since_id = record["status_id"]
                found = True
                print("tweets newer than this tweet id are updated " + str(record["status_id"]))
        if not found:
            raise Exception('No tweet id for updates for older tweets found')    
    except Exception as e:
        print(e)
    
    return since_id

def create_point(status, cash_tag, search_type):
    current_time = datetime.datetime.now().strftime('%s')
    return {
        "measurement": "cashtag_grab",
        "tags": {
            "cashtag": cash_tag,
            "user": status.user.screen_name,
            "status_id": status.id,
            "insert_time": current_time,
            "search_type": search_type
        },
        "time": status.created_at,                                                    
        "fields": {                                                             
            "retweet_count": status.retweet_count,
            "favorite_count": status.favorite_count,                                
        }
    }



def main():    
    # init stuff for influx
    print("******************* STARTING RUN *******************")
    client = InfluxDBClient(url="http://influxdb:8086", token=admin_token, org=org)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    points = []
    
    since_id = get_tweet_id_to_fetch_since(client)

    if do_prefetch_extraction:
        prefetched_tickers = get_tickers()

    latest_tweet_time = None
    for page in tweepy.Cursor(api.home_timeline, count=200, tweet_mode="extended", since_id=since_id).pages(call_amount):
        for status in page:
            if status.user.screen_name in ignores:
                continue
            matched = []
            #dbg
            #blockline = '\n________________________________________\n'
            print('Checking tweet: ' + str(status.id) + ' from ' + status.user.screen_name + ' at ' + str(status.created_at))     
            for match in re.finditer(cashtag_reg_precise, status.full_text, re.MULTILINE):   
                cash_tag = match.group().lower()
                if cash_tag not in matched:
                    matched.append(cash_tag)                                         
                    points.append(create_point(status, cash_tag, "precise"))
                    print("found precise " + cash_tag)
            
            if do_prefetch_extraction:
                for ticker in prefetched_tickers:
                    cashtag_reg_prefetched = r"[^a-zA-Z$@0-9]" + re.escape(ticker) + r"[^a-zA-Z0-9]"
                    if re.search(cashtag_reg_prefetched, status.full_text.lower()) != None:
                        points.append(create_point(status, '$' + ticker, "prefetched"))
                        print("found prefetched $" + ticker)

            # know when the latest tweet was posted so the tool only fetches tweets after that in the next run
            if latest_tweet_time == None or latest_tweet_time < status.created_at:
                latest_tweet_time = status.created_at
                since_id = status.id

    # influx db write and close
    write_api.write(bucket=bucket, record=points)
    client.close()
    print("******************* FINISHED RUN *******************")

main()

# redo whole process every hour (old, now done with cron job)
# time_one_min_before = datetime.datetime.now() - datetime.timedelta(minutes=1)
# schedule.every().hour.at(time_one_min_before.strftime("%M:%S")).do(main)

# while True:
#     schedule.run_pending()
#     time.sleep(10 * 1000)