# AWS Resource Auto Tagging

These python scripts are used in AWS Lambda to autotag resources and are run everyday at 12 AM PST. There are two modes that it operates in: audit and enforce. Audit mode runs the scripts as it normally would, except no changes are actually made. Enforce on the other hand runs the scripts and tags resources. An email and slack message is sent to resource owners if any tags are missing or invalid.

Specific steps that it takes:

* Queries for Owning_Mail, Owning_Team, and Patch Group in EC2 Instances
* If Owning_Mail or Owning_Team is missing, an email and slack message is sent to the resource owner
* If the Patch Group tag is invalid or missing a default one is created for it.
    * an invalid tag is one that does not match this format: {environment}-{platform}-{role}-{urgency}-{order}
* All resources are auto-tagged with an expiration date and its creator ID

## Getting Started

These instructions will provide setup examples and usage

### Supported Platforms

Amazon Web Services

### Prerequisites
* SQS with events hooked up to systems manager for ec2 launches
* AWS Lambda with cloudwatch event
    * cron(0 7 * * ? *)
* IAM role that provides the following permissions for Lambda function:
    * describe_{ resource }
    * describe_tags
    * Add tags 
    * Invoke_lambda
    * SQS receive message
    * SystemsManager DescribeInstanceInformation
* The following Lambda functions
    * dev-png-slack-message
    * dev-png-send-email
    * dev-png-notify-snitch
    * dev-png-ldap-query-attribute
    * dev-png-format-message
    
### Usage

Setup:
* Create a function in Lambda and link it to the IAM role with the correct permissions
* Input the following parameters into the environment variables

Required parameters 

```
mode : audit
environment : prd, dev, tst, stg
order : first, second, last
platform : ubutu, rhel, win, amazon, centos
role : security
urgency : critical
formatted_email : dev-png-format-message
slack_message : dev-png-slack-message
query_ldap : dev-png-ldap-query-attribute
notify_snitch : dev-png-notify-snitch
sender_email : CloudResourceJanitor@t-mobile.com
slack_application_url : slack_hook.com
slack_channel : testing-handler
slack_channel_id : "CD3R2NYBZ"
sqs_url : sqs_url.com
```

Optional parameters

```
mode : enforce
```

## Built With

* [Python](https://www.python.org/) - Scripting
* Snitch


## Versioning

We use [Bitbucket](https://bitbucket.org/) for versioning

## Authors

* **Vinh Nguyen**