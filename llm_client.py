import requests
import logging
import sys

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, api_token: str, model: str = "gpt-4o-mini"):
        self.api_token = api_token
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def call(self, prompt: str, max_tokens: int = 150) -> str:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        response = requests.post(self.api_url, headers=headers, json=data)

        if response.status_code != 200:
            logger.error(f"Received status code {response.status_code} from OpenAI API: {response.text}")
            sys.exit(1)

        response_data = response.json()
        return response_data['choices'][0]['message']['content'].strip()

    def call_batch(self, prompts: list, max_tokens: int = 150) -> list:
        headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

        # Prepare a list of messages for each prompt
        messages = [{"role": "user", "content": prompt} for prompt in prompts]

        # The OpenAI API does not support batch processing directly, so we send them as individual requests.
        # In production, you might want to handle these in parallel or in a more optimized way.
        responses = []
        for message in messages:
            data = {
                "model": self.model,
                "messages": [message],
                "max_tokens": max_tokens,
            }
            response = requests.post(self.api_url, headers=headers, json=data)

            if response.status_code != 200:
                logger.error(f"Received status code {response.status_code} from OpenAI API: {response.text}")
                sys.exit(1)

            response_data = response.json()
            responses.append(response_data['choices'][0]['message']['content'].strip())

        return responses
