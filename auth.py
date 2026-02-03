import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client(env_path):
    """
    Reads the .env file from the PC and returns a connected BigQuery client.
    """
    
    # 1. Load the environment variables
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"❌ Error: Cannot find .env file at {env_path}")

    load_dotenv(env_path)

    print("🔑 Authenticating locally...")

    # 2. CREATE CREDENTIALS
    # We map your "GCP_" names (from .env) to the standard names Google needs (Left side)
    credentials = service_account.Credentials.from_service_account_info({
        "type": "service_account",
        
        # Left side = Google's Name | Right side = Your .env Name
        "project_id": os.environ["GCP_PROJECT_ID"],
        "private_key_id": os.environ.get("GCP_PRIVATE_KEY_ID"), # Optional if not in .env
        "private_key": os.environ["GCP_PRIVATE_KEY"].replace("\\n", "\n"),
        "client_email": os.environ["GCP_CLIENT_EMAIL"],
        "client_id": os.environ.get("GCP_CLIENT_ID"), # Optional if not in .env
        "auth_uri": os.environ["GCP_AUTH_URI"],
        "token_uri": os.environ["GCP_TOKEN_URI"],
        "auth_provider_x509_cert_url": os.environ["GCP_auth_provider_x509_cert_url"],
        "client_x509_cert_url": os.environ.get("GCP_CLIENT_X509_CERT_URL") # Optional
    })

    # 3. CONFIGURE CLIENT
    bq_client = bigquery.Client(
        credentials=credentials,
        project=credentials.project_id,
    )
    
    return bq_client
