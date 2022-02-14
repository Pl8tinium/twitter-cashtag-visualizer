import re
import requests

query = ['[^a-zA-Z$]', 'TRX', '^a-zA-Z']


query = ''.join(query)

abc = """ 

Top 5 Mentions Updated Every 15 Minutes

  [BETA STAGE] Except BTC and ETH  

     TRX    
  1- $DOGE:409592 point 🚀 TRX

  2- $ONG:241055 point 🚀

  3- $SKL:108402 point 🚀

TRX:96152 point 🚀

  5- $GO:96008 point 🚀

$TRX

TRX$TRX


$TRX

.TRX



trx
$TRX

"""

#print(re.search(query, abc))

# get tickers from coingecko
# get tickers from coingecko

# f = open('./most_common_words/mostcommon1000.txt', "r").read()
# print(f.split('\n'))


def get_tickers():    
    data = requests.get('https://api.coingecko.com/api/v3/coins/list').json()
    tickers = []
    for coin in data:
        tickers.append(coin['symbol'].replace('$', '').lower())

    common_words = open('./most_common_words/mostcommon3000.txt', "r").read().lower().split('\n')

    print(len(tickers))
    cleaned_tickers = []
    for ticker in tickers:
        if not ticker in common_words:
            cleaned_tickers.append(ticker)

    print(len(cleaned_tickers))

get_tickers()


