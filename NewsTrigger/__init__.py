import datetime as dt
import logging
import requests
import pandas as pd
import azure.functions as func
import openai
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.storage.blob import BlobServiceClient
import io
from newspaper import Article
from bs4 import BeautifulSoup
from hackernews import HackerNews

# Use environment variables for API key
client = SecretClient(f"https://{'keyvaultforbot'}.vault.azure.net/", DefaultAzureCredential())
logging.info('Setting NewsAPI API Key')
NEWSAPI_API_KEY = client.get_secret('newsapi-api-key').value

logging.info('Setting OpenAI API Key')
OPENAI_API_KEY = client.get_secret('openai-api-key').value
openai.api_key = OPENAI_API_KEY

logging.info('Setting Function App API Key')
API_KEY = client.get_secret('function-app-api').value

##### Azure Blob Storage
blobstorage_account_name = client.get_secret('blobstorage-account-name').value
blobstorage_secret = client.get_secret('blobstorage-secret').value
CONTAINER_NAME = 'botdata'
CSV_NAME = 'news_log.csv'

# check if container exists
blob_service_client = BlobServiceClient(account_url=f"https://{blobstorage_account_name}.blob.core.windows.net", credential=blobstorage_secret)
if not blob_service_client.get_container_client(CONTAINER_NAME).exists():
    blob_service_client.create_container(CONTAINER_NAME)
    logging.info(f'Container {CONTAINER_NAME} created')
container_client = blob_service_client.get_container_client(CONTAINER_NAME)
logging.info ('Container client ready')

def get_old_news():
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=CSV_NAME)
    data = blob_client.download_blob().content_as_text()
    df = pd.read_csv(io.StringIO(data))
    logging.info('Posts log retrieved from blob storage')
    return df

def save_posts_log(df):
    blob_client = blob_service_client.get_blob_client(container=CONTAINER_NAME, blob=CSV_NAME)
    blob_client.upload_blob(data=df.to_csv(index=False), overwrite=True)
    logging.info(f'File {CSV_NAME} saved to blob storage')
    print(f'File {CSV_NAME} saved to blob storage')
    return True


#### NewsAPI
def fetch_newsapi_news(number=10):
    # Fetch tech news from NewsAPI
    url = f"https://newsapi.org/v2/top-headlines?country=us&category=technology&category=business&category=science&apiKey={NEWSAPI_API_KEY}"
    response = requests.get(url).json()
    news_items = response["articles"]
    df = pd.DataFrame(news_items)
    df = df[["title", "description", "url"]].dropna()
    return df.head(number)


def fetch_main_content_from_url(url):
    article = Article(url)
    article.download()
    article.parse()
    return article.text

#### HackerNews
def fetch_hacker_news(number=50):
    hn = HackerNews()
    top_story_ids = hn.top_stories()

    news_list = []
    for story in top_story_ids[:number]:
        item = hn.item(story)
        if item.score > 200 and len(item.title) > 30:
            try:
                content = fetch_main_content_from_url(item.url)[0:3000]
                logging.info(f'Content for {item.title} fetched')
                logging.info(f'Content length: {len(content)}')
            except:
                content = ''
        
            news_list.append({
                'title': item.title,
                'description': content,  # empty description
                'url': item.url
            })

    df = pd.DataFrame(news_list)
    return df

#### OpenAI Engine
def openai_request(instructions, task, sample = [], temperature=0.5, model_engine='gpt-3.5-turbo'):
    prompt = [{"role": "system", "content": instructions }, 
              {"role": "user", "content": task }]
    prompt = sample + prompt
    completion = openai.ChatCompletion.create(model=model_engine, messages=prompt, temperature=temperature, max_tokens=400)
    return completion.choices[0].message.content


#### Define OpenAI Prompt for news Relevance
def select_relevant_news_prompt(news_articles, topics, n):    
    instructions = f"Please review the given list of news titles. Determine their relevance to an audience keen on the following topics: {topics}]. \
    Provide a list of boolean values (True or False) corresponding to each title's relevance."
    task =  f"{news_articles}?" 
    sample = [
        {"role": "user", "content": f"['new AI model available from Nvidia', 'We Exploded the AMD Ryzen 7', 'Release of b2 Game', 'XGBoost 3.0 improvices Decision Forest Algorithms', 'New Zelda Game Now Available']"},
        {"role": "assistant", "content": "[True, False, False, True, False]"},
        {"role": "user", "content": f"['Giant giraffs found in Africa', 'We Exploded the AMD Ryzen 7', 'Rumors about ChatGPT-5', 'Donald Trump to make a come back', 'New Zelda Game Now Available']"}, 
        {"role": "assistant", "content": "[False, False, True, False, False]"},
        {"role": "user", "content": f"['Ukraine Uses a New Weapon', 'Microsoft announces new analytics suite', 'introducing boooi', 'Did you hear of Toyota?', 'Alberta AG launches Virtual Assistant']"}, 
        {"role": "assistant", "content": "[False, False, False, False, True]"}
        ]
    
    return instructions, task, sample


#### Define OpenAI Prompt for news Relevance
def check_previous_posts_prompt(title, old_posts):    
    instructions = f'Assess the level of novelty in a given list of articles. You will compare a news title with a list of previous news and score the noveliy of the articles on a scale of 0 to 5, where 5 indicates a complete overlap and 0 signifies a novel topic.'
    task =  f"'{title}. /n Previous News: {old_posts}' "
    sample = [
        {"role": "user", "content": "'Nvidia launches new AI model.' /n [new AI model available from Nvidia, We Exploded the AMD Ryzen 7 7800X3D, The Lara Croft Collection For Switch Has Been Rated By The ESRB]."},
        {"role": "assistant", "content": "5"},
        {"role": "user", "content": "'Big Explosion of an AMD Ryzen 7.' /n [Improving Mental Wellbeing Through Physical Activity, The Lara Croft Collection For Switch Has Been Rated By The ESRB]."},
        {"role": "assistant", "content": "0"},
        {"role": "user", "content": "'new AI model available from Google.' /n [new AI model available from Nvidia, The Lara Croft Collection For Switch Has Been Rated By The ESRB]."},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "'What Really Made Geoffrey Hinton Into an AI Doomer - WIRED.' /n [Why AI's 'godfather' Geoffrey Hinton quit Google, new AI model available from Nvidia, The Lara Croft Collection For Switch Has Been Rated By The ESRB]."},
        {"role": "assistant", "content": "4"}]
    return instructions, task, sample


#### Define OpenAI Prompt for news Relevance
def call_tweet_function(title, description, url):
    logging.info('Calling Azure Function App to Create Tweet')
    # Define the Azure Function App URL
    request_url = f"https://relatalyfunc.azurewebsites.net/api/HttpCreateTwitterTweet?title={title}&description={description}&url={url}"
    headers = {"x-functions-key": API_KEY}
    response = requests.post(request_url, headers=headers)

    # Check the response status
    if response.status_code == 200:
        print("Azure Function App called successfully.")
    else:
        print("Error calling Azure Function App.")
        print("Response:", response.text)

    return response.status_code


#### Define OpenAI Prompt for news Relevance
def create_fact_tweet(input=""):    
    logging.info('Calling Azure Function App to Create Fact Tweet')
    # Define the Azure Function App URL
    request_url = f"https://relatalyfunc.azurewebsites.net/api/HttpCreateTwitterFactTweet?input={input}"
    headers = {"x-functions-key": API_KEY}
    response = requests.post(request_url, headers=headers)

    # Check the response status
    if response.status_code == 200:
        print("Azure Function App called successfully.")
    else:
        print("Error calling Azure Function App.")
        print("Response:", response.text)
    return response.status_code


#### Define OpenAI Prompt for news Relevance
def previous_post_check(title, old_posts):
    instructions, task, sample = check_previous_posts_prompt(title, old_posts)
    response = openai_request(instructions, task, sample)
    logging.info('doublicate_check:' + response)
    response = eval(response)
    logging.info('doublicate_check:' + str(response))
    return response


#### Main Bot
def main_bot(df):
    df_old = get_old_news()
    df_old = df_old.tail(16)
    logging.info(df_old)
    print(df_old)
    # Fetch news data
    
    logging.info(df['title'])
    
    # Check the Relevance of the News and Filter those not relevant
    relevant_topics ="[machine learning, data science, robotics, openai, artificial intelligence (ai), neural networks, data mining, tensorflow, pytorch, nlp, data analytics, virtual assistants, chatbots, augmented reality, chatgpt, gpt, gpu, anthropic, microsoft, apple, nvidia]"
    instructions, task, sample = select_relevant_news_prompt(list(df['title']), relevant_topics, len(list(df['title'])))
    temperature=0.0
    relevance = openai_request(instructions, task, sample, temperature)
    logging.info(len(list(df['title'])))
    logging.info('relevance:' + relevance)
    relevance_list = eval(relevance)
    logging.info(len(relevance_list))

    s = 0
    df = df[relevance_list]
    if len(df) > 0:
        for index, row in df.iterrows():
            if s == 1:
                break
            logging.info('info:' + row['title'])
            title = row['title']
            title = title.replace("'", "")
            description = row['description']
            url = row['url']            
                                             
            if (title not in df_old.title.values):
                doublicate_check = previous_post_check(title, list(df_old.tail(10)['title']))
                if doublicate_check < 4:
                    # create tweet
                    response = call_tweet_function(title, description, url)
                    if response == 200:
                        print(f"Tweeted: {title}")
                        #add title to the csv file  
                        save_posts_log(pd.concat([df_old, pd.DataFrame({'title': [title]})], ignore_index=True))
                        s += 1
                    else:
                        print(f"Error: {response}")
                        logging.info(f"Error: {response}")
                else: 
                    print(f"Doublicate Context Check True: {title}")
                    logging.info(f"Context Doublicate: {title}")
                    save_posts_log(pd.concat([df_old, pd.DataFrame({'title': [title]})], ignore_index=True))
            else: 
                print(f"Already tweeted: {title}")
                logging.info(f"Already tweeted: {title}")
                
    else: 
        print("No news articles found")
        logging.info("No news articles found")
        # 20% chance to tweet a fact
        import random
        if random.random() < 0.2:
            fact = ' '
            print(f"Fact: {fact}")
            logging.info(f"Fact: {fact}")
            response = create_fact_tweet(fact)
            if response == 200:
                print(f"Tweeted: {fact}")
                logging.info(f"Tweeted: {fact}")
            else:
                print(f"Error: {response}")
                logging.info(f"Error: {response}")



def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = dt.datetime.utcnow().replace(
        tzinfo=dt.timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')
    df_news_api = fetch_newsapi_news(5)
    main_bot(df_news_api)
    df_hacker_news = fetch_newsapi_news(10)
    main_bot(df_hacker_news)


    logging.info('Python timer trigger function ran at %s', utc_timestamp)