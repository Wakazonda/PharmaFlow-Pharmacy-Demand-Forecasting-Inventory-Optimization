import streamlit as st
import pandas as pd
import sys
import os
from datetime import datetime, timedelta

# --- SETUP: Add 'src' to path so we can import our modules ---
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from inventory_manager import InventoryManager
from pos_system import POS_System
from forecasting_engine import ForecastingEngine


# --- INITIALIZE ENGINES ---
# We use @st.cache_resource so it doesn't reload the data every time you click a button
@st.cache_resource
def load_engines():
    inv = InventoryManager()
    pos = POS_System()
    fore = ForecastingEngine()
    return inv, pos, fore


inventory_engine, pos_engine, forecasting_engine = load_engines()

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="PharmaTrack ERP", layout="wide")

# Inject Custom CSS for Sidebar Width and Main Panel
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        min-width: 200px;
        max_width: 250px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("PharmaTrack: Supply Chain & Safety System")

# --- SIDEBAR NAVIGATION ---
st.sidebar.header("Navigation")
page = st.sidebar.selectbox("Go to:", ["Dashboard Overview", "Pharmacist POS", "Expiry Manager", "Safety Alerts", "Demand Forecasting", "Add New Batch"])

# ====================================================
# PAGE 1: DASHBOARD OVERVIEW (metrics)
# ====================================================
if page == "Dashboard Overview":
    st.header("📊 Executive Overview")

    # Calculate Metrics
    total_products = len(inventory_engine.products_df)
    
    # Filter for only ACTIVE batches (Qty > 0)
    # The migration added historical (0 qty) batches which shouldn't be counted here.
    active_batches = inventory_engine.inventory_df[inventory_engine.inventory_df['Qty'] > 0]
    total_batches = len(active_batches)

    # Financials from transactions (Simulated)
    sales_df = pos_engine.transactions_df
    # USE NEW METHOD FOR TRUE COUNT
    total_sales = pos_engine.get_total_transaction_count()
    
    # Simple revenue calc (Qty * Price) - strictly an estimate since dataframe is limited to 200
    # For MVP we can just sum the visible ones or query total. 
    # Let's keep it simple: Estimate based on visible * (total / 200)? No, that's misleading.
    # Let's just sum visible recent revenue for now or query total revenue if needed.
    # The prompt asked for "Total Transactions" count fix specifically.
    est_revenue = (sales_df['Qty_Sold'] * sales_df['Price_At_Sale']).sum()

    # Display Metrics in Columns
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Products", total_products)
    col2.metric("Active Batches", total_batches)
    col3.metric("Total Transactions", f"{total_sales:,}")
    col4.metric("Est. Revenue (Recent)", f"₹{est_revenue:,.0f}")

    st.markdown("---")

    # Recent Sales Table
    st.subheader("Recent Transactions")
    # Hide the long UUID Transaction_ID by selecting specific columns
    display_cols = ["Date", "Product", "Batch", "Qty_Sold", "Customer_Phone", "Price_At_Sale", "Total_Amount"]
    st.dataframe(sales_df[display_cols], width='stretch')

# ====================================================
# PAGE 2: PHARMACIST POS (Selling Items)
# ====================================================
elif page == "Pharmacist POS":
    st.header("🛒 Point of Sale (POS)")

    col1, col2 = st.columns([2, 1])

    with col1:
        # 1. Select Product
        product_list = inventory_engine.products_df['name'].tolist()
        selected_product = st.selectbox("Search Medicine:", product_list)
        
        # Get Real-Time Stock
        current_stock = inventory_engine.get_total_stock(selected_product)
        
        if current_stock > 0:
            st.success(f"✅ Available Stock: {current_stock}")
        else:
            st.error("❌ Out of Stock")
            
        # Removed max_value constraint to allow custom validation
        qty = st.number_input("Quantity:", min_value=1, value=1)

        # 2. Check Stock Button
        if st.button("Check Availability"):
            if qty > current_stock:
                st.error("Required amount not in stock")
                # Clear recommendation if it exists to avoid showing stale data
                if 'recommendation' in st.session_state:
                    del st.session_state['recommendation']
            else:
                recommendation = inventory_engine.get_batch_to_sell(selected_product, qty)

                if isinstance(recommendation, str):
                    st.error(recommendation)
                else:
                    # Save recommendation to session state so it persists
                    st.session_state['recommendation'] = recommendation
                    st.session_state['qty'] = qty
                    st.session_state['prod_name'] = selected_product

    with col2:
        # 3. Display Recommendation
        if 'recommendation' in st.session_state:
            rec = st.session_state['recommendation']

            st.success("✅ Stock Available!")
            st.info(f"**Sell From Batch:** {rec['Sell_From_Batch']}")
            st.warning(f"**Expiry Date:** in {rec['Days_Until_Expiry']} days")

            if "VERIFY" in rec['Compliance_Check']:
                st.error(f"🛑 {rec['Compliance_Check']}")
            else:
                st.success(f"🟢 {rec['Compliance_Check']}")

            # 4. Finalize Sale
            with st.form("finalize_sale"):
                customer_phone = st.text_input("Customer Phone (UPI):")
                confirm = st.form_submit_button("Confirm Sale")

                if confirm:
                    if customer_phone:
                        pos_engine.process_sale(
                            customer_phone,
                            product_id=999,  # Placeholder
                            batch_id=rec['Sell_From_Batch'],
                            qty=st.session_state['qty']
                        )
                        st.balloons()
                        st.success(f"Sale Recorded! SMS Invoice sent to {customer_phone}")
                        # Clear state
                        del st.session_state['recommendation']
                    else:
                        st.error("Please enter Customer Phone Number.")


# ====================================================
# PAGE 3: EXPIRY MANAGER (Risk Report)
# ====================================================
elif page == "Expiry Manager":
    # --- Custom CSS for Card Design ---
    st.markdown("""
    <style>
    .expiry-card {
        background-color: #1E1E1E;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #333;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #2D2D2D;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        border-left: 5px solid #555;
    }
    .metric-label {
        color: #AAA;
        font-size: 0.9em;
    }
    .metric-value {
        font-size: 1.8em;
        font-weight: bold;
        color: #FFF;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="expiry-card">', unsafe_allow_html=True)
        
        # 1. Header Area
        st.title("⚠️ Expiry Risk Management")
        st.caption("Monitor medicines approaching expiration based on selected risk horizon.")
        st.markdown("---")

        # 2. Risk Selector & Filter Layout
        col_controls_1, col_controls_2 = st.columns([1.5, 1])
        
        with col_controls_1:
            st.subheader("Select Risk Horizon")
            # Changed from pills/radio to a dropdown (selectbox) per request
            risk_option = st.selectbox(
                "Risk Level:",
                ["🔴 Critical (7d)", "🟠 Warning (30d)", "🟡 Watchlist (90d)", "🟢 Safe (>90d)"],
                label_visibility="collapsed"
            )
            
            # Map selection to days
            if "Critical" in risk_option:
                days = 7
                selected_risk_label = "Critical"
            elif "Warning" in risk_option:
                days = 30
                selected_risk_label = "Warning"
            elif "Watchlist" in risk_option:
                days = 90
                selected_risk_label = "Watchlist"
            else:
                days = 180
                selected_risk_label = "Safe"
                
        with col_controls_2:
            st.subheader("Filter Categories")
            all_categories = inventory_engine.products_df['category'].unique().tolist()
            selected_cats = st.multiselect(
                "Category Filter:", 
                all_categories, 
                default=all_categories,
                placeholder="Select medical categories...",
                label_visibility="collapsed"
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # Logic preparation
    today = datetime.now()
    # Prepare Full Data
    # 1. Get raw inventory
    raw_inv = inventory_engine.inventory_df
    
    # 2. Filter for ACTIVE batches only (Qty > 0)
    # This prevents historical/sold-out batches from skewing expiry metrics
    active_inv = raw_inv[raw_inv['Qty'] > 0]

    full_inventory = active_inv.merge(
        inventory_engine.products_df[['id', 'name', 'category']], 
        left_on='Product_ID', 
        right_on='id', 
        how='left'
    )
    
    # Calculate Metrics (Pre-filter for context, or Post-filter? Let's do Global Context)
    crit_count = len(full_inventory[full_inventory['Expiry_Date'] < today + timedelta(days=7)])
    warn_count = len(full_inventory[(full_inventory['Expiry_Date'] >= today + timedelta(days=7)) & (full_inventory['Expiry_Date'] < today + timedelta(days=30))])
    watch_count = len(full_inventory[(full_inventory['Expiry_Date'] >= today + timedelta(days=30)) & (full_inventory['Expiry_Date'] < today + timedelta(days=90))])
    safe_count = len(full_inventory[full_inventory['Expiry_Date'] >= today + timedelta(days=90)])

    # 3. Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f"""<div class="metric-card" style="border-left-color: #FF4B4B;">
        <div class="metric-label">Critical (7d)</div>
        <div class="metric-value">{crit_count}</div>
    </div>""", unsafe_allow_html=True)
    
    m2.markdown(f"""<div class="metric-card" style="border-left-color: #FFA500;">
        <div class="metric-label">Warning (30d)</div>
        <div class="metric-value">{warn_count}</div>
    </div>""", unsafe_allow_html=True)
    
    m3.markdown(f"""<div class="metric-card" style="border-left-color: #FFD700;">
        <div class="metric-label">Watchlist (90d)</div>
        <div class="metric-value">{watch_count}</div>
    </div>""", unsafe_allow_html=True)
    
    m4.markdown(f"""<div class="metric-card" style="border-left-color: #4CAF50;">
        <div class="metric-label">Safe (>90d)</div>
        <div class="metric-value">{safe_count}</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Data Filtering
    cutoff = today + timedelta(days=days)
    
    if selected_risk_label == "Safe":
        # Logic for Safe: show items expiring AFTER 90 days (or just everything else?)
        # Let's stick to the prompt's implication of "Horizon". 
        # But "Safe" usually implies far future. Let's filter > 90 days for consistency with metrics
        # Re-using the logic:
        risk_df = full_inventory[full_inventory['Expiry_Date'] >= today + timedelta(days=90)]
    elif selected_risk_label == "Watchlist":
        risk_df = full_inventory[(full_inventory['Expiry_Date'] >= today + timedelta(days=30)) & (full_inventory['Expiry_Date'] < today + timedelta(days=90))]
    elif selected_risk_label == "Warning":
        risk_df = full_inventory[(full_inventory['Expiry_Date'] >= today + timedelta(days=7)) & (full_inventory['Expiry_Date'] < today + timedelta(days=30))]
    else: # Critical
        risk_df = full_inventory[full_inventory['Expiry_Date'] < today + timedelta(days=7)]

    # Category Filter
    if selected_cats:
        risk_df = risk_df[risk_df['category'].isin(selected_cats)]

    # 5. Smart Feedback & Chart
    st.info(f"🔎 Showing **{len(risk_df)}** medicines in **{selected_risk_label} Limit** for selected categories.")
    
    col_table, col_chart = st.columns([2, 1])
    
    with col_table:
        if not risk_df.empty:
            st.dataframe(
                risk_df[['Batch_ID', 'name', 'category', 'Qty', 'Expiry_Date']].rename(columns={'name': 'Product', 'category': 'Category'}),
                width='stretch'
            )
        else:
            st.success("✅ No medicines found in this risk category.")

    with col_chart:
        # Option B: Mini Chart
        # Create a simple distribution dataframe for the chart
        dist_data = pd.DataFrame({
            'Risk Level': ['Critical', 'Warning', 'Watchlist', 'Safe'],
            'Count': [crit_count, warn_count, watch_count, safe_count]
        })
        st.caption("Total Inventory Risk Distribution")
        st.bar_chart(dist_data.set_index('Risk Level'))

    if not risk_df.empty:
        st.download_button(
            "Download Risk Report (CSV)",
            risk_df.to_csv(index=False),
            "expiry_risk_report.csv"
        )

# ====================================================
# PAGE 4: SAFETY ALERTS (Traceability)
# ====================================================
elif page == "Safety Alerts":
    st.header("📲 Patient Safety & Recall System")

    st.markdown("""
    Use this module to trace customers who bought a specific batch.
    **Scenario:** You discover Batch `DOLO-202402-001` is defective or expiring.
    """)

    # --- 1. TRACE & ALERT (TOP SECTION) ---
    batch_input = st.text_input("Enter Batch ID to Trace (e.g., DOLO-202402-001):")

    # Initialize session state for affected customers if not present
    if 'affected_customers' not in st.session_state:
        st.session_state['affected_customers'] = None
    if 'trace_batch_id' not in st.session_state:
        st.session_state['trace_batch_id'] = None

    # Step A: Trace Customers
    if st.button("1. Trace Customers"):
        if batch_input:
            # VALIDATE BATCH EXISTS AND GET PRODUCT INFO
            batch_record = inventory_engine.inventory_df[inventory_engine.inventory_df['Batch_ID'] == batch_input]
            
            if batch_record.empty:
                st.error(f"❌ Batch ID '{batch_input}' not found in the system!")
                st.session_state['affected_customers'] = None
            else:
                # Batch exists, proceed to find sales
                sales_df = pos_engine.transactions_df
                # Match against the new 'Batch' column (internal code)
                affected = sales_df[sales_df['Batch'] == batch_input]
                
                if affected.empty:
                     st.info(f"✅ Batch {batch_input} exists, but no sales recorded for it yet.")
                     st.session_state['affected_customers'] = None
                     st.session_state['trace_batch_id'] = None
                else:
                    st.session_state['affected_customers'] = affected
                    st.session_state['trace_batch_id'] = batch_input
                    st.success(f"⚠️ Found {len(affected)} transactions for Batch {batch_input}")
        else:
            st.error("Please enter a Batch ID.")

    # Step B: Display and Send
    if st.session_state['affected_customers'] is not None:
        affected = st.session_state['affected_customers']
        unique_customers = affected['Customer_Phone'].unique()
        
        st.subheader("Affected Customers")
        st.dataframe(affected[['Transaction_ID', 'Date', 'Customer_Phone', 'Qty_Sold']], width='stretch')
        
        st.warning(f"⚠️ Found {len(unique_customers)} unique affected customers!")

        if st.button("2. Send SMS Alerts"):
            st.subheader("📢 Message Log (Simulated)")
            for phone in unique_customers:
                st.code(
                    f"📲 [SMS SENT] To {phone}: 'Urgent Safety Reminder: Your purchase of Batch {st.session_state['trace_batch_id']} is expiring/recalled. Please check.'")
            
            st.success("All messages sent successfully!")

    st.markdown("---")
    
    # --- 2. BATCH REGISTRY (BOTTOM SECTION) ---
    st.subheader("📂 Batch Registry")
    
    col_filter1, col_filter2 = st.columns(2)
    with col_filter1:
        status_filter = st.selectbox("Filter by Status:", ["All", "Active", "Archived"])
    with col_filter2:
        search_med = st.text_input("Search Medicine Name:", "")

    raw_batches = inventory_engine.inventory_df.copy()
    if not raw_batches.empty:
        # Add Status Column
        raw_batches['Status'] = raw_batches['Qty'].apply(lambda x: "Active" if x > 0 else "Archived")
        
        # Link Product Names (Mock Join since inventory_df only has Product_ID)
        # We need to map product_id to name
        # We can use products_df for this
        products = inventory_engine.products_df
        if not products.empty:
            # Merge
            # inventory_df has 'Product_ID'
            # products_df has 'id' and 'name'
            merged = pd.merge(raw_batches, products, left_on='Product_ID', right_on='id', how='left')
            merged['Medicine'] = merged['name']
        else:
             merged = raw_batches
             merged['Medicine'] = "Unknown"

        # Apply Filters
        if status_filter == "Active":
            merged = merged[merged['Status'] == "Active"]
        elif status_filter == "Archived":
            merged = merged[merged['Status'] == "Archived"]
            
        if search_med:
            merged = merged[merged['Medicine'].str.contains(search_med, case=False, na=False)]

        # Display
        display_cols = ['Batch_ID', 'Medicine', 'Status', 'Qty', 'Expiry_Date', 'Mfg_Date']
        st.dataframe(merged[display_cols], use_container_width=True)
    else:
        st.info("No batches found in system.")

# ====================================================
# PAGE 5: DEMAND FORECASTING (New Feature)
# ====================================================
elif page == "Demand Forecasting":
    st.header("AI Demand Forecasting")
    
    col_config, col_action = st.columns([2, 1])
    with col_config:
        months_ahead = st.slider("Forecast Horizon (Months):", min_value=1, max_value=6, value=1)
        
    with col_action:
        st.write("") # Spacer
        run_forecast = st.button("Generate Forecast Report", type="primary")

    # Dynamic Options for Breakdown
    # Calculate available months based on slider
    future_dates = pd.date_range(start=datetime.now() + pd.DateOffset(months=1), periods=months_ahead, freq='MS')
    month_options = [d.strftime("%B %Y") for d in future_dates]
    view_options = [f"Cumulative (Next {months_ahead} Months)"] + month_options
    
    selected_view = st.selectbox("📊 View Forecast For:", view_options)

    if run_forecast:
        with st.spinner(f"Training AI Models & Predicting..."):
            
            report_data = []
            products_to_forecast = forecasting_engine.get_top_products(n=50)

            if not products_to_forecast:
                st.warning("No sales data found to generate forecast.")
            else:
                # Loop through each product
                for product_name in products_to_forecast:
                    # Get Forecast
                    # We pass months_ahead to predict_demand
                    forecast_df, avg_sales, accuracy = forecasting_engine.predict_demand(product_name, months_ahead=months_ahead)
                    
                    if forecast_df is None or forecast_df.empty:
                        # Debugging: Show why it failed
                        st.write(f"⚠️ Skipped {product_name}: {avg_sales}") 
                        continue
                        
                    # Filter based on user selection
                    if "Cumulative" in selected_view:
                        total_predicted_qty = int(forecast_df['Predicted_Demand'].sum())
                        horizon_label = f"{months_ahead} Months (Total)"
                    else:
                        # Filter by specific month
                        # forecast_df['Date'] is datetime
                        target_month_str = selected_view
                        # Filter
                        match = forecast_df[forecast_df['Date'].dt.strftime("%B %Y") == target_month_str]
                        if not match.empty:
                            total_predicted_qty = int(match.iloc[0]['Predicted_Demand'])
                        else:
                            total_predicted_qty = 0
                        horizon_label = f"{target_month_str} Only"
                    
                    # Get Current Stock
                    prod_row = inventory_engine.products_df[inventory_engine.products_df['name'] == product_name]
                    
                    if prod_row.empty:
                        continue 
                        
                    p_id = prod_row.iloc[0]['id']
                    current_stock = inventory_engine.inventory_df[inventory_engine.inventory_df['Product_ID'] == p_id]['Qty'].sum()

                    # Calculate Status (vs Total Predicted for Period)
                    deficit = current_stock - total_predicted_qty
                    
                    status = "Sufficient"
                    if deficit < 0:
                        status = "Understock"
                    elif deficit > (total_predicted_qty * 2) and total_predicted_qty > 5: 
                        status = "Overstocked"

                    report_data.append({
                        "Medicine": product_name,
                        "Category": prod_row.iloc[0]['category'] if not prod_row.empty else "Unknown",
                        "Current Stock": current_stock,
                        "Predicted Demand": total_predicted_qty,
                        "Horizon": horizon_label,
                        "Status": status,
                        "Model Confidence": f"{accuracy}%"
                    })
                
                if not report_data:
                    # Initialize empty DF with expected columns to avoid KeyError
                    full_forecast_df = pd.DataFrame(columns=[
                        "Medicine", "Category", "Current Stock", 
                        "Predicted Demand", "Horizon", "Status", "Model Confidence"
                    ])
                else:
                    # Convert to DataFrame for easier filtering
                    full_forecast_df = pd.DataFrame(report_data)
                
                # --- SAVE TO SESSION STATE FOR FILTERING ---
                st.session_state['forecast_data'] = full_forecast_df

    # --- DISPLAY & FILTERING ---
    if 'forecast_data' in st.session_state:
        df = st.session_state['forecast_data']
        
        # Search & Filter Controls
        col_search, col_filter = st.columns(2)
        
        with col_search:
            search_query = st.text_input("🔍 Search Medicine:", "")
            
        with col_filter:
            # User requested specific 3 filters
            all_statuses = ["Sufficient", "Overstocked", "Understock"]
            selected_status = st.multiselect("Filter by Status:", all_statuses, default=all_statuses)

        # Apply Filters
        filtered_df = df.copy()
        
        if search_query:
            filtered_df = filtered_df[filtered_df['Medicine'].str.contains(search_query, case=False)]
            
        if selected_status:
             filtered_df = filtered_df[filtered_df['Status'].isin(selected_status)]

        # --- VISUALIZATION ---
        if not filtered_df.empty:
            st.subheader("📈 Forecast vs Inventory")
            st.caption("Comparison of Current Stock vs Predicted Demand")
            
            # Prepare data for chart: Index=Medicine, Columns=[Current Stock, Next Month Forecast]
            # We strictly select the columns and index to ensure clean tooltips
            chart_data = filtered_df[['Medicine', 'Current Stock', 'Predicted Demand']].set_index('Medicine')
            st.bar_chart(chart_data)
            
            st.write(f"Showing {len(filtered_df)} Products")
            st.dataframe(filtered_df, width='stretch')
            
            # Download
            csv = filtered_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download Forecast Report",
                csv,
                "monthly_forecast.csv",
                "text/csv",
                key='download-csv'
            )
        else:
            st.warning("No products match your search/filter.")

# ====================================================
# PAGE 6: ADD NEW BATCH (Admin)
# ====================================================
elif page == "Add New Batch":
    st.header("📦 Add New Inventory Batch")
    
    with st.form("add_batch_form"):
        # 1. Select Product
        product_list = inventory_engine.products_df['name'].tolist()
        product_name = st.selectbox("Select Medicine:", product_list)
        
        # 2. Batch Details
        col1, col2 = st.columns(2)
        with col1:
            supplier_batch = st.text_input("Supplier Batch Number:")
            qty = st.number_input("Quantity Received:", min_value=1, value=100)
        
        with col2:
            mfg_date = st.date_input("Manufacturing Date:")
            expiry_date = st.date_input("Expiry Date:", value=datetime.now() + timedelta(days=365))
            
        submitted = st.form_submit_button("Add Batch")
        
        if submitted:
            if not supplier_batch:
                st.error("Please enter Supplier Batch Number.")
            elif expiry_date <= mfg_date:
                st.error("Expiry Date must be after Manufacturing Date.")
            else:
                # Call backend
                result = inventory_engine.add_batch(
                    product_name, 
                    supplier_batch, 
                    expiry_date.strftime("%Y-%m-%d"), 
                    qty, 
                    mfg_date.strftime("%Y-%m-%d")
                )
                
                if "✅" in result:
                    st.success(result)
                    st.balloons()
                else:
                    st.error(result)

    st.markdown("---")
    st.subheader("📋 View Active Batches")

    # 3. View Active Batches
    # Get all active batches (Qty > 0)
    # We can reuse inventory_df but need to ensure it has product names
    
    # 3.1 Dropdown to Filter by Medicine
    # Get unique product names from products_df
    all_products = inventory_engine.products_df['name'].tolist()
    # Add "All Medicines" option
    search_options = ["All Medicines"] + all_products
    
    selected_view_product = st.selectbox("Filter Active Batches by Medicine:", search_options)

    # 3.2 Filter Data
    # Get raw inventory
    batch_df = inventory_engine.inventory_df.copy()
    
    if not batch_df.empty:
        # Filter for Active only
        active_batch_df = batch_df[batch_df['Qty'] > 0]
        
        # Merge with product names if not already present (inventory_df usually returns raw IDs)
        # Check if 'name' is in columns, if not merge
        if 'name' not in active_batch_df.columns:
             # Merge with products
             prods = inventory_engine.products_df
             if not prods.empty:
                 active_batch_df = active_batch_df.merge(
                     prods[['id', 'name']], 
                     left_on='Product_ID', 
                     right_on='id', 
                     how='left'
                 )
                 # Rename for display
                 active_batch_df = active_batch_df.rename(columns={'name': 'Medicine'})
             else:
                 active_batch_df['Medicine'] = "Unknown"
        
        # Apply Dropdown Filter
        if selected_view_product != "All Medicines":
            active_batch_df = active_batch_df[active_batch_df['Medicine'] == selected_view_product]

        # 3.3 Display Table
        if not active_batch_df.empty:
            # Select user-friendly columns
            # Check existance of columns before selecting
            cols_to_show = ['Batch_ID', 'Medicine', 'Qty', 'Expiry_Date', 'Mfg_Date']
            # Intersection of columns
            final_cols = [c for c in cols_to_show if c in active_batch_df.columns]
            
            st.dataframe(active_batch_df[final_cols], use_container_width=True)
            st.info(f"Showing {len(active_batch_df)} active batches.")
        else:
            if selected_view_product != "All Medicines":
                 st.warning(f"No active batches found for {selected_view_product}.")
            else:
                 st.info("No active batches in inventory.")
    else:
        st.info("Inventory is empty.")