import os
import sys
from datetime import datetime

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db_client import db

class POS_System:
    def __init__(self, transactions_file=None, inventory_file=None):
        if not db:
            raise ConnectionError("❌ Database connection failed.")
        print("✅ POS System Online (Database Backed).")

    # ==========================================
    # FEATURE 1: RECORD A NEW SALE
    # ==========================================
    def process_sale(self, customer_phone, product_id, batch_id, qty):
        """
        Records a sale in DB and updates inventory.
        batch_id here is expected to be the internal_batch_code (string) from the UI recommendation,
        OR the UUID if we pass that. 
        InventoryManager returns 'Sell_From_Batch' (string) and 'Batch_UUID' (uuid).
        The Dashboard currently passes the string code. We need to find the UUID.
        """
        
        # 1. Resolve Batch UUID if needed
        # We need the UUID to insert into transactions and update batches
        try:
            # Try to find batch by internal code
            batch_res = db.table("batches").select("id, product_id, quantity_remaining").eq("internal_batch_code", batch_id).single().execute()
            if not batch_res.data:
                print(f"❌ Error: Batch {batch_id} not found.")
                return

            batch_uuid = batch_res.data['id']
            real_product_id = batch_res.data['product_id'] # Use the real product ID from batch
            current_qty = batch_res.data['quantity_remaining']
            
            if current_qty < qty:
                print(f"❌ Error: Not enough stock. Has {current_qty}, trying to sell {qty}.")
                return

            # 2. Insert Transaction
            txn_data = {
                "product_id": real_product_id,
                "batch_id": batch_uuid,
                "quantity": qty,
                "transaction_type": "SALE",
                "customer_phone": customer_phone,
                "transaction_date": datetime.now().isoformat(),
                "unit_price": 0, # Placeholder, in real app we'd fetch price from products
                "total_amount": 0
            }
            db.table("transactions").insert(txn_data).execute()

            # 3. Update Inventory (Decrement)
            new_qty = current_qty - qty
            db.table("batches").update({"quantity_remaining": new_qty}).eq("id", batch_uuid).execute()

            print(f"💰 SALE COMPLETE: Sold {qty} of Batch {batch_id} to {customer_phone}")

        except Exception as e:
            print(f"❌ Transaction Failed: {e}")

    # ==========================================
    # FEATURE 2: CUSTOMER SAFETY REMINDERS
    # ==========================================
    def send_expiry_reminders(self, batch_code_checking):
        print(f"\n📨 --- CHECKING CUSTOMERS FOR BATCH: {batch_code_checking} ---")

        try:
            # 1. Get Batch Info
            batch_res = db.table("batches").select("id, expiry_date").eq("internal_batch_code", batch_code_checking).single().execute()
            if not batch_res.data:
                print("❌ Error: Batch not found.")
                return

            batch_uuid = batch_res.data['id']
            expiry_date = batch_res.data['expiry_date']

            # 2. Find Customers
            # Select distinct customer_phone from transactions where batch_id = uuid
            response = db.table("transactions").select("customer_phone").eq("batch_id", batch_uuid).execute()
            
            customers = set(r['customer_phone'] for r in response.data if r.get('customer_phone'))

            if not customers:
                print("✅ No customers bought this specific batch.")
                return

            print(f"⚠️ Found {len(customers)} customers who possess this batch.")

            # 3. Simulate Send
            for phone in customers:
                msg = (
                    f"📲 [SMS SENT] To {phone}: "
                    f"'Hello! Safety Reminder from PharmaTrack. "
                    f"The medicine you purchased (Batch {batch_code_checking}) "
                    f"will expire on {expiry_date}. Please check your cabinet!'"
                )
                print(msg)

        except Exception as e:
            print(f"❌ Error sending reminders: {e}")

    def get_total_transaction_count(self):
        """
        Returns the true total count of transactions in the DB.
        """
        try:
            # count='exact', head=True -> performs a count query without fetching data
            res = db.table("transactions").select("*", count="exact", head=True).execute()
            return res.count
        except:
            return 0

    # Compatibility Property
    @property
    def transactions_df(self):
        try:
            import pandas as pd
            # Fetch recent transactions with JOINS to get names
            # transactions -> products (name)
            # transactions -> batches (internal_batch_code)
            res = db.table("transactions")\
                .select("*, products(name), batches(internal_batch_code)")\
                .order("transaction_date", desc=True)\
                .limit(200)\
                .execute()
            
            data = []
            for r in res.data:
                # Handle flattened structure
                prod_name = r['products']['name'] if r.get('products') else "Unknown"
                batch_code = r['batches']['internal_batch_code'] if r.get('batches') else "None"
                
                data.append({
                    "Transaction_ID": r['id'],
                    "Date": r['transaction_date'],
                    "Product": prod_name,
                    "Batch": batch_code,
                    "Qty_Sold": r['quantity'],
                    "Customer_Phone": r['customer_phone'],
                    "Price_At_Sale": r['unit_price'],
                    "Total_Amount": r['total_amount']
                })

            df = pd.DataFrame(data)
            return df
        except Exception as e:
             print(f"Error fetching transactions_df: {e}")
             return pd.DataFrame()

if __name__ == "__main__":
    pos = POS_System()