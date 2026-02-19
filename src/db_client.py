import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class DBClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBClient, cls).__new__(cls)
            cls._instance.init_client()
        return cls._instance

    def init_client(self):
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            print("⚠️ WARNING: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")
            print("Database features will not work.")
            self.client = None
            return

        try:
            self.client: Client = create_client(url, key)
            print("✅ Supabase Client Initialized.")
        except Exception as e:
            print(f"❌ Failed to initialize Supabase client: {e}")
            self.client = None

    def get_client(self):
        return self.client

# Global instance
db = DBClient().get_client()
