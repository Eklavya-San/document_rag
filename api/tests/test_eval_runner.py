import json
from pathlib import Path


async def test_run_eval_collects_answers_and_sources(tmp_path):
    from app.eval.runner import run_eval, load_qa, QaItem

    qa = [
        {
            "id": "q1",
            "question": "how to calibrate?",
            "expected_answer": "calibrate the sensor",
            "expected_doc": "m.pdf",
            "expected_page": 3,
            "tags": ["procedure"],
        }
    ]
    p = tmp_path / "qa.json"
    p.write_text(json.dumps(qa))

    async def pipeline(question):
        return (
            "calibrate the sensor",
            [
                {
                    "filename": "m.pdf",
                    "page": 3,
                    "text": "calibrate the sensor",
                    "score": 0.9,
                    "chunk_id": "c1",
                }
            ],
        )

    results = await run_eval(pipeline, load_qa(str(p)), judge=None)
    assert len(results) == 1
    assert results[0]["answer"] == "calibrate the sensor"
    assert results[0]["sources"][0]["filename"] == "m.pdf"
