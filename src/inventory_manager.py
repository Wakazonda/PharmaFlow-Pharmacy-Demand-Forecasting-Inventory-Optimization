import os
import sys
from datetime import datetime, timedelta

# Ensure src is in path to import db_client
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_client import db

class InventoryManager:
    def __init__(self, inventory_file=None, product_file=None):
        # We no longer need file paths, but keeping args for compatibility if needed
        if not db:
            raise ConnectionError("❌ Database connection failed.")
        
        print("✅ Inventory Manager Online (Database Backed).")

    def _get_product_by_search(self, search_term):
        """
        Helper: Search for a product by name (case-insensitive fuzzy match).
        Returns the first matching product dict or None.
        """
        try:
            # ilike is case-insensitive
            response = db.table("products").select("*").ilike("name", f"%{search_term}%").limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            print(f"⚠️ Search Error: {e}")
            return None

    def get_product_name(self, product_id):
        try:
            response = db.table("products").select("name").eq("id", product_id).single().execute()
            return response.data['name'] if response.data else "Unknown Product"
        except:
            return "Unknown Product"

    # ==========================================
    # FEATURE 1: DASHBOARD
    # ==========================================
    def generate_risk_report(self, days_threshold=30):
        print(f"\n📢 --- GENERATING EXPIRY RISK REPORT (Threshold: {days_threshold} Days) ---")
        today = datetime.now().date()
        warning_date = today + timedelta(days=days_threshold)

        try:
            # Query batches that are expiring soon AND have stock
            response = db.table("batches")\
                .select("*, products(name)")\
                .lt("expiry_date", warning_date.isoformat())\
                .gt("quantity_remaining", 0)\
                .execute()
            
            risk_batches = response.data
            
            if not risk_batches:
                print("✅ Good News: No stock is expiring soon.")
                return []

            alerts = []
            for batch in risk_batches:
                prod_name = batch['products']['name'] if batch.get('products') else "Unknown"
                expiry = datetime.strptime(batch['expiry_date'], "%Y-%m-%d").date()
                days_left = (expiry - today).days
                
                message = (f"⚠️ ALERT: {prod_name} (Batch {batch['internal_batch_code']}) "
                           f"expires in {days_left} days! Qty: {batch['quantity_remaining']}")
                alerts.append(message)
                print(message)
            return alerts
            
        except Exception as e:
            print(f"❌ Risk Report Error: {e}")
            return []

    # ==========================================
    # FEATURE 2: FEFO LOGIC
    # ==========================================
    def get_batch_to_sell(self, user_input_name, qty_needed):
        """
        Input: "Dolo" or "dolo 650"
        Logic: Finds the closest product match, then picks the oldest batch from DB.
        """
        # --- A. SMART SEARCH ---
        product = self._get_product_by_search(user_input_name)
        
        if not product:
            return f"❌ ERROR: Product '{user_input_name}' not found in catalog."

        p_id = product['id']
        real_product_name = product['name']
        is_prescription = product['requires_prescription']

        # --- B. INVENTORY LOOKUP & C. FEFO SORTING ---
        try:
            # Get matching batches with stock > 0, ordered by expiry_date ASC
            response = db.table("batches")\
                .select("*")\
                .eq("product_id", p_id)\
                .gt("quantity_remaining", 0)\
                .order("expiry_date", desc=False)\
                .execute()
            
            my_batches = response.data
            
            if not my_batches:
                return f"❌ OUT OF STOCK: We have no batches of '{real_product_name}'."

            # Check Total Quantity
            total_stock = sum(b['quantity_remaining'] for b in my_batches)
            if total_stock < qty_needed:
                 return f"❌ INSUFFICIENT STOCK: Requested {qty_needed}, but only {total_stock} available."

            # Best batch is the first one (closest expiry) due to sorting
            best_batch = my_batches[0]

            days_until = (datetime.strptime(best_batch['expiry_date'], "%Y-%m-%d").date() - datetime.now().date()).days

            recommendation = {
                "Product": real_product_name,
                "Sell_From_Batch": best_batch['internal_batch_code'],
                "Batch_UUID": best_batch['id'], # Need UUID for transaction
                "Days_Until_Expiry": days_until,
                "Compliance_Check": "🔴 VERIFY PRESCRIPTION" if is_prescription else "🟢 OTC - Safe to Sell"
            }

            return recommendation

        except Exception as e:
            return f"❌ DB Error: {e}"

    def get_total_stock(self, product_name):
        """
        Returns total available quantity for a given product name.
        """
        product = self._get_product_by_search(product_name)
        if not product:
            return 0
            
        try:
            # Sum quantity_remaining for this product
            # Supabase doesn't have a direct SUM in simple client query easily without RPC, 
            # so we fetch and sum in Python for MVP simplification.
            response = db.table("batches").select("quantity_remaining").eq("product_id", product['id']).execute()
            total = sum(item['quantity_remaining'] for item in response.data)
            return int(total)
        except Exception as e:
            print(f"Error getting stock: {e}")
            return 0
            
    # Helper to expose products dataframe-like structure for the dashboard if needed
    # (The dashboard currently accesses .products_df directly in some places)
    # We should probably mock this property or refactor dashboard.
    # For now, let's allow dashboard to break and we fix dashboard later?
    # Or provide a property that fetches all products.
    @property
    def products_df(self):
        # Compatibility layer: Return all products as a pandas DF
        # dashboard.py uses: inventory_engine.products_df['name'].tolist()
        try:
            import pandas as pd
            res = db.table("products").select("*").execute()
            return pd.DataFrame(res.data)
        except:
            return pd.DataFrame() # Empty

    @property
    def inventory_df(self):
        # Compatibility layer: Return all batches
        # dashboard.py uses: inventory_engine.inventory_df
        try:
            import pandas as pd
            res = db.table("batches").select("*").execute()
            df = pd.DataFrame(res.data)
            # Rename columns to match old CSV format if needed by dashboard
            # Old: Batch_ID, Product_ID, Qty, Expiry_Date, Mfg_Date
            # New: internal_batch_code, product_id, quantity_remaining, expiry_date, manufacture_date
            if not df.empty:
                df = df.rename(columns={
                    "internal_batch_code": "Batch_ID",
                    "product_id": "Product_ID",
                    "quantity_remaining": "Qty",
                    "expiry_date": "Expiry_Date",
                    "manufacture_date": "Mfg_Date"
                })
                df['Expiry_Date'] = pd.to_datetime(df['Expiry_Date'])
            return df
        except:
            return pd.DataFrame()

    def add_batch(self, product_name, supplier_batch, expiry_date, quantity, mfg_date):
        """
        Adds a new batch to inventory.
        Auto-generates internal_batch_code: PRODUCT-YYYYMM-XXX
        """
        try:
            # 1. Get Product ID
            product = self._get_product_by_search(product_name)
            if not product:
                return f"❌ Error: Product '{product_name}' not found."
            
            p_id = product['id']
            p_name_short = product['name'].split()[0].upper()[:4] # First 4 chars of name
            
            # 2. Generate Internal Batch Code
            # Format: CODE-YYYYMM-SEQUENCENO
            # Sanitize product name: Remove non-alphanumeric, take first 5 uppercase
            clean_name = ''.join(c for c in product['name'] if c.isalnum()).upper()
            p_code = clean_name[:5]
            
            now_str = datetime.now().strftime("%Y%m")
            base_code = f"{p_code}-{now_str}"
            
            # Find existing batches with this prefix to determine next sequence
            # Query all matching codes to find max sequence
            response = db.table("batches").select("internal_batch_code").ilike("internal_batch_code", f"{base_code}%").execute()
            
            max_seq = 0
            for record in response.data:
                code = record.get('internal_batch_code', '')
                if code.startswith(base_code):
                    try:
                        # Extract "001" from "DOLO-202402-001"
                        parts = code.split('-')
                        if len(parts) >= 3:
                            seq_part = parts[-1]
                            if seq_part.isdigit():
                                seq = int(seq_part)
                                if seq > max_seq:
                                    max_seq = seq
                    except:
                        pass
            
            next_seq = max_seq + 1
            internal_code = f"{base_code}-{str(next_seq).zfill(3)}"
            
            # 3. Insert
            data = {
                "product_id": p_id,
                "supplier_batch_number": supplier_batch,
                "internal_batch_code": internal_code,
                "quantity_remaining": int(quantity),
                "expiry_date": expiry_date, # YYYY-MM-DD
                "manufacture_date": mfg_date
            }
            
            db.table("batches").insert(data).execute()
            return f"✅ Batch Added! New Code: {internal_code}"
            
        except Exception as e:
            return f"❌ Error adding batch: {e}"

if __name__ == "__main__":
    im = InventoryManager() 
    print("Testing Search for 'dolo'...")
    print(im.get_batch_to_sell("dolo", 2))