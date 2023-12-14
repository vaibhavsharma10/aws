import sys
import traceback
import logging
import json
import uuid
import boto3
import time
import os
import openai

from urllib.parse import unquote_plus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

api_key = os.getenv('OPENAI_API_KEY')
openai.api_key = api_key

prepend_text = "in the following text with delimiter ~~~, \
give the list of adverse event in the text"

model ="text-davinci-002"


def process_error() -> dict:
    ex_type, ex_value, ex_traceback = sys.exc_info()
    traceback_string = traceback.format_exception(ex_type, ex_value, ex_traceback)
    error_msg = json.dumps(
        {
            "errorType": ex_type.__name__,
            "errorMessage": str(ex_value),
            "stackTrace": traceback_string,
        }
    )
    return error_msg


def extract_text(response: dict, extract_by="LINE"):
    text = []
    #for block in response["Blocks"]:
    #    if block["BlockType"] == extract_by:
    #        text.append(block["Text"])
    for resultPage in response:
        for item in resultPage["Blocks"]:
            if item["BlockType"] == extract_by:
                text.append(item["Text"])
    return text

def startJob(s3BucketName, objectName):
    response = None
    client = boto3.client('textract')
    response = client.start_document_text_detection(
    DocumentLocation={
        'S3Object': {
            'Bucket': s3BucketName,
            'Name': objectName
        }
    })
    return response["JobId"]
def isJobComplete(jobId):
    # For production use cases, use SNS based notification 
    # Details at: https://docs.aws.amazon.com/textract/latest/dg/api-async.html
    time.sleep(5)
    client = boto3.client('textract')
    response = client.get_document_text_detection(JobId=jobId)
    status = response["JobStatus"]
    #print("Job status: {}".format(status))
    while(status == "IN_PROGRESS"):
        time.sleep(5)
        response = client.get_document_text_detection(JobId=jobId)
        status = response["JobStatus"]
        print("Job status: {}".format(status))
    return status
def getJobResults(jobId):
    pages = []
    client = boto3.client('textract')
    response = client.get_document_text_detection(JobId=jobId)
    pages.append(response)
    #print("Resultset page recieved: {}".format(****(pages)))
    nextToken = None
    if('NextToken' in response):
        nextToken = response['NextToken']
    while(nextToken):
        response = client.get_document_text_detection(JobId=jobId, NextToken=nextToken)
        pages.append(response)
        #print("Resultset page recieved: {}".format(****(pages)))
        nextToken = None
        if('NextToken' in response):
            nextToken = response['NextToken']
    return pages
# Document

def lambda_handler(event, context):
    textract = boto3.client("textract")
    s3 = boto3.client("s3")

    try:
        if "Records" in event:
            file_obj = event["Records"][0]
            bucketname = str(file_obj["s3"]["bucket"]["name"])
            filename = unquote_plus(str(file_obj["s3"]["object"]["key"]))

            logging.info(f"Bucket: {bucketname} ::: Key: {filename}")
            jobId = startJob(bucketname, filename)
            #print("Started job with id: {}".format(jobId))
            if(isJobComplete(jobId)):
                response = getJobResults(jobId)
            # change LINE by WORD if you want word level extraction
            logging.info(response)
            raw_text = extract_text(response, extract_by="LINE")
            logging.info(raw_text)
            listToStr = ' '.join([str(elem) for elem in raw_text])
            prompt = prepend_text + "~~~"+listToStr+"~~~"
            logging.info("CALLING OPEN IA API---------------")
            response = openai.Completion.create(
                engine=model,
                prompt=prompt,
                n=1,
                temperature=1,
                max_tokens=100
            )
            logging.info("Response OPEN IA API---------------"+str(response))
            generated_text = ''
            for idx, option in enumerate(response.choices):
                generated_text += option.text.strip()
            
            s3.put_object(
                Bucket=bucketname,
                Key=f"output/{filename.split('/')[-1]}_{uuid.uuid4().hex}.txt",
                Body=str("".join(generated_text)),
                #Body=str(generated_text),
            )
            
            return {
                "statusCode": 200,
                "body": json.dumps("Document processed successfully!"),
            }
    except:
        error_msg = process_error()
        logger.error(error_msg)

    return {"statusCode": 500, "body": json.dumps("Error processing the document!")}
