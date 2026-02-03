import os
import json
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client(env_path):
    """
    Reads the .env file and returns a connected BigQuery client.
    Expects standard Google Service Account variable names.
    """
    
    # 1. Load the environment variables
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"❌ Error: Cannot find .env file at {env_path}")

    load_dotenv(env_path)
    print("🔑 Authenticating...")

    # 2. CREATE CREDENTIALS (The Clean Way)
    # We build the dictionary using the keys Google expects directly.
    # This matches exactly what you did in Streamlit Secrets.
    key_dict = {
        "type": "service_account",
        "project_id": os.getenv("project_id"),
        "private_key_id": os.getenv("private_key_id"),
        "private_key": os.getenv("private_key").replace("\\n", "\n") if os.getenv("private_key") else None,
        "client_email": os.getenv("client_email"),
        "client_id": os.getenv("client_id"),
        "auth_uri": os.getenv("auth_uri"),
        "token_uri": os.getenv("token_uri"),
        "auth_provider_x509_cert_url": os.getenv("auth_provider_x509_cert_url"),
        "client_x509_cert_url": os.getenv("client_x509_cert_url"),
    }

    # 3. CONFIGURE CLIENT
    credentials = service_account.Credentials.from_service_account_info(key_dict)
    
    bq_client = bigquery.Client(
        credentials=credentials,
        project=credentials.project_id,
    )
    
    return bq_client
