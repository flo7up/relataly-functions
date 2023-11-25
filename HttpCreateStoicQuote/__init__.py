import logging
import json
import openai
import datetime as dt
import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from blob_manager_append import get_old_terms, add_term
from twitter_manager import publish_tweet

# Constants
KEYVAULT_NAME = 'keyvaultforbot'  # replace with your own keyvault

# Globals
keyvault_client = SecretClient(f"https://{KEYVAULT_NAME}.vault.azure.net/", DefaultAzureCredential())
openai_api_key = keyvault_client.get_secret('openai-api-key').value
openai.api_key = openai_api_key

def openai_request(instructions, task, sample, model_engine='gpt-3.5-turbo'):
    """Create an OpenAI request."""
    
    prompt = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": task}
    ]
    prompt = sample + prompt
    completion = openai.chat.completions.create(
        model=model_engine,
        messages=prompt,
        temperature=1.0,
        max_tokens=300
    )
    logging.info(completion.choices[0].message.content)
    return completion.choices[0].message.content

def create_tweet_prompt(quote):
    """Define OpenAI Prompt for News Tweet."""

    instructions = 'You run a twitter account about stoic quotes with a length below 280 characters. Create a tweet about the following stoic quote and just return the tweet.'
    task = f'{quote}'

    sample = [
        {"role": "user", "content": f"'The best revenge is to be unlike him who performed the injustice.' - Marcus Aurelius"},
        {"role": "assistant", "content": "🌿 'The best revenge is to be unlike him who performed the injustice.' - Marcus Aurelius. Let's cultivate kindness and rise above negativity, embracing the #Stoic path towards a peaceful mind and a harmonious life. 🧘‍♂️ #MarcusAurelius #StoicQuotes #Stoicism"},
        {"role": "user", "content": f" 'We cannot choose our external circumstances, but we can always choose how we respond to them.' - Epictetus"},
        {"role": "assistant", "content": "🌿 '💡 'We cannot choose our external circumstances, but we can always choose how we respond to them.' - Epictetus. Embrace the power of choice in response, not in circumstance. It's our reactions that define our journey. 🚀 #StoicQuotes #Stoicism #Epictetus #Mindfulness"}
    ]
    return instructions, task, sample


def create_term_prompt(old_terms):
    """Define OpenAI Prompt for News Tweet."""

    instructions = 'Your job is to continue a given list of stoic quotes and return another stoic quote in the same format.'
    task = f'{old_terms}'
    
    sample = []
    return instructions, task, sample

def create_tweet():
    """Create and post a tweet."""
    # Get old terms from blob
    old_terms = get_old_terms()['term'].to_list()
    logging.info(f'Old terms: {old_terms}')

    # Define prompt
    instructions, task, sample = create_term_prompt(old_terms[0:25])
    term = openai_request(instructions, task, sample)
    logging.info(f'Term created: {term}')

    instructions, task, sample = create_tweet_prompt(term)
    # Try three times to create a tweet with a length below 280 characters
    for _ in range(3):
        # Tweet creation
        tweet_text = openai_request(instructions, task, sample)
        
        # If tweet length > 280 characters, create a new tweet
        status = publish_tweet(tweet_text)
        if status != 'error tweet too long':
            logging.info(f'Tweet created: {tweet_text}')

            # Add term to list of old terms and store to blob storage
            add_term(old_terms, term)

            logging.info(f'Term added: {term}')
            break
        
    

def main(mytimer: func.TimerRequest) -> None:
    """Main function for handling the timer trigger."""
    utc_timestamp = dt.datetime.utcnow().replace(
        tzinfo=dt.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')

    create_tweet()

    logging.info('Python timer trigger function ran at %s', utc_timestamp)

if __name__ == "__main__":
    main()