import logging
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient, AppendBlobClient

# Constants
KEYVAULT_NAME = 'keyvaultforbot'  # replace with your own keyvault
CONTAINER_NAME = 'botdata'
CSV_NAME = 'stoic_quotes_log_test.csv'

# Globals
keyvault_client = SecretClient(f"https://{KEYVAULT_NAME}.vault.azure.net/", DefaultAzureCredential())
blobstorage_account_name = keyvault_client.get_secret('blobstorage-account-name').value
blobstorage_secret = keyvault_client.get_secret('blobstorage-secret').value
blob_service_client = BlobServiceClient(account_url=f"https://{blobstorage_account_name}.blob.core.windows.net", credential=blobstorage_secret)

def ensure_container_exists():
    """Ensure the blob container exists; if not, create it."""
    if not blob_service_client.get_container_client(CONTAINER_NAME).exists():
        blob_service_client.create_container(CONTAINER_NAME)
        logging.info(f'Container {CONTAINER_NAME} created')

def get_old_terms():
    """Retrieve old quotes from append blob."""
    append_blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=CSV_NAME, blob_type="AppendBlob")
    if not append_blob_client.exists():
        append_blob_client.create_append_blob()
    data = append_blob_client.download_blob().content_as_text()
    return data.split('\n')

def add_term(term):
    """Add a new term to old terms and store in append blob."""
    append_blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=CSV_NAME, blob_type="AppendBlob")
    append_blob_client.append_block(f"{term}\n")

if __name__ == "__main__":
    ensure_container_exists()