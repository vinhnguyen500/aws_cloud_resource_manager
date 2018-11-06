# AWS Build Application

These scripts are utilized by AWS Lambda to manage resources in AWS. All resources are autotagged with necessary information including the Owner_ID and an expiration date. Users are notified of expiring resources through their email and username associated with the Owner_ID found through LDAP authentication. Expired resources are terminated if no further action is taken.

* Autotags resources in AWS
* Sends notifications through slack and email if expiring soon
* Terminates and clears out any expired resources

## Getting Started

Within the subdirectories auto-tag and cleanup are instructions on how to setup the resource manager in AWS Lambda. NOTICE: Each lambda function has environment variables that need to be defined.

### Supported Platforms

Amazon Web Services
* Red Hat Enterprise Linux 7
* Windows Server 2012

### Supported Resources
* EC2 Instances
* EC2 Images (AMI)
* AWS Autoscalers

### Prerequisites

Software needed: 

* AWS Lambda
* Python 2/3

## Built With

* Python
* Snitch (Internal logging software)


## Versioning

We use [Bitbucket](https://bitbucket.org/) for versioning

## Authors

* **Vinh Nguyen**


