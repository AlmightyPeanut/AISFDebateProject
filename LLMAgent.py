from openai import OpenAI


class LLMAgent:
    def __init__(self):
        api_keys = {}
        with open("SECRETS", "r") as f:
            for line in f.readlines():
                line = line.split("=")
                api_keys[line[0]] = line[1].rstrip()

        self.open_ai_client = OpenAI(
            api_key=api_keys["OPEN_AI_API_KEY"]
        )

    def get_response(self, messages: list[dict[str, str]]) -> str:
        response = self.open_ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        ).choices[0].message.content

        # response = "<thinking></thinking> <argument></argument>"

        return response
