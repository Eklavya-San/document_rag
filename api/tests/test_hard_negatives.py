from app.eval.hard_negatives import mine_hard_negatives


def test_flags_high_score_low_precision_chunks():
    results = [
        {
            "id": "q1",
            "question": "q",
            "answer": "a",
            "context_precision": 0.0,
            "sources": [
                {
                    "filename": "m.pdf",
                    "page": 9,
                    "text": "noise",
                    "score": 0.91,
                    "chunk_id": "c9",
                }
            ],
        },
        {
            "id": "q2",
            "question": "q",
            "answer": "a",
            "context_precision": 1.0,
            "sources": [
                {
                    "filename": "m.pdf",
                    "page": 3,
                    "text": "calibrate",
                    "score": 0.9,
                    "chunk_id": "c3",
                }
            ],
        },
    ]
    out = mine_hard_negatives(results, score_threshold=0.85)
    assert len(out) == 1
    assert out[0]["chunk_id"] == "c9"
