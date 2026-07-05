# data_processing.py

import pandas as pd
import glob

class DataLoader:
    def __init__(self, file_path_pattern):
        self.file_path_pattern = file_path_pattern
        self.data = None
    
    def load_data(self):
        csv_files = glob.glob(self.file_path_pattern)
        dataframes = []
        for file in csv_files:
            df = pd.read_csv(file)
            df.columns = df.columns.str.lower()
            dataframes.append(df)
        self.data = pd.concat(dataframes, ignore_index=True)  # df
        return self.data

class DataProcessor:
    def __init__(self, data, scale=False):
        self.data = data
        self.scale = scale  # Whether to scale the data or not
    
    def process_data(self):
        # "Datetime (UTC)" to datetime
        self.data.columns = self.data.columns.str.strip().str.lower()
        self.data['datetime (utc)'] = pd.to_datetime(self.data['datetime (utc)'])
        self.data['hour'] = self.data['datetime (utc)'].dt.hour  # Extract the hour of the day
        self.data['month'] = self.data['datetime (utc)'].dt.month

        # Assign seasons based on month
        self.data['season'] = self.data['month'].apply(self.assign_season)

        # Rename long column names to simplified names
        self.data = self.data.rename(columns={
            'carbon intensity gco₂eq/kwh (direct)': 'carbon intensity',
        })

        if 'renewable energy percentage (re%)' in self.data.columns:
            # If 'renewable percentage' already exists, fill its NaNs with values from the other column before dropping
            if 'renewable percentage' in self.data.columns:
                self.data['renewable percentage'] = self.data['renewable percentage'].combine_first(
                    self.data['renewable energy percentage (re%)']
                )
                self.data = self.data.drop(columns=['renewable energy percentage (re%)'])
            else:
                self.data = self.data.rename(columns={'renewable energy percentage (re%)': 'renewable percentage'})

        
        # Select the relevant columns
        self.data = self.data[['country', 'month', 'season', 'hour', 'carbon intensity', 'renewable percentage']]

        return self.data
    
    @staticmethod
    def assign_season(month):
        """Assign a season based on the month."""
        if month in [12, 1, 2]:
            return 'Winter'
        elif month in [3, 4, 5]:
            return 'Spring'
        elif month in [6, 7, 8]:
            return 'Summer'
        elif month in [9, 10, 11]:
            return 'Autumn'