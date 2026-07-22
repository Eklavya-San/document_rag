class OllamaClient:
    def __init__(self, settings):
        self.settings = settings

    async def ping(self) -> bool:
        return False  # replaced in Task 6
