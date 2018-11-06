import json, boto3, datetime, os, base64, ast, sys
from botocore.exceptions import ClientError

# global variables used for email and slack
URL = os.environ.get("sqs_url")
SENDER_EMAIL = os.environ.get("sender_email")
APP_URL = os.environ.get("slack_application_url")
CHANNEL = os.environ.get("slack_channel")
CHANNEL_ID = os.environ.get("slack_channel_id")
MODE = ""


def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """
    MODE = os.environ.get('mode')
    if not MODE:
        MODE = 'audit'

    print("Operating in " + MODE + " mode")
    sqs_client = boto3.client('sqs')

    # keep looping until no more messages
    missingOwners = {}
    missingPatches = {}
    while True:
        sqs_response = sqs_client.receive_message(
            QueueUrl = URL,
            AttributeNames=['ApproximateNumberOfMessages'],
            MaxNumberOfMessages= 10,
            MessageAttributeNames=['instance-launch-info']
        )
        if 'Messages' in sqs_response:
            for message in sqs_response['Messages']:
                canDelete = False
                instance_detail = json.loads(message['Body'])['detail']
                nt_id = instance_detail['userIdentity']['principalId'].split(':')[1]
                if instance_detail['responseElements'] != None:
                    instances = instance_detail['responseElements']['instancesSet']['items']

                    for instance in instances:
                        instance_id = instance['instanceId']
                        ec2client = boto3.client("ec2")
                        response = ec2client.describe_instances(InstanceIds=[instance_id])

                        if response["Reservations"] and response["Reservations"][0]["Instances"]:
                            instValid, item1, item2 = checkTags(instance_id, 
                                    response["Reservations"][0]['Instances'][0]['Tags'], nt_id,)

                            if item1:
                                if nt_id in missingOwners:
                                    missingOwners[nt_id].append(item1)
                                else:
                                    missingOwners[nt_id] = [item1]
                            if item2:
                                if nt_id in missingPatches:
                                    missingPatches[nt_id].append(item2)
                                else:
                                    missingPatches[nt_id] = [item2]

                            canDelete = canDelete and instValid
                else:
                    canDelete = True
                if canDelete:
                    sqs_client.delete_message(
                        QueueUrl= URL,
                        ReceiptHandle= message['ReceiptHandle']
                    )
                    print("Deleted queue message")
        else:
            print("No more messages found in the queue")
            break

    for user in missingOwners:
            notify(user, str(missingOwners[user]), "is missing Owning_Mail or Owning_Team tags", 
                    "Please add these tags to your resources.", "Missing Owner Tags", "Alert: Missing Owner tags!")
    
    for user in missingPatches:
            notify(user, str(missingPatches[user]), "has an invalid Patch Group tag. These resources will receive the latest patches",
                    "If you do not need the latest patches, please fix these tags", "Invalid Patch Tags", "Error: Invalid patch tags!")        

    return {
        "statusCode": 200,
        "body": json.dumps('Tagged resources')
    }


def checkTags(instance_id, tagSet, nt_id):
    """
    # Checks for tags and adds them if they are not present
    """
    tags = []
    missingOwnersItem = ""
    missingPatchesItem = ""
    patch_name = ""
    isPatchTag = False
    isExpiration = False
    isCreatorID = False
    isOwnerMailTag = False
    isOwnerTeamTag = False
    for tag in tagSet:
        if tag['Key'] == 'Expiration':
            isExpiration = True

        if tag['Key'] == 'Creator ID':
            isCreatorID = True

        if tag['Key'] == 'Patch Group':
            isPatchTag = checkPatchValidity(tag['Value'])

        if tag['Key'] == 'Owning_Mail':
            isOwnerMailTag = True
        
        if tag['Key'] == 'Owning_Team':
            isOwnerTeamTag = True

    if not isExpiration:
        tags.append(
        {   
            'Key': 'Expiration',
            'Value': (datetime.date.today() + datetime.timedelta(days = 30)).strftime('%Y-%m-%d')
        })
    if not isCreatorID:
        tags.append(
        {
            'Key': 'Creator ID',
            'Value': nt_id
        })

    if not isOwnerTeamTag or not isOwnerMailTag:
        missingOwnersItem = instance_id

    if not isPatchTag:
        print("invalid patch tags!")
        missingPatchesItem = instance_id

        patch_name = createPatchTag(tags, instance_id, nt_id)
        tags.append({ 'Patch Group' :  patch_name })

    print("Attaching tags: " + str(tags) + " to instance " + instance_id)
    if MODE == 'enforce':
        attachInstanceTags(instance_id, tags)
    
    if MODE == "enforce" and patch_name != "Not yet populated" and isOwnerMailTag and isOwnerTeamTag:
        return True
    
    return False, missingOwnersItem, missingPatchesItem



def checkPatchValidity(val):
    """
    # checks if the PatchGroup tag is valid
    :param val: the tag to evaluate
    :return: boolean if valid or not
    """

    tag_list = val.split('-')
    if len(tag_list) < 5:
        return False

    if tag_list[0] not in os.environ.get('environment'):
        return False

    if tag_list[1] not in os.environ.get('platform'):
        return False

    if tag_list[2] not in os.environ.get('role'):
        return False 

    if tag_list[3] not in os.environ.get('urgency'):
        return False 

    if tag_list[4] not in os.environ.get('order'):
        return False

    return True 


def createPatchTag(tags, instance_id, nt_id):
    """
    # creates a patch tag based on platform, filler if platform not found
    :param tags: the list of tags to add to a resource
    :param instance_id: the id of the resource
    :param nt_id: the nt_id owner of a resource
    :return: The tag value
    """

    client = boto3.client('ssm')
    response = client.describe_instance_information(
        InstanceInformationFilterList=[
            {
                'key': 'InstanceIds',
                'valueSet': [instance_id]
            }
        ]
    )
    patch_tag_value = ''
    platform_name = ''
    if (response['InstanceInformationList']):
        platform_name = response['InstanceInformationList'][0]['PlatformName'] 
    if 'Red Hat Enterprise Linux' in platform_name:
        patch_tag_value = 'default-rhel'
    elif 'Windows' in platform_name:
        patch_tag_value = 'default-windows'
    elif 'Ubuntu' in platform_name:
        patch_tag_value = 'default-ubuntu'
    elif 'Centos' in platform_name:
        patch_tag_value = 'default-centos'
    elif 'Amazon Linux 2' in platform_name:
        patch_tag_value = 'default-amazon2'
    elif 'Amazon Linux' in platform_name:
        patch_tag_value = 'default-amazon'
    else:
        print("No patch group found for platform")
        patch_tag_value = 'Not yet populated'

    return patch_tag_value


def attachInstanceTags(instance_id, tags):
    """
    # attaches a list of tags to a resource
    :param instance_id: the id of the resource
    :param tags: list of tags to add
    :return: boolean value to indicate if the instance exists or not, true if not found!
    """
    
    empty = False
    lambda_client = boto3.client('lambda')
    data = {
        'comp_name': "attachInstanceTags", 
        'action': "attach tags", 
        'level': "info", 
        'msg': "attached " + str(tags) + " to instance " + instance_id
    }     
    try:
        client = boto3.client('ec2')
        response = client.create_tags(
            Resources=[instance_id],
            Tags= tags
        )
        print("Attached tags to instance")
    except ClientError as e:
        if e.response['Error']['Code'] == 'InvalidInstanceID.NotFound':
            print("No such instance exists")
            empty = True
        else:
            print("Error attaching tags to instance: " + str(e))
    
    if (not empty):
        invoke_response = lambda_client.invoke(
            FunctionName= os.environ.get("notify_snitch"),
            InvocationType= "RequestResponse",
            Payload= json.dumps(data)
        )


def create_messages(application, action, remedy):
    """
    # Creates a preformatted message depending on expiration
    :param application: name of the application
    :param action: What is being done to the application
    :param remedy: steps to take
    :return: String containing the message
    """

    messages = [] 
    messages.append("""Your Resources: </br><pre style="margin-left: 40px">""" + application + "</br></pre>" + action + """ in AWS. <strong style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;">""" + remedy +"""</strong>
                                    </td>
                                </tr><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="content-block" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0; padding: 0 0 20px;" valign="top">
                                        This message was sent to inform you of changes happening to your resources.
                                        <ul>
                                            <li>New instances are auto-tagged with an expiration date, an NT ID, and a patch group if invalid.</li>
                                            <li>Instances without the necessary tags are notified through email and Slack.</li>
                                        </ul>
                                        If you have any further questions, please reply to this email.""")
    
    messages.append("Your Resources:\n\n" + application + "\n\n" + action + " in AWS. " + remedy + "\n" + 
                    ("\nThis message was sent to inform you of changes happening to your resources.\n"
                    "\nNew instances are auto-tagged with an expiration date, an NT ID, and a patch group if invalid."
                    "Instances without Owner Mail and Owner Team tags are notified through email and slack.\n"
                    "\nIf you have any further questions, please reply to this email."))  

    return messages                     


def get_email(nt_id):
    """
    # Retrieves the email from an nt_id
    :param nt_id: the id to search through
    :return: email address or None if not found
    """

    secret = json.loads(get_secret())
    username = secret['account_name']
    pw = secret['password']
    data = {
                "domain": "corporate.t-mobile.com",
                "base_dname": "OU=Production,OU=Users,OU=Accounts,DC=Corporate,DC=T-Mobile,DC=com",
                "bind_dname": "CN=%s,OU=LDAPS,OU=Non-production,OU=Services,OU=Accounts,DC=corporate,DC=t-mobile,DC=com" % username,
                "password": pw,
                "obj_name": nt_id,
                "obj_class": "user",
                "attributes": ["mail"],
            }
    lambda_client = boto3.client('lambda')
    invoke_response = lambda_client.invoke(
        FunctionName= os.environ.get("query_ldap"),
        InvocationType= "RequestResponse",
        Payload= json.dumps(data)
    )
    if ("FunctionError" not in invoke_response):
        data = ast.literal_eval(json.load(invoke_response['Payload'])['body'])
        print(data)
        return data[0][0][1]['mail'][0]

    return None

def notify(nt_id, application, action, remedy, subj, heading):
    """
    # notifies an owner through email and slack
    :param nt_id: owner id to send to
    :param application: the resource affected
    :param action: the thing happening to the resource
    :param remedy: steps taken to remedy
    :param subj: subject line of the email
    :param heading: heading line of the email
    :return: N/A
    """

    email = get_email(nt_id)
    lambda_client = boto3.client('lambda')
    messages = create_messages(application, action, remedy)
    print(email)
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
    err = checkError(invoke_email_response, "Error sending email!")
    if err:
        print(str(err))

    slack_data = {
        'application_url': APP_URL,
        'channel': CHANNEL,
        'message': messages[1].rsplit("\n",5)[0],
        'channel_id': CHANNEL_ID,
        'nt_ids': [nt_id]
    }
    invoke_slack_response = lambda_client.invoke(
        FunctionName= os.environ.get("slack_message"),
        InvocationType= "RequestResponse",
        Payload= json.dumps(slack_data)
    )
    err = checkError(invoke_slack_response, "Error sending slack message!")
    if err:
        print(str(err))


def get_secret():
    """
    # gets the secret from AWS secrets manager
    :param N/A:
    :return: the secrets value or None if not found
    """

    secret_name = "Jido-Active-Directory-Service-Account"

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name= os.environ.get("AWS_DEFAULT_REGION")
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId= secret_name
        )
    except ClientError as e:
        print("Error getting secret key!: " + str(e))
        return None
    else:
        # Decrypts secret using the associated KMS CMK.
        if 'SecretString' in get_secret_value_response:
            return get_secret_value_response['SecretString']

    return None


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