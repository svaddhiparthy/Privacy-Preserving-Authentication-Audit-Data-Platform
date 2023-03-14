# SecureLog: A Secure and Efficient Data Logging and Analysis System
## Overview
SecureLog is a secure and efficient data logging and analysis system that extracts data from an SQS service, transforms it to preserve uniqueness and privacy, and loads it into a PostgreSQL database table as per the provided schema. The app version is extracted and converted to an integer as per the destination database requirements. The final result is the creation of a user_logins table with the data from the SQS queue.

## Documentation
Read messages from the queue
The Boto3 library and the sqs.receive_message() method are used to read messages from the queue.

### Data structures used
The system uses a combination of dictionaries and lists to store and manipulate the data.

### Masking of PII data for duplicate values identification
To mask the PII data, a one-way hashing function such as SHA-256 is used. This creates a unique hash for each value while still allowing duplicate values to be identified by comparing their corresponding hashes.

### Connecting and writing to Postgres
The psycopg2 library is used to connect to Postgres and write data to the appropriate table. The psycopg2.connect() method is used to connect to the Postgres database, and the psycopg2.cursor() and cursor.execute() methods are used to write the data to the appropriate table.

### Running the application
The system can be run as a script on a local machine or containerized environment like Docker. It requires access to the internet and the correct credentials to connect to the AWS SQS and Postgres.

### Steps
Extracting the data from SQS
The system connects to the local stack SQS service and receives messages from the SQS queue running on the Docker image on port 4566. The messages are then parsed as JSON data and stored in a variable.

### Transforming the data
The data is transformed by masking the device_id and IP fields, using hashing, and converting the app version to an integer to suit the data type listed in the DDL statement provided. The app version is assumed to follow semantic versioning convention major.minor.patch structure.

### Loading the data into PostgreSQL
The system connects to the local stack Postgres service running on the second Docker image on port 5432. The system creates a table in the PostgreSQL database (if it doesn't exist) with the provided schema and then inserts the transformed data into the table.

### Future Scope
Deployment
To deploy this application in production, a cloud-based infrastructure such as AWS or GCP can be used. Additionally, a CI/CD pipeline can be set up to automatically build and deploy new versions of the application as they become available.

### Components to make this production-ready
Proper error handling and logging should be implemented to track any issues that occur. A backup and recovery plan should also be implemented.

### Application scaling
A distributed database like Amazon Aurora or Google Spanner can be used for storing the data. A load balancer can be used to distribute incoming traffic across multiple instances of the application, and auto-scaling can be used to automatically add or remove instances of the application based on the load.

### Recovering PII
Recovering PII (personally identifiable information) later would depend on the transformation technique used. Hashing is irreversible, but cryptography-based masking is reversible.

## Assumptions
The system is running on a local machine and Python 3.
The user has the necessary access credentials to connect to the SQS and PostgreSQL services.
The data is JSON formatted and follows a specific structure.
The version numbering follows version numbering semantics, and hence it is important to preserve the major version and drop the two other digits.
