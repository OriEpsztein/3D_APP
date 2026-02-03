import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

def get_bq_client(env_path):
    """
    Reads the .env file from the specific path and returns a connected BigQuery client.
    """
    
    # 1. Load the environment variables
    if not os.path.exists(env_path):
        raise FileNotFoundError(f"❌ Error: Cannot find .env file at {env_path}")

    load_dotenv(env_path)

    print("🔑 Authenticating...")

    # 2. YOUR CODE (Creating credentials from the .env variables)
    credentials = service_account.Credentials.from_service_account_info({
        "type": "service_account",
        "project_id": os.environ["GCP_PROJECT_ID"],
        "client_email": os.environ["client_email"],
        "private_key": os.environ["GCP_PRIVATE_KEY"].replace("\\n", "\n"),
        "auth_uri": os.environ["GCP_AUTH_URI"],
        "token_uri": os.environ["token_uri"],
        "auth_provider_x509_cert_url": os.environ["GCP_auth_provider_x509_cert_url"],
    })

    # 3. YOUR CODE (Configuring the client)
    bq_client = bigquery.Client(
        credentials=credentials,
        project=credentials.project_id,
    )
    

    return bq_client
