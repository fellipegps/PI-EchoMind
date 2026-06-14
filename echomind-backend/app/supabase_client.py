import os

from supabase import Client, create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_URL e SUPABASE_SECRET_KEY devem estar configurados no .env"
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)
