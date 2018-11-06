import json, os, boto3, datetime, sys, pprint

# Global variable used to send emails and slack messages
SENDER_EMAIL = os.environ.get("sender_email")
APP_URL = os.environ.get("slack_application_url")
CHANNEL = os.environ.get("slack_channel")
CHANNEL_ID = os.environ.get("slack_channel_id")


def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """

    mode = os.environ.get("mode")
    if not mode:
        mode = "audit"

    print("Operating in " + mode + " mode")
        
    fudge_factor = int(os.environ.get("expiration_fudge_factor"))
    if not fudge_factor:
        fudge_factor = 5

    # If a server was to be deleted today, and fudge factor was 5, the server
    # will be deleted 5 days from today
    expiration_date = (datetime.date.today() - datetime.timedelta(days = fudge_factor)).strftime('%Y-%m-%d')

    expiring_emails = {}
    expired_emails = {}
    
    # search for expirations in auto scaling groups
    asgs = cleanup_asg(mode, expiration_date, expiring_emails, expired_emails)

    # search for expirations in ec2 instances
    ec2s = cleanup_ec2(mode, expiration_date, expiring_emails, expired_emails)

    # search for expirations in ec2 images
    amis = cleanup_ami(mode, expiration_date, expiring_emails, expired_emails)

    print(string_dict("expiring resource emails", expiring_emails))
    print(string_dict("expired resource emails", expired_emails))

    if asgs or ec2s or amis:
        msg = {
            "expired_resources": {
                "asgs" : asgs,
                "ec2s" : ec2s,
                "amis" : amis,
            },
            "expiring_resources_email_recipients" : expiring_emails,
            "expired_resources_email_recipients" : expired_emails
        }
        snitch_ret_val = None
        if mode == "enforce":
            snitch_ret_val = notify_snitch("enforce_aws_cleanup", "clear resources", "info", msg)
        else:
            snitch_ret_val = notify_snitch("audit_aws_cleanup", "clear resources", "info", msg)
            
        if snitch_ret_val:
            return snitch_ret_val

    lambda_client = boto3.client('lambda')
    for email in expiring_emails.keys():
        nt_ids = expiring_emails[email]['nt_ids']
        expiring_emails[email].pop('nt_ids')
        
        # send email to resource owner about expired resources
        messages = create_messages(string_dict("Applications", expiring_emails[email]), "is about to be deleted", "in " + str(fudge_factor) + " days")
        email_ret_val = send_email(email, messages, "Expiring Application in AWS", "Warning: Your Application is about to be terminated!")
        if email_ret_val:
            return email_ret_val

        # send slack message to resource owner about expired resources
        slack_ret_val = send_slack(messages[1].rsplit("\n",6)[0], nt_ids)
        if slack_ret_val:
            return slack_ret_val

    for email in expired_emails.keys():
        nt_ids = expired_emails[email]['nt_ids']
        expired_emails[email].pop('nt_ids')

        # send email to resource owner about expiring resources
        messages = create_messages(string_dict("Applications", expired_emails[email]), "was terminated", "today")
        email_ret_val = send_email(email, messages, "Expired Resources in AWS", "Alert: Your resources have been terminated")
        if email_ret_val:
            return email_ret_val
        

        # send slack message to resource owner about expiring resources
        slack_ret_val = send_slack(messages[1].rsplit("\n", 6)[0], nt_ids)
        if slack_ret_val:
            return slack_ret_val

    return {
        "statusCode": 200,
        "body": json.dumps('Successful')
    }


def cleanup_asg(mode, expiration_date, expiring_emails, expired_emails):
    """
    # clears expired autoscaling groups by setting capicity to zero
    :param mode: runs in either audit mode or enforce mode
    :param expiration_date: expiration date for expired resources
    :param expiring_emails: contains recipients for expiring resources
    :param expired_emails: contains recipients for expired resources
    :return expired_asgs: returns asgs that have expired
    """

    exceptions = os.environ.get("except_asg_name")

    client = boto3.client('autoscaling')
    paginator = client.get_paginator('describe_auto_scaling_groups')
    page_iterator = paginator.paginate(
        PaginationConfig={'PageSize': 100}
    )

    # Get the emails for resources that expire fudge days before today
    response = page_iterator.search(
        'AutoScalingGroups[] | [?contains(Tags[].Key, `Expiration`)]'.format(
            'Expiration', '*'))

    expired_asgs = []
    add_to_list(expired_asgs, expired_emails, expiring_emails, expiration_date, response, "AutoScalingGroupName", exceptions)

    object_print("clearing out asgs: ", expired_asgs)

    # Clear out the ASGs that expire today    
    if mode == "enforce" and expired_asgs:
        for asg in expired_asgs:
            try:
                date = datetime.datetime.strptime(expiration_date, '%Y-%m-%d') + datetime.timedelta(days = 30)
                client.update_auto_scaling_group(
                    AutoScalingGroupName=asg,
                    MinSize=0,
                    DesiredCapacity=0
                )
                client.create_or_update_tags(
                    Tags=[
                        {
                            'Key': 'Expiration',
                            'ResourceId': asg,
                            'ResourceType': 'auto-scaling-group',
                            'Value': date.strftime('%Y-%m-%d'),
                            'PropagateAtLaunch': True
                        },
                    ],
                )
            except Exception as e:
                asgs = pprint.pformat(expired_asgs)
                print("An error occured while updating desired auto scaling group size to zero for: " + asgs)
                print(str(e))
                snitch_ret_val = notify_snitch("cleanup_asg", "clear auto scaling group data", "error", str(e))
                if snitch_ret_val:
                    print("Error notifying snitch!")
                    return snitch_ret_val
                    
                sys.exit()            

    return expired_asgs


def cleanup_ec2(mode, expiration_date, expiring_emails, expired_emails):
    """
    # terminates expired instances
    :param mode: runs in either audit mode or enforce mode
    :param expiration_date: expiration date for expired resources
    :param expiring_emails: contains recipients for expiring resources
    :param expired_emails: contains recipients for expired resources
    :return expired_ec2s: returns instances that have expired
    """

    ec2client = boto3.client('ec2')
    exceptions = os.environ.get("except_instance_id")

    response = query_resources(ec2client, 'instances')
    expired_instances = []  
    for reservation in (response["Reservations"]):
        add_to_list(expired_instances, expired_emails, expiring_emails, expiration_date, reservation["Instances"], "InstanceId", exceptions)

    object_print("terminating instances: ", expired_instances)

    if mode == "enforce" and expired_instances:
        for instance in expired_instances:
            try: 
                ec2client.terminate_instances(InstanceIds=expired_instances)
            except Exception as e:
                ec2s = pprint.pformat(expired_instances)
                print("An error occured while terminating the following instances: " + ec2s)
                print(str(e))
                snitch_ret_val = notify_snitch("cleanup_ec2", "terminate instances", "error", str(e))
                if snitch_ret_val:
                    print("Error notifying Snitch!")
                    return snitch_ret_val
                    
                sys.exit()

    return expired_instances


def cleanup_ami(mode, expiration_date, expiring_emails, expired_emails):
    """
    # terminates expired images
    :param mode: runs in either audit mode or enforce mode
    :param expiration_date: expiration date for expired resources
    :param expiring_emails: contains recipients for expiring resources
    :param expired_emails: contains recipients for expired resources
    :return expired_amis: returns images that have expired
    """

    client = boto3.client('ec2')
    exceptions = os.environ.get("except_image_id")

    response = query_resources(client, 'images')
    expired_images = []
    add_to_list(expired_images, expired_emails, expiring_emails, expiration_date, response["Images"], "ImageId", exceptions)

    object_print("terminating images: ", expired_images)

    if mode == "enforce" and expired_images:
        for image in expired_images:
            try:
                data = client.deregister_image(ImageId=image)
            except Exception as e:
                amis = pprint.pformat(expired_images)
                print( "An error occured while terminating the following images: " + amis)
                print(str(e))
                ret_val = notify_snitch("cleanup_ami", "terminate images", "error", str(e))
                sys.exit()

    return expired_images


def query_resources(client, resource_type):
    """
    # Helper method for cleanup_ec2 and cleanup_ami. Searches for tags that have an expiration date
    :param client: Boto3 client for each resource
    :param resource_type: type of resource to describe
    :return reponse: returns the response from the client after describing it
    """

    return getattr(client, ('describe_' + resource_type))(
        Filters=[
            {
                'Name': 'tag:Expiration',
                'Values': ['*']
            }
        ]
    )


def add_to_list(resource_list, expired_emails, expiring_emails, expiration_date, response, attribute, exceptions):
    """
    # Adds resources to a list, appends emails to corresponding list (if it's expired or expiring)
    :param resource_list:
    :param expiring_emails: contains recipients for expiring resources
    :param expired_emails: contains recipients for expired resources
    :param expiration_date: expiration date for expired resources
    :param response: the reponse from the client after describing
    :param attribute: the attribute to identify an individual resource
    :param exceptions: exceptions of resources to avoid
    :return: N/A
    """

    for item in response:
        if item[attribute] not in exceptions:
            expired = False
            for pair in item['Tags']:
                if pair["Key"] == "Expiration":
                    date = datetime.datetime.strptime(pair["Value"], "%Y-%m-%d")
                    expired_date = datetime.datetime.strptime(expiration_date, "%Y-%m-%d")
                    if date.date() == datetime.date.today():
                        add_to_emails(expiring_emails, item)

                    if date.date() <= expired_date.date():
                        expired = True
                        break

            if expired:
                resource_list.append(item[attribute])
                add_to_emails(expired_emails, item)
             

def add_to_emails(emails, item):
    """
    # Adds emails to the dictionary along with its resources
    :param emails: dictionary of emails to add to
    :param item: the resource's dict structure
    :return: N/A
    """

    email = ""
    stack = ""
    role = ""
    nt_id = ""
    for pair in item["Tags"]:
        if pair["Key"] == "Owning_Mail":
            email = pair["Value"]
        if pair["Key"] == "Stack":
            stack = pair["Value"]
        if pair["Key"] == "Role":
            role = pair["Value"]
        if pair["Key"] == "Creator_ID":
            nt_id = pair["Value"]

    if email in emails:
        if stack in emails[email]:
            if (role not in emails[email][stack]):
                emails[email][stack].append(role)
        else:
            emails[email][stack] = [role]

        if nt_id not in emails[email]['nt_ids']:
            emails[email]['nt_ids'].append(nt_id)
    else:
        emails[email] = {stack : [role],
                         'nt_ids': [nt_id]}



def object_print(message, structure):
    """
    # Prints a data structure
    :param message: prints a message first
    :param structure: the data structure to print
    :return: N/A
    """

    print(message, end='')
    pprint.pprint(structure)


def string_dict(obj_name, given_dct):
    """
    # Converts given dct (body) to a pretty formatted string.
    # Resulting string used for file writing.
    :param obj_name: (str) name of the dict
    :param given_dict: dict to convert to a string
    :return: string converted dict
    """

    string = pprint.pformat(given_dct, width=1)[1:]

    new_str = ''
    for num, line in enumerate(string.split('\n')):
        if num == 0:
            # (pprint module always inserts one less whitespace for first line)
            # (indent=1 is default, giving everything one extra whitespace)
            new_str += ' '*4 + line + '\n'
        else:
            new_str += ' '*3 + line + '\n'

    return obj_name + ' = {\n' + new_str
    

def create_messages(application, action, fudge_factor):
    """
    # Creates a preformatted message depending on expiration
    :param application: name of the application
    :param action: What is being done to the application
    :param fudge_factor: In how many days is it happening
    :return: String containing the message
    """
    messages = [] 
    messages.append("""Your Application: </br><pre style="margin-left: 40px">""" + application + "</pre></br>" + action + """ in AWS <strong style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;">""" + fudge_factor + """</strong>
                                    </td>
                                </tr><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="content-block" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0; padding: 0 0 20px;" valign="top">
                                        This message was sent to inform you of changes happening to your resources.
                                        <ul>
                                            <li>Applications are flagged with an expiration of about 30 days for security and environment hygiene reasons.
                                            <li>The resources will be terminated if no action is taken.</li>
                                            <li>You will get an additional email when a resource has been terminated.</li>
                                            <li>If you need to extend the expiration, you can reply to this email. Otherwise, no further action is required
                                        </ul>
                                        If you have any further questions regarding why your resource is being deleted, please reply to this email.""")
    
    messages.append("Your Application:\n\n""" + application + "\n" + action + " in AWS " + fudge_factor + "\n" + 
                    ("\nThis message was sent to inform you of changes happening to your resources.\n"
                    "\nApplications are flagged with an expiration of about 30 days for security and environment hygiene reasons."
                    "The resources will be terminated if no action is taken.\n"
                    "\nIf you need to extend the expiration, or if you have any questions regarding why your resource is being deleted, you can reply to this message. Otherwise, no further action is required"))  

    return messages                     


def notify_snitch(comp_name, action, level, msg):
    """
    # notifies snitch through the lambda function notify_snitch
    :param comp_name: component name
    :param action: action being done
    :param level: the level of urgency
    :param msg: message to send to snitch
    :return: any errors from lambda invoke
    """
    lambda_client = boto3.client('lambda')
    data = {
        'comp_name': comp_name, 
        'action':action, 
        'level': level, 
        'msg': msg
    }          
    invoke_response = lambda_client.invoke(
        FunctionName= os.environ.get("notify_snitch"),
        InvocationType= "RequestResponse",
        Payload= json.dumps(data)
    )
    return checkError(invoke_response, "Error notifying snitch!")


def send_email(email, messages, subj, heading):
    """
    # sends an email through the lambda function send_email
    :param email: email recipient
    :param messages: list containing an html version and text version of message
    :param subj: subject line
    :param heading: heading line
    :return: any errors from lambda invoke
    """
    lambda_client = boto3.client('lambda')
    email_data = {
        'sender_mail': SENDER_EMAIL,
        'email': email,
        'subj': subj,
        'heading': heading,
        'messages': messages, 
        'region': os.environ.get("AWS_DEFAULT_REGION")
    }
    invoke_email_response = lambda_client.invoke(
        FunctionName= os.environ.get("formatted_email"),
        InvocationType= "RequestResponse",
        Payload= json.dumps(email_data)
    )
    return checkError(invoke_email_response, "Error sending email!")
    

def send_slack(message, nt_ids):
    """
    # sends a slack message through the slack lambda function
    :param message: message to send to slack
    :param nt_ids: list containing nt_ids
    :return: any errors from lambda invoke
    """
    lambda_client = boto3.client('lambda')
    slack_data = {
            'application_url': APP_URL,
            'channel': CHANNEL,
            'message': message,
            'channel_id': CHANNEL_ID
        }
    if nt_ids:
        slack_data['nt_ids'] = nt_ids

    invoke_slack_response = lambda_client.invoke(
        FunctionName= os.environ.get("slack_message"),
        InvocationType= "RequestResponse",
        Payload= json.dumps(slack_data)
    )
    return checkError(invoke_slack_response, "Error notifying snitch!")


def checkError(invoke_response, message):
    """
    # checks for errors in lambda functions from invoke
    :param invoke_response: response from invoke_lambda
    :param message: message to print if error
    :return: errors from the response message, None if no errors
    """
    if 'FunctionError' in invoke_response:
       err_message = invoke_response['Payload'].read()
       print(message)
       print(err_message)
       return {
           'statusCode': 500,
           'body': json.dumps(str(err_message))
       }
    return None    