import pandas as pd
import numpy as np
import yfinance
import mplfinance
import matplotlib.dates as mpl_dates
import matplotlib.pyplot as plt
from datetime import datetime
from discord_webhook import DiscordWebhook
from collections import OrderedDict
import time
import csv
import alpaca_trade_api as tradeapi
from apscheduler.schedulers.background import BackgroundScheduler
import talib


def serial_date_to_string(srl_no):
  new_date = datetime.datetime(1970,1,1,0,0) + datetime.timedelta(srl_no - 1)
  return new_date.strftime("%Y-%m-%d")

def isSupport(df,i):
  support = df['Low'][i] < df['Low'][i-1]  and df['Low'][i] < df['Low'][i+1] \
  and df['Low'][i+1] < df['Low'][i+2] and df['Low'][i-1] < df['Low'][i-2]
  return support

def isResistance(df,i):
  resistance = df['High'][i] > df['High'][i-1]  and df['High'][i] > df['High'][i+1] \
  and df['High'][i+1] > df['High'][i+2] and df['High'][i-1] > df['High'][i-2]
  return resistance

def is_bearish_candle(candle):
  return candle['Close'] < candle['Open']

def is_bullish_candle(candle):
  return candle['Close'] > candle['Open']

def is_bullish_engulfing(candles):
  current_day = candles[-1]
  previous_day = candles[-2]
  if is_bearish_candle(previous_day) \
      and is_bullish_candle(current_day) \
      and float(current_day['Close']) >= float(previous_day['Open']) \
      and float(current_day['Open']) <= float(previous_day['Close']):
      return True
  return False

def is_bearish_engulfing(candles):
  current_day = candles[-1]
  previous_day = candles[-2]
  if is_bullish_candle(previous_day) \
      and is_bearish_candle(current_day) \
      and float(current_day['Open']) >= float(previous_day['Close']) \
      and float(current_day['Close']) <= float(previous_day['Open']):
      return True
  return False

def closest_support(recent_close, supports):
  if (len(supports) > 0) == True:
    closestsup = supports[0][0]
    for x in range(len(supports)):
      if recent_close-supports[x][0] < recent_close-closestsup:
        closestsup = supports[x][0]
    return closestsup

def closest_resistance(recent_close, resistances):
  if (len(resistances) > 0) == True:
    closestres = resistances[0][0]
    for x in range(len(resistances)):
      if recent_close-resistances[x][0] < abs(recent_close-closestres):
        closestres = resistances[x][0]
    return closestres

def sma_20(candles):
  total = 0
  for i in range(1, 20):
    total += candles[-i]['Close']
  total /= 20
  return round(total, 2)

def sma_50(candles):
  total = 0
  for i in range(1, 50):
    total += candles[-i]['Close']
  total /= 50
  return round(total, 2)

def golden_cross(candles):
  sma20_1 = sma_20(candles)
  sma50 = sma_50(candles)
  candles.pop()
  sma20_2 = sma_20(candles)
  if sma20_2 < sma20_1 \
    and sma20_2 < sma50 \
    and sma20_1 > sma50:
    return True
  return False

def death_cross(candles):
  sma20_1 = sma_20(candles)
  sma50 = sma_50(candles)
  candles.pop()
  sma20_2 = sma_20(candles)
  if sma20_2 > sma20_1 \
    and sma20_2 > sma50 \
    and sma20_1 < sma50:
    return True
  return False

def isFarFromLevel(l):
  return np.sum([abs(l-x) < s  for x in levels]) == 0

def rsi(df):
  rsi = talib.RSI(df["Close"], timeperiod=14)
  return round(rsi[-1], 2)

def atr(df):
  atr = talib.ATR(df["High"], df["Low"], df["Close"], timeperiod=14)
  atr = round(atr, 2)
  atrp = round(float(atr[-1])/float(df["Close"][-1])*100, 2)
  return " ATR: {} ({}%)".format(atr[-1], atrp)

def buy_stock(ticker, shares, api):
  order = api.submit_order(ticker, shares, 'buy', 'market', 'day')

def sell_stock(ticker, shares, api):
  order = api.submit_order(ticker, shares, 'sell', 'market', 'day')

def close_position(ticker, shares, unrealized_plpc, api):
  shares = float(shares)
  unrealized_plpc = float(unrealized_plpc)
  if shares > 0:
    if unrealized_plpc >= 0.02:
      sell_stock(ticker, shares, api)
    if unrealized_plpc <= (-0.0075):
      sell_stock(ticker, shares, api)
  if shares < 0:
    shares = abs(shares)
    if unrealized_plpc <= 0.02:
      buy_stock(ticker, shares, api)
    if unrealized_plpc >= (-0.0075):
      buy_stock(ticker, shares, api)

def bb_call(df):
  upper, middle, lower = talib.BBANDS(df['Close'], matype=talib.MA_Type.T3)
  recent_low = df["Low"][-1]
  if recent_low <= lower[-1]:
    return True
  return False

def bb_short(df):
  upper, middle, lower = talib.BBANDS(df['Close'], matype=talib.MA_Type.T3)
  recent_high = df["High"][-1]
  print(upper[-1])
  print(recent_high)
  if recent_high >= upper[-1]:
    return True
  return False

def job_function():
  plt.rcParams['figure.figsize'] = [12, 7]
  plt.rc('font', size=14)
  companies = csv.reader(open('companies.csv'))
  api = tradeapi.REST('PKN80O8AA5ZBE5UU8ZQ0','innUuDaMCot1VBnmgORE5qCbNdXNa7GXIrLATJ8j', 'https://paper-api.alpaca.markets', api_version='v2')# Lists currently open trades
  positions = api.list_positions()
  for position in positions:
    print(position.symbol, position.unrealized_plpc)
    close_position(position.symbol, position.qty, position.unrealized_plpc, api)
    time.sleep(1)
  names = []
  open_positions = []
  for company in companies:
    symbol, name = company
    names.append(symbol)

  for name in names:
    time.sleep(0.01)
    print(name)
    ticker = yfinance.Ticker(name)
    df = ticker.history(interval="1d", period="3mo")
    df['Date'] = pd.to_datetime(df.index)
    df['Date'] = df['Date'].apply(mpl_dates.date2num)
    df = df.loc[:,['Date', 'Open', 'High', 'Low', 'Close']]
    candles = [OrderedDict(row) for i, row in df.iterrows()]

    rsis = talib.RSI(df["Close"], timeperiod=14)
    rsi = rsis[-1]
    levels = []
    plainlevels = []
    for i in range(2,df.shape[0]-2):
      if isSupport(df,i):
        levels.append((df['Date'][i],df['Low'][i]))
        plainlevels.append(df['Low'][i])
      elif isResistance(df,i):
        levels.append((df['Date'][i],df['High'][i]))
        plainlevels.append(df['High'][i])
    s =  np.mean(df['High'] - df['Low'])
    recent_close = candles[-1]['Close']
    supports = []
    resistances = []
    for i in plainlevels:
      difference = round(recent_close-i, 2)
      if i < recent_close:
        supports.append((i, difference))
      elif i > recent_close:
        round(i-recent_close, 2)
        resistances.append((i, difference))
    closestsup = closest_support(recent_close, supports)
    closestres = closest_resistance(recent_close, resistances)
    if closestres is not None:
      respoint = round(closestres, 2)
    if closestsup is not None:
      suppoint = round(closestsup, 2)
    webhookurl = 'https://discord.com/api/webhooks/946504205819084863/a9kznVU_l8jpLimoLMshT8NoqeaE9tltipW_PpqX_qTxOKDm2clErlkH4NSR4SWAXN6H'
    if is_bearish_engulfing(candles):
      webhook = DiscordWebhook(url=webhookurl, content='Bearish Engulfing on ' + str(name) + ', Support: ' + str(suppoint) + ', Resistance: ' + str(respoint) + atr(df))
      response = webhook.execute()
      shareno = int(5000/recent_close)
      sell_stock(name, shareno, api)
      print("Bearish Engulfing on "+ str(name))
    if is_bullish_engulfing(candles):
      webhook = DiscordWebhook(url=webhookurl, content='Bullish Engulfing on ' + str(name) + ', Support: ' + str(suppoint) + ', Resistance: ' + str(respoint) + atr(df))
      response = webhook.execute()
      shareno = int(5000/recent_close)
      buy_stock(name, shareno, api)
      print("Bullish Engulfing on "+ str(name)) 
    if float(rsi) < 30:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is oversold (RSI: ' + str(round(rsi, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(5000/recent_close)
      buy_stock(name, shareno, api)
      print("Oversold "+ str(name))
    if float(rsi) > 70:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is overbought (RSI: ' + str(round(rsi, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(5000/recent_close)
      sell_stock(name, shareno, api)
      print("Overbought "+ str(name))
    """if bb_call(df) == True:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is at the bottom of the Bollinger Band (RSI: ' + str(round(rsi, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(5000/recent_close)
      buy_stock(name, shareno, api)
      print("BB Call "+ str(name))
    if bb_short(df) == True:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is at the top of the Bollinger Band (RSI: ' + str(round(rsi, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(5000/recent_close)
      sell_stock(name, shareno, api)
      print("BB Short "+ str(name))"""


while True:
  job_function()
  time.sleep(60*15)  # Wait for 15 minutes


"""sched = BackgroundScheduler()
sched.start()
sched.add_job(job_function, 'cron', day_of_week='mon-fri', minute='*/15', hour='8-13')"""
