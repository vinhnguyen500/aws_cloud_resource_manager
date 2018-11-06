import json, boto3, os

def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """

    params = ['sender_mail', 'email', 'subj', 'heading', 'messages', 'region']
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
    ret_val = send_preformatted_email_message(event['sender_mail'], event['email'], event['subj'], 
                                    event['heading'], event['messages'], event['region'])
    
    if ret_val:
        return ret_val
        
    return {
        "statusCode": 200,
        "body": json.dumps('Formatted message')
    }


# Method used for sending pre-formatted alert messages
def send_preformatted_email_message(sender_mail, email, subj, heading, messages, region):
    """
    # sends a preformatted email message
    :param sender_mail: the email of the sender
    :param email: the email of the recipient
    :param subj: subject line of the email
    :param heading: heading line of the email
    :param messages: list of strings containing the html version and text version
    :param region: region of the SES service to send
    :return: error codes or None if successful
    """

    message = create_email_message(subj, heading, messages[0])
    data = {
        'email_sender': sender_mail,
        'email': email,
        'subj': subj,
        'heading': heading,
        'html_message': message,
        'text_message': messages[1], 
        'region': region
    }
    lambda_client = boto3.client('lambda')
    invoke_response = lambda_client.invoke(
        FunctionName= os.environ.get("send_email"),
        InvocationType= "RequestResponse",
        Payload= json.dumps(data)
    )
    if 'FunctionError' in invoke_response:
       err_message = invoke_response['Payload'].read()
       print("Error sending formatted message!")
       print(err_message)
       return {
           'statusCode': 500,
           'body': json.dumps(str(err_message))
       }
    return None    
    

# Private helper method for preformatted alert messages
def create_email_message(subj, heading, message):
    """
    # creates the formatted message
    :param subj: subject of the email
    :param heading: heading of the email
    :param message: message to send
    :return: the formatted message
    """
    
    return """<html xmlns="http://www.w3.org/1999/xhtml" style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;">
                            <head>
                                <meta name="viewport" content="width=device-width" />
                                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                                <title> """ + subj + """ </title>


                                <style type="text/css">
                                    img {
                                        max-width: 100%;
                                    }
                                    body {
                                        -webkit-font-smoothing: antialiased; -webkit-text-size-adjust: none; width: 100% !important; height: 100%; line-height: 1.6em;
                                    }
                                    body {
                                        background-color: #f6f6f6;
                                    }
                                    @media only screen and (max-width: 640px) {
                                    body {
                                        padding: 0 !important;
                                    }
                                    h1 {
                                        font-weight: 800 !important; margin: 20px 0 5px !important;
                                    }
                                    h2 {
                                        font-weight: 800 !important; margin: 20px 0 5px !important;
                                    }
                                    h3 {
                                        font-weight: 800 !important; margin: 20px 0 5px !important;
                                    }
                                    h4 {
                                        font-weight: 800 !important; margin: 20px 0 5px !important;
                                    }
                                    h1 {
                                        font-size: 22px !important;
                                    }
                                    h2 {
                                        font-size: 18px !important;
                                    }
                                    h3 {
                                        font-size: 16px !important;
                                    }
                                    .container {
                                        padding: 0 !important; width: 100% !important;
                                    }
                                    .content {
                                        padding: 0 !important;
                                    }
                                    .content-wrap {
                                        padding: 10px !important;
                                    }
                                    .invoice {
                                        width: 100% !important;
                                    }
                                    }
                                </style>
                            </head>

                            <body itemscope itemtype="http://schema.org/EmailMessage" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; -webkit-font-smoothing: antialiased; -webkit-text-size-adjust: none; width: 100% !important; height: 100%; line-height: 1.6em; background-color: #f6f6f6; margin: 0;" bgcolor="#f6f6f6">

                            <table class="body-wrap" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; width: 100%; background-color: #f6f6f6; margin: 0;" bgcolor="#f6f6f6"><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0;" valign="top"></td>
                                    <td class="container" width="600" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; display: block !important; max-width: 600px !important; clear: both !important; margin: 0 auto;" valign="top">
                                        <div class="content" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; max-width: 600px; display: block; margin: 0 auto; padding: 20px;">
                                            <table class="main" width="100%" cellpadding="0" cellspacing="0" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; border-radius: 3px; background-color: #fff; margin: 0; border: 1px solid #e9e9e9;" bgcolor="#fff"><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="alert alert-warning" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 16px; vertical-align: top; color: #fff; font-weight: 500; text-align: center; border-radius: 3px 3px 0 0; background-color: #ff00ff; margin: 0; padding: 20px;" align="center" bgcolor="#ff00ff" valign="top" font-weight: "bold">
                                                        <b>""" + heading + """</b>
                                                    </td>
                                                </tr><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="content-wrap" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0; padding: 20px;" valign="top">
                                                        <table width="100%" cellpadding="0" cellspacing="0" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="content-block" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0; padding: 0 0 20px;" valign="top">
                                                                    """+ message + """
                                                                </td>
                                                            </tr></table></td>
                                                </tr></table><div class="footer" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; width: 100%; clear: both; color: #999; margin: 0; padding: 20px;">
                                                <table width="100%" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><tr style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; margin: 0;"><td class="aligncenter content-block" style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 12px; vertical-align: top; color: #999; text-align: center; margin: 0; padding: 0 0 20px;" align="center" valign="top">This is an automated messaged from the DTD Platform Engineering Team.</td>
                                                    </tr></table></div></div>
                                    </td>
                                    <td style="font-family: 'Helvetica Neue',Helvetica,Arial,sans-serif; box-sizing: border-box; font-size: 14px; vertical-align: top; margin: 0;" valign="top"></td>
                                </tr></table></body>
                            </html>
                                            """    