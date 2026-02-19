import os
import pandas as pd
import numpy as np
import random
import uuid
import sys
from datetime import datetime, timedelta

# --- CONFIGURATION ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "../data")
sys.path.append(SCRIPT_DIR)

# Try importing DB client, but don't crash if unrelated
try:
    from db_client import db
except ImportError:
    db = None

# ==============================================================================
# PART 1: CSV DATA GENERATION (The "Source" Data)
# ==============================================================================
class DatasetGenerator:
    """Generates raw CSV data for Products, Inventory, and Transactions."""
    
    CATALOG = [
        # === COMMON / OTC MEDICINES ===
        {"id": 101, "name": "Dolo 650 (Paracetamol)", "category": "Fever", "price": 30, "shelf_life": 365, "seasonal": "Viral", "requires_prescription": False},
        {"id": 102, "name": "Crocin Advance", "category": "Fever", "price": 20, "shelf_life": 365, "seasonal": "Viral", "requires_prescription": False},
        {"id": 103, "name": "Digene Gel (Mint)", "category": "Digestive", "price": 120, "shelf_life": 300, "seasonal": "None", "requires_prescription": False},
        {"id": 104, "name": "Pudin Hara Pearls", "category": "Digestive", "price": 25, "shelf_life": 250, "seasonal": "Summer", "requires_prescription": False},
        {"id": 105, "name": "Vicks VapoRub", "category": "Cold/Flu", "price": 45, "shelf_life": 500, "seasonal": "Winter", "requires_prescription": False},
        {"id": 106, "name": "Benadryl Cough Syrup", "category": "Cold/Flu", "price": 110, "shelf_life": 365, "seasonal": "Winter", "requires_prescription": False},
        {"id": 107, "name": "Otrivin Nasal Spray", "category": "Cold/Flu", "price": 95, "shelf_life": 365, "seasonal": "Winter", "requires_prescription": False},
        {"id": 108, "name": "Volini Spray", "category": "Pain Relief", "price": 160, "shelf_life": 400, "seasonal": "None", "requires_prescription": False},
        {"id": 109, "name": "Electral Powder (ORS)", "category": "Hydration", "price": 22, "shelf_life": 500, "seasonal": "Summer", "requires_prescription": False},
        {"id": 110, "name": "Betadine Ointment", "category": "First Aid", "price": 135, "shelf_life": 400, "seasonal": "None", "requires_prescription": False},
        
        # === PRESCRIPTION ONLY ===
        {"id": 201, "name": "Augmentin 625 Duo", "category": "Antibiotic", "price": 200, "shelf_life": 180, "seasonal": "None", "requires_prescription": True},
        {"id": 202, "name": "Azithral 500", "category": "Antibiotic", "price": 130, "shelf_life": 180, "seasonal": "Winter", "requires_prescription": True},
        {"id": 203, "name": "Thyronorm 50mcg", "category": "Thyroid", "price": 180, "shelf_life": 200, "seasonal": "None", "requires_prescription": True},
        {"id": 204, "name": "Telma 40 (BP)", "category": "Cardio", "price": 210, "shelf_life": 365, "seasonal": "None", "requires_prescription": True},
        {"id": 205, "name": "Glycomet 500 (Diabetes)", "category": "Diabetes", "price": 55, "shelf_life": 365, "seasonal": "None", "requires_prescription": True}
    ]

    def get_seasonal_multiplier(self, month, seasonality_type):
        if seasonality_type == "None": return 1.0
        if seasonality_type == "Winter":
            return random.uniform(1.8, 2.8) if month in [11, 12, 1, 2] else random.uniform(0.5, 0.8)
        if seasonality_type == "Summer":
            return random.uniform(1.8, 2.5) if month in [4, 5, 6] else random.uniform(0.6, 0.9)
        if seasonality_type == "Viral":
            return random.uniform(1.5, 2.2) if month in [7, 8, 9, 11, 12, 1] else 0.8
        return 1.0

    def generate(self):
        print("🚀 [Step 1] Generating Raw CSV Data...")
        os.makedirs(DATA_DIR, exist_ok=True)
        
        # 1. Products
        df_products = pd.DataFrame(self.CATALOG)
        df_products.to_csv(f"{DATA_DIR}/products.csv", index=False)
        print(f"   ✅ Generated 'products.csv' ({len(df_products)} items)")

        # 2. Inventory (Initial State)
        inventory_data = []
        today = datetime.now()
        for product in self.CATALOG:
            # Generic bucket logic for CSV
            inventory_data.append({
                "Batch_ID": f"B{product['id']}-NEW",
                "Product_ID": product['id'],
                "Qty": random.randint(50, 200),
                "Expiry_Date": (today + timedelta(days=product['shelf_life'])).strftime("%Y-%m-%d"),
                "Mfg_Date": (today - timedelta(days=30)).strftime("%Y-%m-%d")
            })
        pd.DataFrame(inventory_data).to_csv(f"{DATA_DIR}/inventory.csv", index=False)
        print(f"   ✅ Generated 'inventory.csv'")

        # 3. Transactions (History)
        records = []
        customers = [f"98765{str(i).zfill(5)}" for i in range(200)]
        start_date = today - timedelta(days=5 * 365) # 5 Years
        
        print("   ⏳ Generating 5 years of transactions...")
        txn_id = 100001
        
        for day_offset in range((today - start_date).days):
            curr_date = start_date + timedelta(days=day_offset)
            is_weekend = curr_date.weekday() >= 5
            daily_txns = random.randint(8, 12) + (5 if is_weekend else 0)
            
            for _ in range(daily_txns):
                prod = random.choice(self.CATALOG)
                # Seasonality adjustment
                if self.get_seasonal_multiplier(curr_date.month, prod['seasonal']) < 1.0 and random.random() < 0.5:
                    prod = random.choice(self.CATALOG) # Try again

                qty = random.choices([1, 2, 3, 5], weights=[70, 20, 5, 5])[0]
                records.append({
                    "Transaction_ID": txn_id,
                    "Date": curr_date.strftime("%Y-%m-%d"),
                    "Product_ID": prod['id'],
                    "Product_Name": prod['name'],
                    "Batch_ID": f"B{prod['id']}-HIST", # Placeholder
                    "Qty_Sold": qty,
                    "Customer_Phone": random.choice(customers),
                    "Price_At_Sale": prod['price'],
                    "Total_Amount": qty * prod['price']
                })
                txn_id += 1
                
        pd.DataFrame(records).to_csv(f"{DATA_DIR}/transactions.csv", index=False)
        print(f"   ✅ Generated 'transactions.csv' ({len(records)} records)")


# ==============================================================================
# PART 2: DATABASE SEEDING (The "Intelligent" Loader)
# ==============================================================================
class DatabaseSeeder:
    """Reads CSVs, creates Consistent History, Rebalances Inventory, and pushes to Supabase."""
    
    def clean_batch_code(self, product_name, date_obj, seq):
        clean = ''.join(c for c in product_name if c.isalnum()).upper()[:5]
        return f"{clean}-{date_obj.strftime('%Y%m')}-{str(seq).zfill(3)}"

    def seed(self):
        if not db:
            print("❌ DB Connection failed. Check .env")
            return

        print("\n🚀 [Step 2] Seeding Database (Robust Migration)...")
        print("   🧹 Wiping existing data...")
        try:
            db.table("transactions").delete().neq("id", "0").execute()
            db.table("batches").delete().neq("id", "0").execute()
            db.table("products").delete().neq("id", "0").execute()
        except: pass

        # 1. Products
        print("   📦 Migrating Products...")
        df_prod = pd.read_csv(f"{DATA_DIR}/products.csv").replace({np.nan: None})
        prod_map = {} # old_id -> {uuid, name}
        prod_buffer = []
        
        for _, row in df_prod.iterrows():
            new_id = str(uuid.uuid4())
            prod_buffer.append({
                "id": new_id,
                "name": row['name'],
                "category": row['category'],
                "seasonal_tag": row['seasonal'],
                "requires_prescription": bool(row['requires_prescription'])
            })
            prod_map[row['id']] = {"id": new_id, "name": row['name']}
            
        if prod_buffer:
            db.table("products").insert(prod_buffer).execute()

        # 2. Inventory (Rebalanced)
        print("   🏭 Migrating Active Inventory (Optimistic Distribution)...")
        df_inv = pd.read_csv(f"{DATA_DIR}/inventory.csv").sample(frac=1, random_state=42).reset_index(drop=True)
        
        active_batch_map = {}
        seq_tracker = {}
        batch_buffer = []
        now = datetime.now()
        
        # Distribution: 5% Critical, 15% Urgent, 80% Safe
        total_items = len(df_inv)
        
        for idx, row in df_inv.iterrows():
            p = prod_map.get(row['Product_ID'])
            if not p: continue
            
            pct = idx / total_items
            if pct < 0.05: days = np.random.randint(2, 7) # Critical
            elif pct < 0.20: days = np.random.randint(8, 60) # Urgent
            else: days = np.random.randint(90, 540) # Safe
            
            exp_date = now + timedelta(days=days)
            mfg_date = exp_date - timedelta(days=np.random.randint(365, 730))
            
            # Generate Code
            key = f"{p['id']}-{mfg_date.strftime('%Y%m')}"
            seq = seq_tracker.get(key, 0) + 1
            seq_tracker[key] = seq
            code = self.clean_batch_code(p['name'], mfg_date, seq)
            
            b_uuid = str(uuid.uuid4())
            batch_buffer.append({
                "id": b_uuid,
                "product_id": p['id'],
                "internal_batch_code": code,
                "expiry_date": exp_date.strftime("%Y-%m-%d"),
                "manufacture_date": mfg_date.strftime("%Y-%m-%d"),
                "quantity_remaining": int(row['Qty']),
                "supplier_batch_number": "HISTORICAL-STOCK"
            })
            active_batch_map[row['Batch_ID']] = b_uuid

        # 3. Transactions (Consistent History)
        print("   💰 Synthesizing Transaction History...")
        df_txn = pd.read_csv(f"{DATA_DIR}/transactions.csv")
        txn_buffer = []
        synth_batches = {} # cache for historical batches
        
        for _, row in df_txn.iterrows():
            p = prod_map.get(row['Product_ID'])
            if not p: continue
            
            b_id = active_batch_map.get(row['Batch_ID'])
            
            # Synthesize batch if missing (Sold Out)
            if not b_id:
                t_date = pd.to_datetime(row['Date'])
                fake_mfg = t_date - timedelta(days=30)
                m_key = f"{p['id']}-{fake_mfg.strftime('%Y%m')}"
                
                if m_key in synth_batches:
                    b_id = synth_batches[m_key]
                else:
                    seq = seq_tracker.get(m_key, 0) + 1
                    seq_tracker[m_key] = seq
                    code = self.clean_batch_code(p['name'], fake_mfg, seq)
                    b_id = str(uuid.uuid4())
                    
                    # Create Sold-Out Batch
                    batch_buffer.append({
                        "id": b_id,
                        "product_id": p['id'],
                        "internal_batch_code": code,
                        "expiry_date": (fake_mfg + timedelta(days=365)).strftime("%Y-%m-%d"),
                        "manufacture_date": fake_mfg.strftime("%Y-%m-%d"),
                        "quantity_remaining": 0,
                        "supplier_batch_number": "ARCHIVED-SALE"
                    })
                    synth_batches[m_key] = b_id
            
            txn_buffer.append({
                "product_id": p['id'],
                "batch_id": b_id,
                "quantity": int(row['Qty_Sold']),
                "transaction_type": "SALE",
                "unit_price": float(row['Price_At_Sale']),
                "total_amount": float(row['Total_Amount']),
                "transaction_date": row['Date'],
                "customer_phone": str(row['Customer_Phone'])
            })

        # Bulk Insert Helper
        def bulk_insert(table, data):
            for i in range(0, len(data), 1000):
                chunk = data[i:i+1000]
                try:
                    db.table(table).insert(chunk).execute()
                    print(f"      Inserted {table} chunk {i}...", end="\r")
                except Exception as e:
                    print(f"❌ Error: {e}")
            print("")

        print(f"   🚀 Uploading {len(batch_buffer)} batches...")
        bulk_insert("batches", batch_buffer)
        
        print(f"   🚀 Uploading {len(txn_buffer)} transactions...")
        bulk_insert("transactions", txn_buffer)
        
        print("\n🎉 ALL DONE! System is consistent and ready.")


if __name__ == "__main__":
    print("------------------------------------------------")
    print("   PHARMATRACK FAKE DATA GENERATOR")
    print("------------------------------------------------")
    print("1. Generate CSVs (Raw Data)")
    print("2. Seed Database (From CSVs)")
    print("3. FULL RESET (Generate + Seed)")
    
    choice = input("Enter choice (1/2/3): ")
    
    gen = DatasetGenerator()
    seeder = DatabaseSeeder()
    
    if choice == "1":
        gen.generate()
    elif choice == "2":
        seeder.seed()
    elif choice == "3":
        gen.generate()
        seeder.seed()
    else:
        print("Invalid choice.")
