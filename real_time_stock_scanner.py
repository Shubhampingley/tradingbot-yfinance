import yfinance as yf
import pandas as pd
import numpy as np
import requests
import matplotlib.pyplot as plt

# Function to load stock symbols from a CSV file
def load_stock_symbols(csv_file):
    df = pd.read_csv(csv_file)
    print(f"Columns in CSV: {df.columns}")  # Check the columns in the CSV
    stock_list = df['SYMBOL'].tolist()  # Accessing the 'SYMBOL' column
    return stock_list

# Function to calculate MACD
def calculate_macd(df, short_period=12, long_period=26, signal_period=9):
    df['Short_EMA'] = df['Close'].ewm(span=short_period, min_periods=1).mean()
    df['Long_EMA'] = df['Close'].ewm(span=long_period, min_periods=1).mean()
    df['MACD'] = df['Short_EMA'] - df['Long_EMA']
    df['Signal'] = df['MACD'].ewm(span=signal_period, min_periods=1).mean()
    return df

# Function to detect support and resistance
def support_resistance(df):
    df['Support'] = df['Low'].rolling(window=20).min()
    df['Resistance'] = df['High'].rolling(window=20).max()
    return df

# Function to calculate Fibonacci retracement levels for target setting
def fibonacci_retracement(df):
    max_price = df['High'].max()
    min_price = df['Low'].min()

    diff = max_price - min_price
    levels = {
        "Level_0%": max_price,
        "Level_23.6%": max_price - 0.236 * diff,
        "Level_38.2%": max_price - 0.382 * diff,
        "Level_50%": max_price - 0.5 * diff,
        "Level_61.8%": max_price - 0.618 * diff,
        "Level_100%": min_price
    }
    return levels

# Function to send Telegram alert
def send_telegram_alert(message, telegram_token, telegram_chat_id):
    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
    payload = {"chat_id": telegram_chat_id, "text": message}
    requests.post(url, json=payload)

# Function to implement the swing trading strategy (real-time analysis)
def real_time_stock_scanner(ticker, telegram_token, telegram_chat_id):
    # Fetch the latest stock data for the ticker (today's data)
    df = yf.download(ticker, period="1d", interval="5m")  # 1 day, 5-minute interval
    
    # Apply MACD and Support/Resistance to today's data
    df = calculate_macd(df)
    df = support_resistance(df)
    fib_levels = fibonacci_retracement(df)
    
    # Generate Buy and Sell Signals based on simplified conditions
    df['Buy_Signal'] = (df['MACD'] > df['Signal']) & (df['Close'] > df['Support'])
    df['Sell_Signal'] = (df['MACD'] < df['Signal']) & (df['Close'] < df['Resistance'])
    
    # Check if any signals are present
    if df[df['Buy_Signal']].shape[0] > 0:
        send_telegram_alert(f"{ticker} - BUY Signal: {df['Close'].iloc[-1]}", telegram_token, telegram_chat_id)
    
    if df[df['Sell_Signal']].shape[0] > 0:
        send_telegram_alert(f"{ticker} - SELL Signal: {df['Close'].iloc[-1]}", telegram_token, telegram_chat_id)
    
    # Plot the data for visual confirmation
    plt.figure(figsize=(10,6))
    plt.plot(df['Close'], label=f'{ticker} Close Price', color='black')
    plt.plot(df['Support'], label='Support', color='green', linestyle='--')
    plt.plot(df['Resistance'], label='Resistance', color='red', linestyle='--')
    plt.scatter(df.index[df['Buy_Signal']], df['Close'][df['Buy_Signal']], marker='^', color='green', label='Buy Signal', alpha=1)
    plt.scatter(df.index[df['Sell_Signal']], df['Close'][df['Sell_Signal']], marker='v', color='red', label='Sell Signal', alpha=1)
    plt.title(f'{ticker} - Real-time Swing Trading Strategy')
    plt.legend()
    plt.show()
    
    # Display Fibonacci levels for setting targets
    print("Fibonacci Levels:")
    for level, value in fib_levels.items():
        print(f"{level}: {value}")
    
    return df

# Function to scan a list of stocks in real-time from CSV
def scan_real_time_stocks(csv_file, telegram_token, telegram_chat_id):
    stock_list = load_stock_symbols(csv_file)
    
    for ticker in stock_list:
        print(f"Scanning {ticker}...")
        df = real_time_stock_scanner(ticker, telegram_token, telegram_chat_id)
        print(f"Finished scanning {ticker}\n")

# Example Usage: Pass the CSV file path here
csv_file = 'nifty500.csv'  # CSV with the list of stock symbols (e.g., TATAMOTORS.NS, INFY.NS)
telegram_token = "YOUR_TELEGRAM_TOKEN"
telegram_chat_id = "YOUR_TELEGRAM_CHAT_ID"

# Start scanning the stocks from the CSV
scan_real_time_stocks(csv_file, telegram_token, telegram_chat_id)
