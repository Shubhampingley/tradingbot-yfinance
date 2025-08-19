import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# Function to fetch historical data and apply moving average crossover strategy
def moving_average_crossover(ticker, short_window=50, long_window=200):
    """Moving Average Crossover Strategy."""
    
    # Fetch historical data for the ticker
    df = yf.download(ticker, period="1y", interval="1d")  # 1 year of daily data
    
    # Calculate short-term and long-term moving averages
    df['Short_MA'] = df['Close'].rolling(window=short_window, min_periods=1).mean()
    df['Long_MA'] = df['Close'].rolling(window=long_window, min_periods=1).mean()

    # Generate signals based on crossovers
    df['Signal'] = 0  # Default: no signal
    df['Signal'][short_window:] = np.where(df['Short_MA'][short_window:] > df['Long_MA'][short_window:], 1, 0)  # Buy Signal
    df['Position'] = df['Signal'].diff()  # Buy when 1, Sell when -1
    
    # Print signals
    print(f"Buy signals for {ticker}:")
    print(df[df['Position'] == 1][['Close', 'Short_MA', 'Long_MA', 'Position']])
    
    print(f"Sell signals for {ticker}:")
    print(df[df['Position'] == -1][['Close', 'Short_MA', 'Long_MA', 'Position']])
    
    # Plotting the data
    plt.figure(figsize=(10, 6))
    plt.plot(df['Close'], label=f'{ticker} Close Price', color='black')
    plt.plot(df['Short_MA'], label=f'Short {short_window} Day MA', color='blue')
    plt.plot(df['Long_MA'], label=f'Long {long_window} Day MA', color='red')
    plt.title(f'{ticker} - Moving Average Crossover Strategy')
    plt.legend()
    plt.show()
    
    return df

# Example Usage
ticker = "TATAMOTORS.NS"  # Change this to any Indian stock or US stock (e.g., AAPL)
df = moving_average_crossover(ticker)
