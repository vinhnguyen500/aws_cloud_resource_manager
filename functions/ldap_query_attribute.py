import json, ldap

def lambda_handler(event, context):
    """
    # Handler that triggers upon an event hooked up to Lambda
    :param event: event data in the form of a dict
    :param context: runtime information of type LambdaContext
    :return: codes indicating success or failure
    """

    attributes = getAttributes(event['domain'], event['base_dname'], event['bind_dname'],
        event['password'], event['obj_name'], event['obj_class'], event['attributes'])
    
    print(attributes)
    return {
        "statusCode": 200,
        "body": json.dumps(attributes),
    }

def getAttributes(domain, base_dname, bind_dname, password, obj_name, obj_class, attributes):
    """
    # queries ldap to search for the users with the specified attributes
    :param domain: the domain to search in
    :param base_dname: the base to search under, all children will be searched under this base
    :param bind_dname: the username of the service account
    :param password: password of the service account
    :param obj_name: object name to search for. EX) nt_id
    :param obj_class: class of the object
    :param attributes: list of attributes to look for EX) ["Mail"]
    :return: error codes are returned
    """

    l = ldap.initialize('ldaps://' + domain + ':636')
    binddn = bind_dname
    pw = password
    basedn = base_dname
    searchFilter = "(&(name=" + obj_name + ")(objectClass=" + obj_class + "))"
    searchAttribute = attributes

    #this will scope the entire subtree under base_dname
    searchScope = ldap.SCOPE_SUBTREE

    #Bind to the server
    try:
        l.protocol_version = ldap.VERSION3
        l.simple_bind_s(binddn, pw)

    except ldap.INVALID_CREDENTIALS:
        return { 
            "statusCode": 500,
            "body" : "Your username or password is incorrect."
        }

    except ldap.LDAPError as e:
        if type(e.message) == dict and e.message.has_key('desc'):
            print(e.message['desc'])
        else:
            return {
                "statusCode": 500, 
                "body": str(e)
            }
    try:
        ldap_result_id = l.search(basedn, searchScope, searchFilter, searchAttribute)
        result_set = []
        while 1:
            result_type, result_data = l.result(ldap_result_id, 0)
            if (result_data == []):
                raise ValueError("No results found")
            else:
                ## if you are expecting multiple results you can append them
                ## otherwise you can just wait until the initial result and break out
                if result_type == ldap.RES_SEARCH_ENTRY:
                    result_set.append(result_data)
            return result_set
            # result_set[0][0][1]['attribute'][0] to get attribute of only one result
    except ldap.LDAPError as e:
        return {
            "statusCode": 500,
            "body": str(e)
        }
    l.unbind_s()
    return None

