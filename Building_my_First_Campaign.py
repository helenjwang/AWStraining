#!/usr/bin/env python
# coding: utf-8

# # Building Your First Campaign
# 
# This notebook will walk you through the steps to build a recommendation model for movies based on data collected from the movielens data set. The goal is to recommend movies that are relevant based on a particular user.
# 
# The data is coming from the MovieLens project, you can google it during any of the waiting periods to learn more about the data and potential uses.

# ## How to Use the Notebook
# 
# Code is broken up into cells like the one below. There's a triangular `Run` button at the top of this page you can click to execute each cell and move onto the next, or you can press `Shift` + `Enter` while in the cell to execute it and move onto the next one.
# 
# As a cell is executing you'll notice a line to the side showcase an `*` while the cell is running or it will update to a number to indicate the last cell that completed executing after it has finished exectuting all the code within a cell.
# 
# 
# Simply follow the instructions below and execute the cells to get started with Amazon Personalize.

# ## Imports 
# 
# Python ships with a broad collection of libraries and we need to import those as well as the ones installed to help us like boto3(The AWS SDK) and Pandas/Numpy which are core data science tools

# In[26]:


# Imports
import boto3
import json
import numpy as np
import pandas as pd
import time


# Next you will want to validate that your environment can communicate successfully with Amazon Personalize, the lines below do just that.

# In[27]:


# Configure the SDK to Personalize:
personalize = boto3.client('personalize')
personalize_runtime = boto3.client('personalize-runtime')


# ## Configure the data
# 
# Data is imported into Amazon Personalize through Amazon S3, below we will specify a bucket that you have created within AWS for the purposes of this exercise.
# 
# Below you will update the `bucket` variable to instead be set to the value that you created earlier in the CloudFormation steps, this should be in a text file from your earlier work. the `filename` does not need to be changed.
# 
# ### Specify a Bucket and Data Output Location

# In[28]:


bucket = "personalizedemohelenwang0315"       # replace with the name of your S3 bucket
filename = "movie-lens-100k.csv"


# ### Download, Prepare, and Upload Training Data
# 
# At present you do not have the MovieLens data loaded locally yet for examination, execute the lines below to download the latest copy and to examine it quickly.

# #### Download and Explore the Dataset

# In[29]:


get_ipython().system('wget -N http://files.grouplens.org/datasets/movielens/ml-100k.zip')
get_ipython().system('unzip -o ml-100k.zip')
data = pd.read_csv('./ml-100k/u.data', sep='\t', names=['USER_ID', 'ITEM_ID', 'RATING', 'TIMESTAMP'])
pd.set_option('display.max_rows', 5)
data


# #### Prepare and Upload Data
# 
# As you can see the data contains a UserID, ItemID, Rating, and Timestamp.
# 
# We are now going to remove the items with low rankings, and remove that column before we build our model.
# 
# Once done we will now save the file as a new CSV and then upload it to S3.
# 
# All of that is done by simply executing the lines below.

# In[30]:


data = data[data['RATING'] > 3]                # Keep only movies rated higher than 3 out of 5.
data = data[['USER_ID', 'ITEM_ID', 'TIMESTAMP']] # select columns that match the columns in the schema below
data.to_csv(filename, index=False)
boto3.Session().resource('s3').Bucket(bucket).Object(filename).upload_file(filename)


# ### Create Schema
# 
# A core component of how Personalize understands your data comes from the Schema that is defined below. This configuration tells the service how to digest the data provided via your CSV file. Note the columns and types align to what was in the file you created above.

# In[32]:


schema = {
    "type": "record",
    "name": "Interactions",
    "namespace": "com.amazonaws.personalize.schema",
    "fields": [
        {
            "name": "USER_ID",
            "type": "string"
        },
        {
            "name": "ITEM_ID",
            "type": "string"
        },
        {
            "name": "TIMESTAMP",
            "type": "long"
        }
    ],
    "version": "1.0"
}

create_schema_response = personalize.create_schema(
    name = "personalize-demo-schema1",
    schema = json.dumps(schema)
)

schema_arn = create_schema_response['schemaArn']
print(json.dumps(create_schema_response, indent=2))


# ### Create and Wait for Dataset Group
# 
# The largest grouping in Personalize is a Dataset Group, this will isolate your data, event trackers, solutions, and campaigns. Grouping things together that share a common collection of data. Feel free to alter the name below if you'd like.

# #### Create Dataset Group

# In[33]:


create_dataset_group_response = personalize.create_dataset_group(
    name = "personalize-launch-demo1"
)

dataset_group_arn = create_dataset_group_response['datasetGroupArn']
print(json.dumps(create_dataset_group_response, indent=2))


# #### Wait for Dataset Group to Have ACTIVE Status
# 
# Before we can use the Dataset Group in any items below it must be active, execute the cell below and wait for it to show active.

# In[34]:


max_time = time.time() + 3*60*60 # 3 hours
while time.time() < max_time:
    describe_dataset_group_response = personalize.describe_dataset_group(
        datasetGroupArn = dataset_group_arn
    )
    status = describe_dataset_group_response["datasetGroup"]["status"]
    print("DatasetGroup: {}".format(status))
    
    if status == "ACTIVE" or status == "CREATE FAILED":
        break
        
    time.sleep(60)


# ### Create Dataset
# 
# After the group, the next thing to create is the actual datasets, in this example we will only create 1 for the interactions data. Execute the cells below to create it.

# In[35]:


dataset_type = "INTERACTIONS"
create_dataset_response = personalize.create_dataset(
    name = "personalize-launch-interactions",
    datasetType = dataset_type,
    datasetGroupArn = dataset_group_arn,
    schemaArn = schema_arn
)

dataset_arn = create_dataset_response['datasetArn']
print(json.dumps(create_dataset_response, indent=2))


# #### Attach Policy to S3 Bucket
# 
# Amazon Personalize needs to be able to read the content of your S3 bucket that you created earlier. The lines below will do that.

# In[36]:


s3 = boto3.client("s3")

policy = {
    "Version": "2012-10-17",
    "Id": "PersonalizeS3BucketAccessPolicy",
    "Statement": [
        {
            "Sid": "PersonalizeS3BucketAccessPolicy",
            "Effect": "Allow",
            "Principal": {
                "Service": "personalize.amazonaws.com"
            },
            "Action": [
                "s3:GetObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::{}".format(bucket),
                "arn:aws:s3:::{}/*".format(bucket)
            ]
        }
    ]
}

s3.put_bucket_policy(Bucket=bucket, Policy=json.dumps(policy))


# #### Create Personalize Role
# 
# Also Amazon Personalize needs the ability to assume Roles in AWS in order to have the permissions to execute certain tasks, the lines below grant that.

# In[37]:


iam = boto3.client("iam")

role_name = "PersonalizeRoleDemo"
assume_role_policy_document = {
    "Version": "2012-10-17",
    "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "personalize.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
    ]
}

create_role_response = iam.create_role(
    RoleName = role_name,
    AssumeRolePolicyDocument = json.dumps(assume_role_policy_document)
)

# AmazonPersonalizeFullAccess provides access to any S3 bucket with a name that includes "personalize" or "Personalize" 
# if you would like to use a bucket with a different name, please consider creating and attaching a new policy
# that provides read access to your bucket or attaching the AmazonS3ReadOnlyAccess policy to the role
policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonPersonalizeFullAccess"
iam.attach_role_policy(
    RoleName = role_name,
    PolicyArn = policy_arn
)

# Now add S3 support
iam.attach_role_policy(
    PolicyArn='arn:aws:iam::aws:policy/AmazonS3FullAccess',
    RoleName=role_name
)
time.sleep(60) # wait for a minute to allow IAM role policy attachment to propagate

role_arn = create_role_response["Role"]["Arn"]
print(role_arn)


# ## Import the data
# 
# Earlier you created the DatasetGroup and Dataset to house your information, now you will execute an import job that will load the data from S3 into Amazon Personalize for usage building your model.

# #### Create Dataset Import Job

# In[38]:


create_dataset_import_job_response = personalize.create_dataset_import_job(
    jobName = "personalize-demo-import1",
    datasetArn = dataset_arn,
    dataSource = {
        "dataLocation": "s3://{}/{}".format(bucket, filename)
    },
    roleArn = role_arn
)

dataset_import_job_arn = create_dataset_import_job_response['datasetImportJobArn']
print(json.dumps(create_dataset_import_job_response, indent=2))


# #### Wait for Dataset Import Job to Have ACTIVE Status
# 
# It can take a while before the import job completes, please wait until you see that it is active below.

# In[42]:


max_time = time.time() + 3*60*60 # 3 hours
while time.time() < max_time:
    describe_dataset_import_job_response = personalize.describe_dataset_import_job(
        datasetImportJobArn = dataset_import_job_arn
    )
    status = describe_dataset_import_job_response["datasetImportJob"]['status']
    print("DatasetImportJob: {}".format(status))
    
    if status == "ACTIVE" or status == "CREATE FAILED":
        break
        
    time.sleep(60)


# ## Create the Solution and Version
# 
# In Amazon Personalize a trained model is called a Solution, each Solution can have many specific versions that relate to a given volume of data when the model was trained.
# 
# To begin we will list all the recipies that are supported, a recipie is an algorithm that has not been trained on your data yet. After listing you'll select one and use that to build your model.

# ### Select Recipe

# In[43]:


list_recipes_response = personalize.list_recipes()
list_recipes_response


# Here you can see below that we are picking the `HRNN` recipie.

# In[44]:


recipe_arn = "arn:aws:personalize:::recipe/aws-hrnn" # aws-hrnn selected for demo purposes


# ### Create and Wait for Solution
# 
# First you will create the solution with the API, then you will create a version. It will take several minutes to train the model and thus create your version of a solution. Once it gets started and you are seeing the in progress notifications it is a good time to take a break, grab a coffee, etc.

# #### Create Solution

# In[45]:


create_solution_response = personalize.create_solution(
    name = "personalize-demo-soln-hrnn",
    datasetGroupArn = dataset_group_arn,
    recipeArn = recipe_arn
)

solution_arn = create_solution_response['solutionArn']
print(json.dumps(create_solution_response, indent=2))


# #### Create Solution Version

# In[46]:


create_solution_version_response = personalize.create_solution_version(
    solutionArn = solution_arn
)

solution_version_arn = create_solution_version_response['solutionVersionArn']
print(json.dumps(create_solution_version_response, indent=2))


# #### Wait for Solution Version to Have ACTIVE Status
# 
# This will take at least 20 minutes.

# In[52]:


max_time = time.time() + 3*60*60 # 3 hours
while time.time() < max_time:
    describe_solution_version_response = personalize.describe_solution_version(
        solutionVersionArn = solution_version_arn
    )
    status = describe_solution_version_response["solutionVersion"]["status"]
    print("SolutionVersion: {}".format(status))
    
    if status == "ACTIVE" or status == "CREATE FAILED":
        break
        
    time.sleep(60)


# #### Get Metrics of Solution Version
# 
# Now that your solution and version exists, you can obtain the metrics for it to judge its performance. These metrics are not particularly good as it is a demo set of data, but with larger more compelx datasets you should see improvements.

# In[54]:


get_solution_metrics_response = personalize.get_solution_metrics(
    solutionVersionArn = solution_version_arn
)

print(json.dumps(get_solution_metrics_response, indent=2))


# ## Create and Wait for the Campaign
# 
# Now that you have a working solution version you will need to create a campaign to use it with your applications. A campaign is simply a hosted copy of your model. Again there will be a short wait so after executing you can take a quick break while the infrastructure is being provisioned.

# #### Create Campaign

# In[57]:


create_campaign_response = personalize.create_campaign(
    name = "personalize-demo-camp2",
    solutionVersionArn = solution_version_arn,
    minProvisionedTPS = 1
)

campaign_arn = create_campaign_response['campaignArn']
print(json.dumps(create_campaign_response, indent=2))


# #### Wait for Campaign to Have ACTIVE Status

# In[ ]:


max_time = time.time() + 3*60*60 # 3 hours
while time.time() < max_time:
    describe_campaign_response = personalize.describe_campaign(
        campaignArn = campaign_arn
    )
    status = describe_campaign_response["campaign"]["status"]
    print("Campaign: {}".format(status))
    
    if status == "ACTIVE" or status == "CREATE FAILED":
        break
        
    time.sleep(60)


# ## Get Sample Recommendations
# 
# After the campaign is active you are ready to get recommendations. The lines below will sample a random user and random movie and will aid you with getting recommendations below,.

# #### Select a User and an Item

# In[61]:


items = pd.read_csv('./ml-100k/u.item', sep='|', usecols=[0,1], encoding='latin-1')
items.columns = ['ITEM_ID', 'TITLE']

user_id, item_id, _ = data.sample().values[0]
item_title = items.loc[items['ITEM_ID'] == item_id].values[0][-1]
print("USER: {}".format(user_id))
print("ITEM: {}".format(item_title))

items


# #### Call GetRecommendations
# 
# Using the user that you obtained above, the lines below will get recommendations for you and return the list of movies that are recommended.
# 

# In[62]:


get_recommendations_response = personalize_runtime.get_recommendations(
    campaignArn = campaign_arn,
    userId = str(user_id),
)

item_list = get_recommendations_response['itemList']
title_list = [items.loc[items['ITEM_ID'] == np.int(item['itemId'])].values[0][-1] for item in item_list]

print("Recommendations: {}".format(json.dumps(title_list, indent=2)))


# ## Review
# 
# Using the codes above you have successfully trained a deep learning model to generate movie recommendations based on prior user behavior. Think about other types of problems where this data is available and what it might look like to build a system like this to offer those recommendations.
# 
# Now you are ready to move onto the next notebook `2.View_Campaign_And_Interactions.ipynb`
# 
# 

# ## Notes for the Next Notebook:
# 
# There are a few values you will need for the next notebook, execute the cells below to print them so they can be copied and pasted into the next part of the exercise.

# In[63]:


print("Campaign ARN is: " + str(campaign_arn))


# In[64]:


print("Dataset Group ARN is: " + str(dataset_group_arn))


# In[65]:


print("Solution Version ARN is: " + str(solution_version_arn))


# In[66]:


print("Solution ARN is: " + str(solution_arn))


# In[67]:


print("Dataset Interactions ARN is: " + str(dataset_arn))


# In[ ]:




