# Import packages necessary
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
import schedule
import talib

# Get the date in readable form
def serial_date_to_string(srl_no):
  new_date = datetime.datetime(1970,1,1,0,0) + datetime.timedelta(srl_no - 1)
  return new_date.strftime("%Y-%m-%d")

# Find support levels
def isSupport(df,i):
  support = df['Low'][i] < df['Low'][i-1]  and df['Low'][i] < df['Low'][i+1] \
  and df['Low'][i+1] < df['Low'][i+2] and df['Low'][i-1] < df['Low'][i-2]
  return support

# Find resistance levels
def isResistance(df,i):
  resistance = df['High'][i] > df['High'][i-1]  and df['High'][i] > df['High'][i+1] \
  and df['High'][i+1] > df['High'][i+2] and df['High'][i-1] > df['High'][i-2]
  return resistance

# Check what type of candle it is
def is_bearish_candle(candle):
  return candle['Close'] < candle['Open']
  # A bearish candle is when the closing price is lower than the opening price

def is_bullish_candle(candle):
  return candle['Close'] > candle['Open']
  # A bullish candle is when the closing price is higher than the opening price

# Find whether it is an engulfing candle

# Indicates a sharp upwards change in stock price movement
def is_bullish_engulfing(candles):
  current_day = candles[-1]
  previous_day = candles[-2]
  if is_bearish_candle(previous_day) \
      and is_bullish_candle(current_day) \
      and float(current_day['Close']) >= float(previous_day['Open']) \
      and float(current_day['Open']) <= float(previous_day['Close']):
      return True
  return False

# Indicates a sharp downwards change in stock price movement
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
    # Find whether there are support levels
    for x in range(len(supports)):
      if recent_close-supports[x][0] < recent_close-closestsup:
        closestsup = supports[x][0]
    # If so, save whichever support level is closest to the current stock price
    return closestsup

def closest_resistance(recent_close, resistances):
  if (len(resistances) > 0) == True:
    closestres = resistances[0][0]
    # Find whether there are resistance levels
    for x in range(len(resistances)):
      if recent_close-resistances[x][0] < abs(recent_close-closestres):
        closestres = resistances[x][0]
    # If so, save whichever resistance level is closest to the current stock price 
    return closestres

# Find how far the support or resistance price in question is from the current price
def isFarFromLevel(l):
  return np.sum([abs(l-x) < s  for x in levels]) == 0

# Create moving averages
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

# Use moving averages to create moving average crossovers
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

# Create RSI and ATR by retrieving them through the TA-lib package
def rsi(df):
  rsi = talib.RSI(df["Close"], timeperiod=14)
  return round(rsi[-1], 2)

def atr(df):
  atr = talib.ATR(df["High"], df["Low"], df["Close"], timeperiod=14)
  atr = round(atr, 2)
  atrp = round(float(atr[-1])/float(df["Close"][-1])*100, 2)
  return " ATR: {} ({}%)".format(atr[-1], atrp)

# Create bollinger bands

# See if the current stock price is lower than the low band price, if so, buy it
def bb_call(df):
  upper, middle, lower = talib.BBANDS(df['Close'], matype=talib.MA_Type.T3)
  recent_low = df["Low"][-1]
  if recent_low <= lower[-1]:
    return True
  return False

# See if the current stock price is higher than the high band price, if so, short it
def bb_short(df):
  upper, middle, lower = talib.BBANDS(df['Close'], matype=talib.MA_Type.T3)
  recent_high = df["High"][-1]
  if recent_high >= upper[-1]:
    return True
  return False

# Create orders through Alpaca
def buy_stock(ticker, shares, api):
  order = api.submit_order(ticker, shares, 'buy', 'market', 'day')

def sell_stock(ticker, shares, api):
  order = api.submit_order(ticker, shares, 'sell', 'market', 'day')

# Close open positions in the Alpaca account
def close_position(ticker, shares, unrealized_plpc, api):
  shares = float(shares)
  unrealized_plpc = float(unrealized_plpc)
  webhookurl = 'YOUR-DISCORD-WEBHOOK-URL'
  gainp = unrealized_plpc*100
  if shares > 0:
    if unrealized_plpc >= 0.05:
      sell_stock(ticker, shares, api)
      webhook = DiscordWebhook(url=webhookurl, content='Closed long position on ' + str(ticker) + ' for a gain of ' + str(round(gainp, 3)) + '%')
      response = webhook.execute()   
    if unrealized_plpc <= (-0.01):
      sell_stock(ticker, shares, api)
      webhook = DiscordWebhook(url=webhookurl, content='Closed long position on ' + str(ticker) + ' for a loss of ' + str(round(gainp, 3)) + '%')
      response = webhook.execute()
  if shares < 0:
    shares = abs(shares)
    if unrealized_plpc >= 0.05:
      buy_stock(ticker, shares, api)
      webhook = DiscordWebhook(url=webhookurl, content='Closed short position on ' + str(ticker) + ' for a gain of ' + str(round(gainp, 3)) + '%')
      response = webhook.execute()
    if unrealized_plpc <= (-0.01):
      buy_stock(ticker, shares, api)
      webhook = DiscordWebhook(url=webhookurl, content='Closed short position on ' + str(ticker) + ' for a loss of ' + str(round(gainp, 3)) + '%')
      response = webhook.execute()

def job_function():
  # For plotting features (if implemented)
  plt.rcParams['figure.figsize'] = [12, 7]
  plt.rc('font', size=14)
  # Open and sort through company list and current portfolio positions
  companies = csv.reader(open('companies.csv'))
  api = tradeapi.REST('YOUR-ALPACA-KEY','YOUR-ALPACA-SECRET-KEY', 'https://paper-api.alpaca.markets', api_version='v2')# Lists currently open trades
  positions = api.list_positions()
  for position in positions:
    print(position.symbol, position.unrealized_plpc)
    close_position(position.symbol, position.qty, position.unrealized_plpc, api)
    time.sleep(1)
  names = []
  open_positions = []
  # Turn the CSV of companies into a list of tickers
  for company in companies:
    symbol, name = company
    names.append(symbol)

  # Start looping through each ticker
  for name in names:
    time.sleep(0.01)
    ticker = yfinance.Ticker(name)
    # Input stock data into a dataframe
    df = ticker.history(interval="1wk", period="50wk")
    df['Date'] = pd.to_datetime(df.index)
    df['Date'] = df['Date'].apply(mpl_dates.date2num)
    df = df.loc[:,['Date', 'Open', 'High', 'Low', 'Close']]
    candles = [OrderedDict(row) for i, row in df.iterrows()]
    r = rsi(df)
    
    # Find support and resistance levels and make them into a list
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
    
    # Find the closest support and resistance levels to the stock price
    closestsup = closest_support(recent_close, supports)
    closestres = closest_resistance(recent_close, resistances)
    if closestres is not None:
      respoint = round(closestres, 2)
    if closestsup is not None:
      suppoint = round(closestsup, 2)
    webhookurl = 'YOUR-DISCORD-WEBHOOK-URL'
    
    # Test whether the indicators have triggered and buy/sell accordingly
    if is_bearish_engulfing(candles):
      webhook = DiscordWebhook(url=webhookurl, content='Bearish Engulfing on ' + str(name) + ', Support: ' + str(suppoint) + ', Resistance: ' + str(respoint) + atr(df))
      response = webhook.execute()
      shareno = int(1000/recent_close)
      sell_stock(name, shareno, api)
      print("Bearish Engulfing on "+ str(name))
    if is_bullish_engulfing(candles):
      webhook = DiscordWebhook(url=webhookurl, content='Bullish Engulfing on ' + str(name) + ', Support: ' + str(suppoint) + ', Resistance: ' + str(respoint) + atr(df))
      response = webhook.execute()
      shareno = int(1000/recent_close)
      buy_stock(name, shareno, api)
      print("Bullish Engulfing on "+ str(name)) 
    if float(r) < 25:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is oversold (RSI: ' + str(round(r, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(1000/recent_close)
      buy_stock(name, shareno, api)
      print("Oversold "+ str(name))
    if float(r) > 75:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is overbought (RSI: ' + str(round(r, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(1000/recent_close)
      sell_stock(name, shareno, api)
      print("Overbought "+ str(name))
    if bb_call(df) == True:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is at the bottom of the Bollinger Band (RSI: ' + str(round(r, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(5000/recent_close)
      buy_stock(name, shareno, api)
      print("BB Call "+ str(name))
    if bb_short(df) == True:
      webhook = DiscordWebhook(url=webhookurl, content= str(name) + ' is at the top of the Bollinger Band (RSI: ' + str(round(r, 2)) + atr(df) + ')')
      response = webhook.execute()
      shareno = int(5000/recent_close)
      sell_stock(name, shareno, api)
      print("BB Short "+ str(name))

#Run the program
job_function()
