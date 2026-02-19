import sys
import os

# 1. Add 'src' to Python path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from inventory_manager import InventoryManager
from pos_system import POS_System


class PharmaTrackApp:
    def __init__(self):
        print("\n🔵 INITIALIZING PHARMATRACK ERP SYSTEM...")
        try:
            # Initialize our two core engines
            self.inventory = InventoryManager()
            self.pos = POS_System()
        except Exception as e:
            print(f"❌ ERROR: System failed to start. {e}")
            sys.exit(1)

    def run(self):
        while True:
            print("\n" + "=" * 40)
            print("   PHARMATRACK DASHBOARD - MAIN MENU")
            print("=" * 40)
            print("1. 📉 View Expiry Risk Report (Manager View)")
            print("2. 🛒 Process New Sale (Pharmacist View)")
            print("3. 📲 Send Patient Safety Reminders (CRM View)")
            print("4. ❌ Exit")

            choice = input("\n👉 Select an Option (1-4): ")

            if choice == '1':
                self.inventory.generate_risk_report(days_threshold=45)

            elif choice == '2':
                self.process_sale_flow()

            elif choice == '3':
                batch_id = input("Enter Batch ID to verify (e.g., B101-EXP): ")
                self.pos.send_expiry_reminders(batch_id)

            elif choice == '4':
                print("Exiting System...")
                break
            else:
                print("❌ Invalid Option.")

    def process_sale_flow(self):
        print("\n--- 🛒 NEW SALE WIZARD ---")

        # 1. Input Product
        prod_name = input("Enter Medicine Name (e.g., Dolo 650): ")
        qty = int(input("Enter Quantity: "))

        # 2. ASK THE BRAIN: Which batch should I sell? (FEFO Logic)
        print(f"🔍 Analyzing Inventory for best batch...")
        recommendation = self.inventory.get_batch_to_sell(prod_name, qty)

        # Handle "Out of Stock" or Errors
        if isinstance(recommendation, str):
            print(f"❌ SALE BLOCKED: {recommendation}")
            return

        # 3. Show Recommendation to Pharmacist
        print(f"\n✅ SYSTEM RECOMMENDATION:")
        print(f"   > Sell From Batch: {recommendation['Sell_From_Batch']}")
        print(f"   > Expiry Date: {recommendation['Days_Until_Expiry']} days left")
        print(f"   > Compliance: {recommendation['Compliance_Check']}")

        confirm = input("\nConfirm Sale? (y/n): ")
        if confirm.lower() != 'y':
            print("❌ Sale Cancelled.")
            return

        # 4. CAPTURE CUSTOMER DATA (Traceability)
        phone = input("Enter Customer UPI/Phone: ")

        # 5. RECORD THE TRANSACTION
        self.pos.process_sale(
            customer_phone=phone,
            product_id=999,  # In a real app, we'd look up the ID. For demo, we skip.
            batch_id=recommendation['Sell_From_Batch'],
            qty=qty
        )
        print("✅ Receipt Generated & SMS Sent.")


if __name__ == "__main__":
    app = PharmaTrackApp()
    app.run()