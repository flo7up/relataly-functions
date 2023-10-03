import azure.functions as func
import logging
import requests
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import tweepy
import csv
import os.path
import datetime as dt

# Set up the Azure Key Vault client and retrieve the Blob Storage account credentials
keyvault_name = 'keyvaultforbot' # replace with your own keyvault
client = SecretClient(f"https://{keyvault_name}.vault.azure.net/", DefaultAzureCredential())

#### Twitter Auth
twitter_api = tweepy.Client(bearer_token=client.get_secret('twitterbearertoken').value,
                    access_token=client.get_secret('twitter-access-token').value,
                    access_token_secret=client.get_secret('twitter-access-secret').value,
                    consumer_key=client.get_secret('twitter-api-key').value,
                    consumer_secret=client.get_secret('twitter-api-secret').value)

logging.info('Twitter API ready')

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    title = req.params.get('tweet')

    if title:
        create_tweet(tweet)

        return func.HttpResponse(f"{title}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
    

def log_to_csv(tweet):

    if not os.path.isfile('tweets.csv'):
        with open('tweets.csv', 'w') as f:
            writer = csv.writer(f)
            writer.writerow(['tweet', 'date'])
    
    with open('tweets.csv', 'a') as f:
         writer = csv.writer(f)
         timestamp = dt.datetime.now()
         writer.writerow([tweet, timestamp])

def create_tweet(tweet):

    status = twitter_api.create_tweet(text=tweet)
    # create a csv if it does not exist

    log_to_csv(tweet)

    return status