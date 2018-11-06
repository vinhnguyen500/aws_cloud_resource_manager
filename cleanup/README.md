# AWS Resource Cleanup

These python scripts are used in AWS Lambda to cleanup expired resources and are run everyday at 1 AM PST. There are two modes that it operates in: audit and enforce. Audit mode runs the scripts as it normally would, except no changes are actually made and it just queries expired resources. Enforce on the other hand runs the scripts and terminates any expired items. An email is sent to resource owners a specified amount of days before expiration, and also when a resource is terminated.

Specific steps that it takes:

* Queries for expired resources in EC2 Instances, AMI Images, and Autoscaling Groups
* Resources that are expiring a specified amount of days before a given expiration date will be sent in an email to owners
* Resources that are expired are terminated and an email is sent to the owner
* Exceptions can be given in Lambda environment variables to skip over termination

## Getting Started

These instructions will provide setup examples and usage

### Supported Platforms

Amazon Web Services

### Prerequisites
* AWS Lambda with cloudwatch event
    * cron(0 8 * * ? *)
* IAM role that provides the following permissions for EC2 Instances, AMI images, and Autoscaling Groups:
    * describe_{ resource }
    * Termination of resources
    * describe_tags
    * update_auto_scaling_groups
* The following Lambda functions
    * dev-png-slack-message
    * dev-png-send-email
    * dev-png-notify-snitch
    * dev-png-ldap-query-attribute
    * dev-png-format-message
    
### Usage

Setup:
* Create a function in Lambda and link it to the IAM role with the correct permissions
* Input exceptions into the environment variables of Lambda

Required parameters 

```
mode : audit
fudge_factor : 5
formatted_email : dev-png-format-message
slack_message : dev-png-slack-message
notify_snitch : dev-png-notify-snitch
sender_email : example@email.com
slack_application_url : slack_hook.com
slack_channel : testing-handler
slack_channel_id : "CD3R2NYBZ"
```

Optional parameters

```
mode : enforce
fudge_factor : 10
except_asg_name : tower-web
except_image_id : ami-6740661f, ami-0fa406e143b1a360c, ami-0645e2d1662c3adf1
except_instance_id : i-0e2b9d5fb7dbcf494, i-0c49e4f5fa5e9aee2, i-0dfcd36cff05e7fcb
```

## Built With

* [Python](https://www.python.org/) - Scripting
* Snitch- Used for error logging


## Versioning

We use [Bitbucket](https://bitbucket.org/) 

## Authors

* **Vinh Nguyen**