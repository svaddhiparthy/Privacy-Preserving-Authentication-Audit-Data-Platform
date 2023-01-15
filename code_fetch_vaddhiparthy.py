# Loading libraries
import boto3  # for communicating with AWS Resources
import hashlib  # for masking
import psycopg2  # to connect to PostgresSQL database
import json  # to parse JSON data
from datetime import datetime  # to generate current date

''' Extracting the data from SQS Service
connect to the localstack SQS service (for real-time scenarios, the access credentials can be stored on a different file)'''
sqs = boto3.client('sqs', aws_access_key_id="suryaid", aws_secret_access_key='suryapass',
                   endpoint_url='http://localhost:4566', region_name='us-east-1')
# Receive messages from the SQS queue running on docker image on port 4566
response = sqs.receive_message(QueueUrl='http://localhost:4566/000000000000/login-queue')
messages = response['Messages']

''' Transforming data:
1. The data transformed through this way is hard to be reversed and uniqueness is preserved
2. The app version as per DDL is an int, hence transforming data to suit destination data-type 
'''
# Iterating through the messages
for message in messages:
    # Parse the JSON data
    data = json.loads(message['Body'])

    # Masking the device_id and ip fields
    hasher = hashlib.sha256()
    hasher.update(data['device_id'].encode('utf-8'))
    masked_device_id = hasher.hexdigest()
    hasher = hashlib.sha256()
    hasher.update(data['ip'].encode('utf-8'))
    masked_ip = hasher.hexdigest()

# App version in the destination Database is int, extracting the Major version number
app_version = data['app_version'].split('.')[0]

'''Loading the data into the PostgresSQL Database"
connect to the localstack Postgres service running on second docker image on port 5432'''
connection = psycopg2.connect(host='localhost', port='5432', user='postgres', password='password', dbname='postgres')
cur = connection.cursor()
# Create table as per the provided schema of the target table.
cur.execute(
    """
  CREATE TABLE IF NOT EXISTS user_logins(
    user_id varchar(128),
    device_type varchar(32),
    masked_ip varchar(256),
    masked_device_id varchar(256),
    locale varchar(32),
    app_version integer,
    create_date date
  );
  """
)
# Insert the data into the user_logins table created in previous step
cur.execute(
    "INSERT INTO user_logins (user_id, device_type, masked_ip, masked_device_id, locale, app_version, create_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
    (data['user_id'], data['device_type'], masked_ip, masked_device_id, data['locale'], int(app_version),
     datetime.now()))

# Committing changes to db
connection.commit()
# Closing connection to save resources
connection.close()
