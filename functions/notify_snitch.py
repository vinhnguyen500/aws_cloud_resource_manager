from botocore.vendored import requests
import json, datetime, boto3, os

SENDER_EMAIL = os.environ.get("sender_email")
EMAIL_RECIPIENT = os.environ.get("email_recipient")
APP_URL = os.environ.get("slack_application_url")
CHANNEL = os.environ.get("slack_channel")


def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """

    params = ['comp_name', 'action', 'level', 'msg']
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
    notify_snitch(event['comp_name'], event['action'], event['level'], event['msg'])
    
    return {
        "statusCode": 200,
        "body": json.dumps('Notified snitch')
    }


def notify_snitch(comp_name, action, level, msg):
    """
    # Notifies snitch about an event through a POST
    :param comp_name: Component name to identify origin
    :param action: Action the component is performing
    :param level: Severity of event
    :param msg: Message that will be sent to Splunk
    :return: returns any errors
    """

    headers = json.loads(os.environ.get("headers"))
    epoch = int(datetime.datetime.now().strftime('%s'))
    data = {
        "source": "aws_lamba",
        "time": epoch,
        "event": {
            "log_level": level,
            "action": action,
            "time": epoch,
            "application_name": "aws_cleanup",
            "message": msg,
            "component_name": comp_name
        }
    }
    try:
        json_data = json.dumps(data)
        response = str(requests.post(os.environ.get("snitch_endpoint"), headers=headers, data=json_data, verify=False))[1:-1]

        if response != 'Response [200]':
            raise ConnectionError("Error code: " + response)
    except Exception as e:
        messages = []
        messages.append("""The AWS Lambda function: dev-png-aws-manage was unable to communicate with Snitch; <strong style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;">""" + str(e) + """</strong>
									</td>
								</tr><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="content-block" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0; padding: 0 0 20px;" valign="top">
										This email was sent to alert you that Snitch requests are not working.
                                        <ul>
                                            <li>Without Snitch, any logging or monitoring is down and we cannot view events</li>
                                        </ul>
                                       """ + json_data)
        messages.append("The AWS Lambda function, dev-png-aws-manage was unable to communicate with Snitch; " + str(e) + "\n This message was sent to alert you that Snitch requests are not working. Without Snitch any logging or monitoring is down and we cannot view events.")
        
        lambda_client = boto3.client('lambda')
        email_data = {
            'sender_mail': SENDER_EMAIL,
            'email': EMAIL_RECIPIENT,
            'subj': "Snitch error",
            'heading': "Alert: Could not send message to Snitch!",
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
            return err
        
        slack_data = {
            'application_url': APP_URL,
            'channel': CHANNEL,
            'message': messages[1]
        }
        invoke_slack_response = lambda_client.invoke(
            FunctionName= os.environ.get("slack_message"),
            InvocationType= "RequestResponse",
            Payload= json.dumps(slack_data)
        )
        err = checkError(invoke_slack_response, "Error sending slack message!")
        if err:
            return err


def checkError(invoke_response, message):
    if 'FunctionError' in invoke_response:
       err_message = invoke_response['Payload'].read()
       print(message)
       print(err_message)
       return {
           'statusCode': 500,
           'body': json.dumps(str(err_message))
       }
    return None    