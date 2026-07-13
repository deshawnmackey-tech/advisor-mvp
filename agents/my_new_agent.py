class MyNewAgent:
    def __init__(self, client_id: str, user_message: str):
        self.client_id = client_id
        self.user_message = user_message

    async def run(self) -> dict:
        return {
            "snapshot": {
                "client_id": self.client_id,
                "message": self.user_message,
            },
            "actions": [],
            "disclaimer": "This is educational guidance, not financial advice.",
        }
