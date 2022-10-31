

def lambda_handler(event, context):
    emoji_type = event["emoji_type"]
    message = event["message"]
    
    print(emoji_type)
    print(message)
    
    custom_message = None

    if emoji_type == 0:
        custom_message = "Message for code 0: " + message

    elif emoji_type == 1:
        custom_message = "Message for code 1: " + message

    else:
        custom_message = "Message for all other codes: " + message       
    response = {
        "message": message,
        "custom_message": custom_message,
    }
    return response
