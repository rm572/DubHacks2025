import boto3
import json
import os
from dotenv import load_dotenv


load_dotenv()

bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID_BEDROCK"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY_BEDROCK")
)

def parse_ride_request(user_input: str):
    """
    Uses Amazon Bedrock to extract location info from a natural language request.
    """
    prompt = f"""
    You're a smart ride assistant helping students around the University of Washington campus.
    Extract locations from this casual ride request.
    Return a JSON object with one key: "location".
    If either location is missing or unclear, return null for that field.
    Request: "{user_input}"
    """

    response = bedrock.invoke_model(
        # modelId="anthropic.claude-haiku-4-5-20251001-v1:0",
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        # inferenceProfileArn="arn:aws:bedrock:us-west-2:501174417548:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0",
        contentType="application/json",
        accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 100
        })
    )

    chunks = []
    for event in response["body"]:
        # event is a bytes object, so decode it directly
        decoded = event.decode("utf-8")
        chunks.append(decoded)

    full_response = "".join(chunks)
    model_response = json.loads(full_response)

    # Claude models return the response under 'body', read it
    # model_response = json.loads(response["body"].read())
    text = model_response["content"][0]["text"]

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fallback if parsing fails
        return {"location": None}
