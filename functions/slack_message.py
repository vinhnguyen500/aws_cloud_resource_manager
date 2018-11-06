from botocore.vendored import requests
import json, boto3, base64, ast, os

# Global variables used for slack channel access
ACCESS_TOKEN = os.environ.get("oauth_access_token")
TOKEN = os.environ.get("bot_user_oauth_access_token")
HEADERS = { 'Content-type' : 'application/x-www-form-urlencoded' }


def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """

    params = ['application_url', 'channel', 'message']
    missing = []
    for i in range(len(params)):
        if params[i] not in event:
            missing.append(params[i])
    if missing:
        err = "Missing these parameters: " + str(missing)
        print(err)
        
        return {
            "statusCode": 500,
            "body": json.dumps(err)
        }
        
    nt_ids = None
    if 'nt_ids' in event:
        nt_ids = event['nt_ids']

    message = event['message']
    slack_name = ""
    
    if nt_ids:
        for nt_id in nt_ids:
            if nt_id:
                slack_name += (tag_name(nt_id, event['application_url'], event['channel_id']) + ", ")
    
    print(slack_name)
    if slack_name:
        message = slack_name + "\n" + message

    message += "\n------------------------------------------"
    
    send_message(event['application_url'], event['channel'], message)
    
    return {
        "statusCode": 200,
        "body": json.dumps('Message sent')
    }


def tag_name(nt_id, url, channel):
    """
    # searches for a slack id through nt_id and invites them
    :param nt_id: the id of the user for slack
    :param url: the url of the slack application
    :param channel: the channel to invite users to
    :return: slack id
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
        email = data[0][0][1]['mail'][0]
        print("data returned from ldap query: "),
        print(data)
        print("email of nt_id: " + email)
        slack_id = get_user_id(email, HEADERS, TOKEN)
        if slack_id:
            invite_user(slack_id, channel)
            return "<@" + slack_id + ">"   

    return nt_id


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


def get_user_id(email, headers, token):
    """
    # gets the slack id from a given email
    :param email: email to search for
    :param headers: headers for the request 
    :param token: token for api access
    :return: the slack_id
    """

    payload = { 'token': token, 'email': email}
    response = requests.get('https://slack.com/api/users.lookupByEmail', headers=headers, params=payload)
    if response.ok:
        return response.json()['user']['id']
    
    return None


def checkMember(member_id, name, headers, token):
    """
    # checks if a member is the specified one
    :param member_id: the user id to check against
    :param name: name of the user to look for
    :param headers: headers for request
    :param token: token for api access
    :return: true if the member matches the name
    """

    payload = { 'token' : token, 'user' : member_id }
    response = requests.get('https://slack.com/api/users.info', headers=headers, params=payload)
    print (response.json()["user"]["name"])
    if response.json()["user"]["name"] == name:
        return True
    
    return False


def send_message(application_url, channel, message):
    """
    # sends the slack message
    :param application_url: the url of the application
    :param channel: the channel to send to
    :param message: the message to send
    :return: N/A
    """

    headers = {
        'Content-type': 'application/json',
    }
    data = '{"text": "%s"}' % message
    print("Sending slack message: " + data)
    response = requests.post(application_url, headers=headers, data=data)
    print(response.text)


def invite_user(slack_id, channel):
    """
    # invites a user to a channel
    :param slack_id: the id of the user to invite
    :param channel: the channel to invite to
    :return: N/A
    """
    data = {
        'token': ACCESS_TOKEN,
        'channel': channel,
        'user': slack_id
    }
    response = requests.post("https://slack.com/api/channels.invite", headers= HEADERS, data=data)
    print(response.text)