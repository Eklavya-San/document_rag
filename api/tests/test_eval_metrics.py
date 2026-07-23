class Judge:
    def __init__(self, replies):
        self.replies = list(replies)
        self.i = 0

    async def chat(self, messages):
        r = self.replies[self.i]
        self.i += 1
        return r


async def test_context_precision_scores_relevant_top_source():
    from app.eval.metrics import context_precision

    sources = [
        {"filename": "m.pdf", "page": 3, "text": "calibrate the sensor", "score": 0.9}
    ]
    j = Judge(["yes"])
    p = await context_precision("how to calibrate?", sources, j.chat)
    assert p == 1.0


async def test_faithfulness_low_for_unsupported_answer():
    from app.eval.metrics import faithfulness

    sources = [{"text": "calibrate the sensor"}]
    j = Judge(["no"])
    f = await faithfulness("the sky is blue", sources, j.chat)
    assert f == 0.0
