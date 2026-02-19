import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_squared_error
from datetime import datetime
import os
import sys
import warnings

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_client import db

# Suppress technical warnings for a cleaner output
warnings.filterwarnings("ignore")


class ForecastingEngine:
    def __init__(self, transactions_file=None):
        # We ignore transactions_file as we use DB now
        if not db:
             raise ConnectionError("❌ Database connection failed.")

        print("🔮 Initializing Forecasting Engine (Database Backed)...")
        self.df = self._load_data_from_db()
        print(f"✅ Forecasting Data Loaded: {len(self.df)} records.")

    def _load_data_from_db(self):
        try:
            # Fetch all transactions using multiple requests (Pagination)
            # Supabase defaults to 1000 records per request.
            # We need the full history (20,000+ rows) for forecasting.
            
            all_data = []
            page_size = 1000
            offset = 0
            
            while True:
                # Fetch a chunk
                response = db.table("transactions")\
                    .select("transaction_date, quantity, products(name)")\
                    .order("transaction_date", desc=True)\
                    .range(offset, offset + page_size - 1)\
                    .execute()
                
                chunk = response.data
                if not chunk:
                    break
                    
                for row in chunk:
                    # Handle possible missing product linkage
                    prod_name = row['products']['name'] if row.get('products') else "Unknown"
                    
                    all_data.append({
                        "Date": row['transaction_date'],
                        "Qty_Sold": row['quantity'],
                        "Product_Name": prod_name
                    })
                
                if len(chunk) < page_size:
                    break
                    
                offset += page_size
                print(f"   ...Fetched {len(all_data)} records...")

            df = pd.DataFrame(all_data)
            if not df.empty:
                df['Date'] = pd.to_datetime(df['Date'])
            return df

        except Exception as e:
            print(f"❌ Error loading forecasting data: {e}")
            return pd.DataFrame()

    def create_features(self, df):
        """
        TRANSFORMATION: Converts simple date-sales data into ML Features.
        The model learns from these 'Clues'.
        """
        df = df.copy()
        # Clue 1: Seasonality (Month of year)
        df['Month'] = df.index.month

        # Clue 2: The Trend (Year)
        df['Year'] = df.index.year

        # Clue 3: Lag_12 (What did we sell exactly 1 year ago?) - Captures Seasonality
        df['Lag_12'] = df['Qty_Sold'].shift(12)

        # Clue 4: Lag_1 (What did we sell last month?) - Captures Immediate Trend
        df['Lag_1'] = df['Qty_Sold'].shift(1)

        # Clue 5: Rolling Average (Average of last 3 months) - Smooths out noise
        df['Rolling_Mean_3'] = df['Qty_Sold'].shift(1).rolling(window=3).mean()

        return df

    def predict_demand(self, product_name, months_ahead=3):
        """
        Main function: Takes a product name, trains a custom model, and predicts future.
        """
        # 1. Filter Data for this specific medicine
        prod_data = self.df[self.df['Product_Name'] == product_name].copy()

        if prod_data.empty:
            return None, "Not enough data", 0

        # 2. Resample to Monthly Data (Standard for Inventory Planning)
        if 'Date' in prod_data.columns:
            monthly_sales = prod_data.set_index('Date').resample('MS')['Qty_Sold'].sum().to_frame()
        else:
             return None, "Date column missing", 0

        # We need at least 15 months to create Lags (12 months + 3 months buffer)
        if len(monthly_sales) < 15:
            return None, "Requires >15 months of history for high accuracy", 0

        # 3. Create Features (The 'Clues')
        data_with_features = self.create_features(monthly_sales)

        # Drop empty rows created by shifting (The first 12 months have no 'Lag_12')
        data_with_features.dropna(inplace=True)

        # 4. Prepare Training Data
        FEATURES = ['Month', 'Year', 'Lag_12', 'Lag_1', 'Rolling_Mean_3']
        TARGET = 'Qty_Sold'

        X = data_with_features[FEATURES]
        y = data_with_features[TARGET]

        # 5. Train XGBoost Model (The Learning Phase)
        model = xgb.XGBRegressor(
            n_estimators=100,  # Number of decision trees
            learning_rate=0.05,  # Learning speed (slower is often more accurate)
            max_depth=5,  # Depth of trees
            objective='reg:squarederror'
        )
        model.fit(X, y)

        # --- ACCURACY CHECK ---
        # Test how well it learned the past
        predictions = model.predict(X)
        rmse = np.sqrt(mean_squared_error(y, predictions))
        avg_sales = y.mean()
        # Convert Error to Accuracy % (100 - Error%)
        accuracy_score = max(0, 100 * (1 - (rmse / avg_sales)))

        # 6. Future Forecasting (Recursive Loop)
        # We predict Month 1, add it to history, then use it to predict Month 2...
        future_dates = pd.date_range(
            start=monthly_sales.index[-1] + pd.DateOffset(months=1),
            periods=months_ahead,
            freq='MS'
        )
        forecast_values = []

        # Start with current history
        current_history = monthly_sales.copy()

        for date in future_dates:
            # Re-generate features with new history
            temp_features = self.create_features(current_history)

            # Grab the last row (which represents the 'Next' unknown month)
            # We construct the feature vector manually to ensure shape is correct
            last_real_qty = current_history.iloc[-1]['Qty_Sold']
            qty_12_months_ago = current_history.iloc[-12]['Qty_Sold'] if len(current_history) > 12 else 0

            # Create a single row DataFrame for prediction
            next_input = pd.DataFrame([{
                'Month': date.month,
                'Year': date.year,
                'Lag_12': qty_12_months_ago,
                'Lag_1': last_real_qty,
                'Rolling_Mean_3': current_history['Qty_Sold'].iloc[-3:].mean()
            }])

            # Predict
            pred_qty = model.predict(next_input)[0]
            pred_qty = max(0, int(pred_qty))  # Ensure no negative sales

            forecast_values.append(pred_qty)

            # Add prediction to history so the next loop can see it
            new_row = pd.DataFrame({'Qty_Sold': [pred_qty]}, index=[date])
            current_history = pd.concat([current_history, new_row])

        # 7. Format Output
        forecast_df = pd.DataFrame({
            'Date': future_dates,
            'Predicted_Demand': forecast_values
        })

        return forecast_df, int(avg_sales), round(accuracy_score, 1)

    def get_top_products(self, n=30):
        """
        Returns the top N selling products based on total quantity sold.
        """
        if self.df.empty:
            return []
            
        top_products = (
            self.df.groupby('Product_Name')['Qty_Sold']
            .sum()
            .sort_values(ascending=False)
            .head(n)
            .index
            .tolist()
        )
        return top_products

    def predict_next_month_allocation(self, product_name):
        """
        Simplified prediction for just the NEXT month (30 days).
        Returns: (predicted_qty, accuracy_score)
        """
        # Reuse logic from predict_demand but optimize for single value return
        df, _, acc = self.predict_demand(product_name, months_ahead=1)
        
        if df is None or df.empty:
            return 0, 0
            
        predicted_qty = df.iloc[0]['Predicted_Demand']
        return int(predicted_qty), acc


# --- TEST ZONE (Run this file to verify) ---
if __name__ == "__main__":
    fe = ForecastingEngine()
    print("\n🔮 TEST: Forecasting Demand for 'Dolo 650 (Paracetamol)'...")

    df, avg, acc = fe.predict_demand("Dolo 650 (Paracetamol)")

    if df is not None:
        print(f"✅ Model Accuracy: {acc}%")
        print(f"📊 Average Monthly Sales: {avg}")
        print("\n🔮 Next 3 Months Forecast:")
        print(df)
    else:
        print(f"❌ Error: {avg}")