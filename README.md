# PharmaTrack ERP

PharmaTrack ERP is a comprehensive pharmacy management system designed to streamline day-to-day operations for modern pharmacies. It combines robust inventory tracking with intelligent demand forecasting and an intuitive Point of Sale (POS) interface.

## Key Features

-   **Inventory Management**: 
    -   Real-time stock monitoring.
    -   Batch-level tracking with expiration date alerts.
    -   Automated "First-Expire, First-Out" (FEFO) recommendations to reduce waste.
    
-   **Demand Forecasting**: 
    -   AI-driven insights to predict future sales trends.
    -   Helps optimize stock levels and prevent overstocking or stockouts.
    -   Visualizes sales data with interactive charts.

-   **Point of Sale (POS)**:
    -   Efficient billing system integrated with inventory.
    -   Quick product search and cart management.
    -   Generates digital receipts.

-   **Interactive Dashboard**:
    -   Built with Streamlit for a responsive and user-friendly experience.
    -   Centralized view of key metrics and alerts.

## Technology Stack

-   **Frontend**: Streamlit
-   **Backend**: Python
-   **Database**: Supabase (PostgreSQL) - Cloud-hosted
-   **Data Analysis**: Pandas, Scikit-learn (for forecasting models)

## Prerequisites

-   Python 3.8 or higher
-   A Supabase account and project (for the database)

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/PharmaTrack_ERP.git
    cd PharmaTrack_ERP
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv venv
    
    # Windows
    venv\Scripts\activate
    
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**:
    Create a `.env` file in the root directory and add your Supabase credentials:
    ```env
    SUPABASE_URL=your_supabase_project_url
    SUPABASE_KEY=your_supabase_anon_key
    ```

## Usage

To start the application, run the following command in your terminal:

```bash
streamlit run dashboard.py
```

The application will open automatically in your default web browser.

## Project Structure

-   `dashboard.py`: Main entry point for the Streamlit application.
-   `src/`: Contains core logic modules.
    -   `inventory_manager.py`: Handles stock updates and queries.
    -   `pos_system.py`: Manages sales transactions.
    -   `forecasting_engine.py`: Logic for demand prediction models.
    -   `db_client.py`: Database connection handling.
-   `data/`: Stores local data files (if any) or exported reports.
-   `schema.sql`: Database schema definition for initial setup.

## Contributing



## License

[MIT License](LICENSE)
