from openai import OpenAI

endpoint = "https://[openai-resource-name].openai.azure.com/openai/v1/"
model_name = "gpt-4o-mini"
deployment_name = "gpt-4o-mini"

api_key = "xxxxxxxx"

client = OpenAI(
    base_url=f"{endpoint}",
    api_key=api_key
)

completion = client.chat.completions.create(
    model=deployment_name,
    messages=[
        {
            "role": "user",
            "content": "대한민국의 수도는?",
        }
    ],
)

print(completion.choices[0].message)