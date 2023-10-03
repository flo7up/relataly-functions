import logging
import tweepy
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Constants
KEYVAULT_NAME = 'keyvaultforbot'  # replace with your own keyvault

# Globals
keyvault_client = SecretClient(f"https://{KEYVAULT_NAME}.vault.azure.net/", DefaultAzureCredential())
twitter_api = tweepy.Client(
    bearer_token=keyvault_client.get_secret('twitterbearertoken').value,
    access_token=keyvault_client.get_secret('twitter-access-token').value,
    access_token_secret=keyvault_client.get_secret('twitter-access-secret').value,
    consumer_key=keyvault_client.get_secret('twitter-api-key').value,
    consumer_secret=keyvault_client.get_secret('twitter-api-secret').value
)

def check_tweet_length(tweet):
    """Check if tweet length is within Twitter's limit."""
    
    if len(tweet) > 280:
        logging.error(f'Tweet too long: {len(tweet)}')
        return False
    else:
        logging.info(f'Tweet length OK: {len(tweet)}')
        return True

def publish_tweet(tweet_text):
    """Publish a tweet on Twitter."""
    if check_tweet_length(tweet_text):
        status = twitter_api.create_tweet(text=tweet_text)
        logging.info(f'Tweet posted: {status}')
        return status
    else:
        logging.error(f'Tweet too long: {len(tweet_text)}')
        return 'error tweet too long'