import logging
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient, BlobClient  # Updated import

# Constants
KEYVAULT_NAME = 'keyvaultforbot'  # replace with your own keyvault
CONTAINER_NAME = 'botdata'
BLOB_NAME = 'stoic_quotes_log_test'

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

def ensure_blob_exists():
    """Ensure the append blob exists; if not, create it."""
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)
    if not blob_client.exists():
        blob_client.upload_blob("", blob_type="AppendBlob", overwrite=True)

def get_blob_client():
    """Get a BlobClient."""
    return blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=BLOB_NAME)

def get_old_terms():
    """Retrieve old quotes from append blob."""
    ensure_blob_exists()
    blob_client = get_blob_client()
    data = blob_client.download_blob().content_as_text()
    return data.split('\n')

def add_term(term):
    """Add a new term to old terms and store in append blob."""
    ensure_blob_exists()
    blob_client = get_blob_client()
    blob_client.append_block(f"{term}\n")

if __name__ == "__main__":
    ensure_container_exists()