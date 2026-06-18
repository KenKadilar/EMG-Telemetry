# Lambda behind API Gateway: return the most recent EMG activity readings from DynamoDB as JSON.
import json
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

table = boto3.resource('dynamodb').Table('emgCloudReadings')


def decimalToNumber(value):
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError


def lambda_handler(event, context):
    response = table.query(
        KeyConditionExpression=Key('device').eq('emg-edge-gateway'),
        ScanIndexForward=False,
        Limit=300
    )
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(response['Items'], default=decimalToNumber)
    }
