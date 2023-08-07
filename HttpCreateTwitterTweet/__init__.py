
import azure.functions as func
import logging
import openai
import requests
import logging
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
import tweepy

# Set up the Azure Key Vault client and retrieve the Blob Storage account credentials
keyvault_name = 'keyvaultforbot'
client = SecretClient(f"https://{keyvault_name}.vault.azure.net/", DefaultAzureCredential())

#### Twitter Auth
twitter_api = tweepy.Client(bearer_token=client.get_secret('twitterbearertoken').value,
                    access_token=client.get_secret('twitter-access-token').value,
                    access_token_secret=client.get_secret('twitter-access-secret').value,
                    consumer_key=client.get_secret('twitter-api-key').value,
                    consumer_secret=client.get_secret('twitter-api-secret').value)

logging.info('Twitter API ready')

##### OpenAI API Key
openai.api_key = client.get_secret('openai-api-key').value

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    title = req.params.get('title')
    description = req.params.get('description')
    url = req.params.get('url')
    if not title:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            title = req_body.get('title')

    if title:
        create_tweet(title, description, url)

        return func.HttpResponse(f"{title}. This HTTP triggered function executed successfully.")
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )
    

def create_tiny_url(url):
    response = requests.get(f'http://tinyurl.com/api-create.php?url={url}')
    shortened_url = response.text
    return shortened_url

### OpenAI API
def openai_request(instructions, task, model_engine='gpt-3.5-turbo'):
    prompt = [{"role": "system", "content": instructions }, 
              {"role": "user", "content": task }]
    completion = openai.ChatCompletion.create(model=model_engine, messages=prompt, temperature=0.5, max_tokens=300)
    return completion.choices[0].message.content


#### Define OpenAI Prompt for News Tweet
def create_tweet_prompt(title, description, tiny_url):
    instructions = f'You are a twitter user that creates tweets with a maximum length of 280 characters.'
    task = f"Create an informative tweet on twitter based on the following news title and description. \
        The tweet must use a maximum of 280 characters. \
        Include the {tiny_url}. But do not include any other urls.\
        Title: {title}. \
        Description: {description}. \
        Use hashtags to reach a wider audience. \
        Do not include any emojis in the tweet"
    return instructions, task


def check_tweet_length(tweet):
    if len(tweet) > 280:
        print(f'Tweet too long: {len(tweet)}')
        return False
    else:
        print(f'Tweet length OK: {len(tweet)}')
        return True
    
def create_tweet(title, description, url):
    # create tiny url
    tiny_url = create_tiny_url(url)

    # define prompt
    instructions, task = create_tweet_prompt(title, description, tiny_url)

    # tweet creation
    tweet = openai_request(instructions, task)
    tweet = tweet.replace('"', '')

    # check tweet length and post tweet
    if check_tweet_length(tweet):
            print(f'Creating tweet: {tweet}')
            status = twitter_api.create_tweet(text=tweet)
            #logging.info(f'Tweet posted: {status.id}')
    else: 
        status = 'error tweet too long'
    return status