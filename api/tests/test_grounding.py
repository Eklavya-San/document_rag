class JudgeYes:
    async def chat(self, messages):
        return "yes"


class JudgeNo:
    async def chat(self, messages):
        return "no"


async def test_grounded_true_when_judge_says_yes():
    from app.rag.grounding import check_grounding
    from app.rag.retriever import Source

    sources = [
        Source(
            text="calibrate the sensor",
            doc_id=1,
            filename="m.pdf",
            page=3,
            score=0.9,
            chunk_id="c",
        )
    ]
    assert await check_grounding("calibrate the sensor", sources, JudgeYes()) is True


async def test_grounded_false_when_judge_says_no():
    from app.rag.grounding import check_grounding
    from app.rag.retriever import Source

    sources = [
        Source(
            text="calibrate the sensor",
            doc_id=1,
            filename="m.pdf",
            page=3,
            score=0.9,
            chunk_id="c",
        )
    ]
    assert await check_grounding("the sky is blue", sources, JudgeNo()) is False
