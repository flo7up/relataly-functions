import logging
import io
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
import openai
import pandas as pd
import tweepy

# Constants
KEYVAULT_NAME = 'keyvaultforbot'
CONTAINER_NAME = 'botdata'
CSV_NAME = 'facts_log_test.csv'

# Globals
keyvault_client = None
blob_service_client = None
openai_api_key = None
twitter_api = None



"""Setup for retrieving Azure Key Vault secrets and creating the clients."""

# Azure Key Vault client setup
keyvault_client = SecretClient(f"https://{KEYVAULT_NAME}.vault.azure.net/", DefaultAzureCredential())

# Blob Storage setup
blobstorage_account_name = keyvault_client.get_secret('blobstorage-account-name').value
blobstorage_secret = keyvault_client.get_secret('blobstorage-secret').value
blob_service_client = BlobServiceClient(account_url=f"https://{blobstorage_account_name}.blob.core.windows.net", credential=blobstorage_secret)

# Twitter Auth
twitter_api = tweepy.Client(
    bearer_token=keyvault_client.get_secret('twitterbearertoken').value,
    access_token=keyvault_client.get_secret('twitter-access-token').value,
    access_token_secret=keyvault_client.get_secret('twitter-access-secret').value,
    consumer_key=keyvault_client.get_secret('twitter-api-key').value,
    consumer_secret=keyvault_client.get_secret('twitter-api-secret').value
)

# OpenAI API Key
openai_api_key = keyvault_client.get_secret('openai-api-key').value
openai.api_key = openai_api_key


def ensure_container_exists():
    """Ensure the blob container exists; if not, create it."""

    if not blob_service_client.get_container_client(CONTAINER_NAME).exists():
        blob_service_client.create_container(CONTAINER_NAME)
        logging.info(f'Container {CONTAINER_NAME} created')


def get_old_terms():
    """Retrieve old terms from blob storage."""

    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=CSV_NAME)
    if not blob_client.exists():
        empty_df = pd.DataFrame(columns=['term'])
        blob_client.upload_blob(data=empty_df.to_csv(index=False), overwrite=True)

    data = blob_client.download_blob().content_as_text()
    df = pd.read_csv(io.StringIO(data))
    logging.info('Posts log retrieved from blob storage')
    return df


def openai_request(instructions, task, sample, model_engine='gpt-3.5-turbo'):
    """Create an OpenAI request."""

    prompt = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": task}
    ]
    prompt = sample + prompt
    completion = openai.ChatCompletion.create(
        model=model_engine,
        messages=prompt,
        temperature=0.5,
        max_tokens=300
    )
    logging.info(completion.choices[0].message.content)
    return completion.choices[0].message.content


def create_tweet_prompt(old_terms):
    """Define OpenAI Prompt for News Tweet."""

    instructions = 'You are a twitter user that creates tweets with a length below 280 characters.'
    task = 'Choose a technical term from the field of AI, machine learning or data science. Then create a twitter tweet that describes the term. Just return a python dictionary with the term and the tweet.'
    
    if old_terms != []:
        avoid_terms =f'Avoid the following terms, because you have previously tweetet about them: {old_terms}'
        task = task + avoid_terms

    sample = [
        {"role": "user", "content": f"Choose a technical term from the field of AI, machine learning or data science. Then create a twitter tweet that describes the term. Just return a python dictionary with the term and the tweet."},
        {"role": "assistant", "content": "{'GradientDescent': '#GradientDescent is a popular optimization algorithm used to minimize the error of a model by adjusting its parameters. \
         It works by iteratively calculating the gradient of the error with respect to the parameters and updating them accordingly. #ML'}"}
    ]
    return instructions, task, sample


def check_tweet_length(tweet):
    """Check if tweet length is within Twitter's limit."""
    
    if len(tweet) > 280:
        logging.error(f'Tweet too long: {len(tweet)}')
        return False
    else:
        logging.info(f'Tweet length OK: {len(tweet)}')
        return True


def add_term(old_terms, term):
    """Add a new term to old terms and store in blob storage."""

    old_terms.append(term)
    df = pd.DataFrame(old_terms, columns=['term'])
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=CSV_NAME)
    blob_client.upload_blob(data=df.to_csv(index=False), overwrite=True)


def create_tweet():
    """Create and post a tweet."""

    # Get old terms from blob
    old_terms = get_old_terms()['term'].to_list()
    logging.info(f'Old terms: {old_terms}')

    # Define prompt
    instructions, task, sample = create_tweet_prompt(old_terms[0:25])

    # Try three times to create a tweet with a length below 280 characters
    for _ in range(3):
        # Tweet creation
        tweet = openai_request(instructions, task, sample)
        logging.info(f'Tweet created: {tweet}')

        tweet_text = str(list(eval(tweet).values())[0])
        term = str(list(eval(tweet).keys())[0])

        # If tweet length > 280 characters, create a new tweet
        if check_tweet_length(tweet_text):
            logging.info(f'Tweet created: {tweet_text}')

            # Create tweet
            status = twitter_api.create_tweet(text=tweet_text)
            logging.info(f'Twitter response: {status.id}')

            # Add term to list of old terms and store to blob storage
            add_term(old_terms, term)

            logging.info(f'Tweet posted: {status["data"]["id"]}')
            logging.info(f'Term added: {term}')
            return status, term, tweet_text
            

    return 'error tweet too long', '', ''


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Main function for handling the HTTP trigger."""

    logging.info('Python HTTP trigger function processed a request.')


    
    status, term, tweet = create_tweet()
    return func.HttpResponse(
        f"This HTTP triggered function executed successfully.",
        status=status,
        tweet_id=status["data"]["id"],
        term=term,
        tweet=status["data"]["text"]
    )



if __name__ == "__main__":
    ensure_container_exists()
    main()
