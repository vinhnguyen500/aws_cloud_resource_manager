import boto3, json
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """
    
    params = ['email_sender', 'email', 'subj', 'heading', 'html_message', 
              'text_message', 'region']
    missing = []
    for i in range(len(params)):
        if params[i] not in event:
            missing.add(params[i])
    
    if missing:
        err = "Missing these parameters: " + str(missing)
        print(err)
        return {
            "statusCode": 500,
            "body": json.dumps(err)
        }
    send_email(event['email_sender'], event['email'], event['subj'], event['heading'],
               event['html_message'], event['text_message'], event['region'])
        
    return {
        "statusCode": 200,
        "body": json.dumps('Sent email')
    }


def send_email(email_sender, email, subj, heading, html_message, text_message, region):
    """
    # Sends an HTML based email to recipients about terminations
    :param email: recipient email
    :param subj: subject of the email
    :param heading: The heading of the email, appears in a banner at the top
    :param html_message: The body of the email
    :param text_message: text form of the body
    :return: N/A
    """

    SENDER = email_sender
    RECIPIENT = email
    SUBJECT = subj

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = text_message
                
    # The HTML body of the email.
    BODY_HTML = html_message

    # The character encoding for the email.
    CHARSET = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses',region_name=region)

    # Try to send the email.
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Html': {
                        'Charset': CHARSET,
                        'Data': BODY_HTML,
                    },
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])