#!/usr/bin/env python
# coding: utf-8

# # View Campaign and Interactions
# 
# In the first notebook `Personalize_BuildCampaign.ipynb` you successfully built and deployed a recommendation model using deep learning with Amazon Personalize.
# 
# This notebook will expand on that and will walk you through adding the ability to react to real time behavior of users. If their intent changes while browsing a movie, you will see revised recommendations based on that behavior.
# 
# It will also showcase demo code for simulating user behavior selecting movies before the recommendations are returned.

# Below we start with just importing libraries that we need to interact with Personalize

# In[25]:


# Imports

import boto3
import json
import numpy as np
import pandas as pd
import time
import uuid


# Below you will paste in the campaign ARN that you used in your previous notebook. Also pick a random user ID from 50 - 300. 
# 
# Lastly you will also need to find your Dataset Group ARN from the previous notebook.

# In[30]:


# Setup and Config
# Recommendations from Event data
personalize = boto3.client('personalize')
personalize_runtime = boto3.client('personalize-runtime')


HRNN_Campaign_ARN = "arn:aws:personalize:us-east-1:059124553121:campaign/personalize-demo-camp2"

# Define User 
USER_ID = "676"

# Dataset Group Arn:
datasetGroupArn = "arn:aws:personalize:us-east-1:370791210052:dataset-group/personalize-launch-demo1"

# Establish a connection to Personalize's Event Streaming
personalize_events = boto3.client(service_name='personalize-events')


# ## Creating an Event Tracker
# 
# Before your recommendation system can respond to real time events you will need an event tracker, the code below will generate one and can be used going forward with this lab. Feel free to name it something more clever.

# In[31]:


response = personalize.create_event_tracker(
    name='MovieClickTracker-Helen-Wang',
    datasetGroupArn=datasetGroupArn
)
print(response['eventTrackerArn'])
print(response['trackingId'])
TRACKING_ID = response['trackingId']


# ## Configuring Source Data
# 
# Above you'll see your tracking ID and this has been assigned to a variable so no further action is needed by you. The lines below are going to setup the data used for recommendations so you can render the list of movies later.

# In[32]:


# Interaction config
data = pd.read_csv('./ml-100k/u.data', sep='\t', names=['USER_ID', 'ITEM_ID', 'RATING', 'TIMESTAMP'])
pd.set_option('display.max_rows', 5)
data = data[data['RATING'] > 3]                # keep only movies rated 3
data = data[['USER_ID', 'ITEM_ID', 'TIMESTAMP']] # select columns that match the columns in the schema below
data


# In[33]:


# Item Config
items = pd.read_csv('./ml-100k/u.item', sep='|', usecols=[0,1], encoding='latin-1')
items.columns = ['ITEM_ID', 'TITLE']

user_id, item_id, _ = data.sample().values[0]
item_title = items.loc[items['ITEM_ID'] == item_id].values[0][-1]
print("USER: {}".format(user_id))
print("ITEM: {}".format(item_title))

items


# ## Getting Recommendations
# 
# Just like in the previous notebook it is a great idea to get a list of recommendatiosn first and then see how additional behavior by a user alters the recommendations.

# In[34]:


# Get Recommendations as is
get_recommendations_response = personalize_runtime.get_recommendations(
    campaignArn = HRNN_Campaign_ARN,
    userId = USER_ID,
)

item_list = get_recommendations_response['itemList']
title_list = [items.loc[items['ITEM_ID'] == np.int(item['itemId'])].values[0][-1] for item in item_list]

print("Recommendations: {}".format(json.dumps(title_list, indent=2)))
print(item_list)


# ## Simulating User Behavior
# 
# The lines below provide a code sample that simulates a user interacting with a particular item, you will then get recommendations that differ from those when you started.

# In[35]:


session_dict = {}


# In[36]:


def send_movie_click(USER_ID, ITEM_ID):
    """
    Simulates a click as an envent
    to send an event to Amazon Personalize's Event Tracker
    """
    # Configure Session
    try:
        session_ID = session_dict[USER_ID]
    except:
        session_dict[USER_ID] = str(uuid.uuid1())
        session_ID = session_dict[USER_ID]
        
    # Configure Properties:
    event = {
    "itemId": str(ITEM_ID),
    }
    event_json = json.dumps(event)
        
    # Make Call
    personalize_events.put_events(
    trackingId = TRACKING_ID,
    userId= USER_ID,
    sessionId = session_ID,
    eventList = [{
        'sentAt': int(time.time()),
        'eventType': 'EVENT_TYPE',
        'properties': event_json
        }]
)


# Immediately below this line will update the tracker as if the user has clicked a particular title.

# In[37]:


# Pick a movie, we will use ID 207 or Gattica
send_movie_click(USER_ID=USER_ID, ITEM_ID=207)


# After executing this block you will see the alterations in the recommendations now that you have event tracking enabled and that you have sent the events to the service.

# In[38]:


get_recommendations_response = personalize_runtime.get_recommendations(
    campaignArn = HRNN_Campaign_ARN,
    userId = str(USER_ID),
)

item_list = get_recommendations_response['itemList']
title_list = [items.loc[items['ITEM_ID'] == np.int(item['itemId'])].values[0][-1] for item in item_list]

print("Recommendations: {}".format(json.dumps(title_list, indent=2)))
print(item_list)


# ## Conclusion
# 
# You can see now that recommendations are altered by changing the movie that a user interacts with, this system can be modified to any application where users are interacting with a collection of items. These tools are available at any time to pull down and start exploring what is possible with the data you have.
# 
# Finally when you are ready to remove the items from your account, open the `Cleanup.ipynb` notebook and execute the steps there.
# 

# In[39]:


eventTrackerArn = response['eventTrackerArn']
print("Tracker ARN is: " + str(eventTrackerArn))


# In[ ]:




