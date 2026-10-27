"""HTTP tests that run the app against a real Postgres through the api_client fixture.

The evaluation corpus lives in the same tables, so every source indexed here gets a fresh id and
is removed again when its test ends, leaving the passages table exactly as it was found. The
request_log rows that each run's /retrieve and /answer calls write are kept, though: they stay
behind as ordinary traffic.
"""

import uuid

import pytest

TIMETABLE_TITLE = "Tarrowmere ferry timetable"
TIMETABLE_SENTENCES = (
    "The Tarrowmere ferry leaves Kelpie Quay for Ravensholm Island at 07:15 every weekday.",
    "Cars need a deck pass from the harbour kiosk, while bicycles cross for free.",
    "The crossing takes 35 minutes and the boat carries at most 18 cars.",
)
DEPARTURE_QUESTION = "What time does the Tarrowmere ferry leave Kelpie Quay for Ravensholm Island?"
CROSSING_QUERY = "ferry crossing time"
HARBOUR_TOKEN = "tide-table-42"

# Every keyword candidate, unreranked: a cheap, wide look at what is stored under an id.
KEYWORD_SWEEP = {"query": DEPARTURE_QUESTION, "mode": "keyword", "k": 50, "rerank": False}

# Stages each search mode times when reranking is on; switching it off drops "rerank".
STAGES_BY_MODE = {
    "hybrid": {"encode", "keyword", "semantic", "fusion", "rerank", "total"},
    "keyword": {"keyword", "rerank", "total"},
    "semantic": {"encode", "semantic", "rerank", "total"},
}


def fresh_id(label: str) -> str:
    """Return a source id that no other test, or concurrent test run, will use."""
    return f"{label}-{uuid.uuid4().hex[:12]}"


def timetable_payload(source_id: str, body: str | None = None) -> dict:
    """JSON for the ferry timetable as a single source, optionally with replacement text."""
    return {
        "id": source_id,
        "title": TIMETABLE_TITLE,
        "body": body or " ".join(TIMETABLE_SENTENCES),
    }


def source_ids(matches: list[dict]) -> list[str]:
    """The source id of every match in a /retrieve response, in rank order."""
    return [found["source_id"] for found in matches]


# Requests the token check must stop. Nothing should ever be stored under the probe id, but the
# test registers it for cleanup anyway in case the guard lets the index call through.
GUARD_PROBE_ID = fresh_id("ferry-probe")
GUARDED_CALLS = [
    pytest.param("POST", "/sources", {"sources": [timetable_payload(GUARD_PROBE_ID)]}, id="index"),
    pytest.param("DELETE", f"/sources/{GUARD_PROBE_ID}", None, id="remove"),
    pytest.param("POST", "/retrieve", {"query": CROSSING_QUERY}, id="retrieve"),
    pytest.param("POST", "/answer", {"question": DEPARTURE_QUESTION}, id="answer"),
]


@pytest.fixture
def remove_after(api_client):
    """Collect source ids during a test and delete their passages once it is over.

    Cleanup goes through the engine rather than DELETE /sources, so it works whatever token is
    configured and whatever characters the id contains.
    """
    pending: list[str] = []
    yield pending.append
    for source_id in pending:
        api_client.app.state.engine.remove(source_id)


@pytest.fixture
def ferry_source(api_client, remove_after) -> str:
    """Index the ferry timetable under a fresh id and give the test that id."""
    source_id = fresh_id("ferry")
    remove_after(source_id)
    response = api_client.post("/sources", json={"sources": [timetable_payload(source_id)]})
    assert response.status_code == 200
    assert response.json() == {"sources": 1, "passages": 1}
    return source_id


@pytest.fixture
def harbour_token(api_client, monkeypatch) -> str:
    """Switch on the X-API-Token check for one test and return the token it expects."""
    monkeypatch.setattr(api_client.app.state.engine.config, "api_token", HARBOUR_TOKEN)
    return HARBOUR_TOKEN


def test_healthcheck_reports_status_and_backend(api_client):
    """/healthz answers ok with a passage count and one of the known answer backends."""
    response = api_client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body.keys() == {"status", "passages", "backend"}
    assert body["status"] == "ok"
    assert body["backend"] in {"extractive", "anthropic"}


@pytest.mark.parametrize("rerank", [True, False], ids=["rerank", "no-rerank"])
@pytest.mark.parametrize("mode", ["hybrid", "keyword", "semantic"])
def test_retrieve_finds_new_source(api_client, ferry_source, mode, rerank):
    """A just-indexed timetable is found in every mode, and only the stages that ran are timed."""
    payload = {"query": DEPARTURE_QUESTION, "mode": mode, "rerank": rerank}
    response = api_client.post("/retrieve", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert ferry_source in source_ids(body["matches"])
    expected_stages = STAGES_BY_MODE[mode] if rerank else STAGES_BY_MODE[mode] - {"rerank"}
    assert body["timings_ms"].keys() == expected_stages


def test_retrieved_passage_keeps_title_and_sentences(api_client, ferry_source):
    """The stored passage returns under its title, one sentence per line, with scores best first."""
    response = api_client.post("/retrieve", json={"query": DEPARTURE_QUESTION})
    matches = response.json()["matches"]
    ours = [found for found in matches if found["source_id"] == ferry_source]
    assert len(ours) == 1
    assert ours[0]["title"] == TIMETABLE_TITLE
    assert ours[0]["body"].splitlines() == list(TIMETABLE_SENTENCES)
    scores = [found["score"] for found in matches]
    assert scores == sorted(scores, reverse=True)


def test_answer_cites_new_source(api_client, ferry_source):
    """/answer writes a reply that cites the timetable and reports how long composing took."""
    response = api_client.post("/answer", json={"question": DEPARTURE_QUESTION})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].strip()
    cited = {citation["source_id"]: citation for citation in body["citations"]}
    assert ferry_source in cited
    assert cited[ferry_source]["title"] == TIMETABLE_TITLE
    for citation in body["citations"]:
        assert f"[{citation['ref']}]" in body["answer"]
    assert body["usage"].keys() == {"input_tokens", "output_tokens"}
    assert {"compose", "total"} <= body["timings_ms"].keys()


def test_usage_counts_new_retrieval(api_client, ferry_source):
    """A reranked /retrieve is logged exactly once, and /usage summarises it with a rerank stage."""
    # Tagging the question with the fresh source id makes its request_log row this test's alone.
    query = f"{DEPARTURE_QUESTION} ({ferry_source})"
    payload = {"query": query, "rerank": True}
    assert api_client.post("/retrieve", json=payload).status_code == 200
    with api_client.app.state.engine.pool.connection() as conn:
        logged = conn.execute("SELECT route FROM request_log WHERE query = %s", (query,)).fetchall()
    assert logged == [("retrieve",)]
    report = api_client.get("/usage").json()
    assert report["hours"] == 24
    assert report["requests"] >= 1
    assert report["latency_ms"]["p50"] > 0
    assert "rerank" in report["stages"]
    assert "total" not in report["stages"]


@pytest.mark.parametrize("hours", [1, 720])
def test_usage_accepts_window_edges(api_client, hours):
    """The shortest and longest usage windows are accepted and echoed back."""
    response = api_client.get("/usage", params={"hours": hours})
    assert response.status_code == 200
    report = response.json()
    assert report.keys() == {"hours", "requests", "latency_ms", "stages", "cost_usd"}
    assert report["hours"] == hours


@pytest.mark.parametrize("hours", [0, 721])
def test_usage_rejects_window_out_of_range(api_client, hours):
    """A usage window outside 1 to 720 hours is refused with 422."""
    assert api_client.get("/usage", params={"hours": hours}).status_code == 422


def test_removed_source_disappears(api_client, ferry_source):
    """Deleting a source reports its one passage, a repeat delete is 404, and search drops it."""
    response = api_client.delete(f"/sources/{ferry_source}")
    assert response.status_code == 200
    assert response.json() == {"removed_passages": 1}
    assert api_client.delete(f"/sources/{ferry_source}").status_code == 404
    response = api_client.post("/retrieve", json=KEYWORD_SWEEP)
    assert ferry_source not in source_ids(response.json()["matches"])


def test_reindexing_replaces_old_passage(api_client, ferry_source):
    """Posting the same source id again swaps in the new text instead of adding a second copy."""
    revised = " ".join(TIMETABLE_SENTENCES).replace("07:15", "06:40")
    payload = {"sources": [timetable_payload(ferry_source, revised)]}
    assert api_client.post("/sources", json=payload).json() == {"sources": 1, "passages": 1}
    matches = api_client.post("/retrieve", json=KEYWORD_SWEEP).json()["matches"]
    bodies = [found["body"] for found in matches if found["source_id"] == ferry_source]
    assert len(bodies) == 1
    assert "06:40" in bodies[0]
    assert "07:15" not in bodies[0]
    assert api_client.delete(f"/sources/{ferry_source}").json() == {"removed_passages": 1}


def test_removing_unknown_source_is_404(api_client):
    """Deleting a source id that was never indexed answers 404."""
    assert api_client.delete(f"/sources/{fresh_id('ghost-ferry')}").status_code == 404


@pytest.mark.parametrize(
    "id_template",
    ["", "deck pass {}", "kelpie/quay-{}", "berth#{}", "{}" + "x" * 200],
    ids=["empty", "space", "slash", "hash", "too-long"],
)
def test_index_rejects_invalid_source_id(api_client, remove_after, id_template):
    """/sources answers 422 unless every id is 1 to 200 word characters, dots or dashes."""
    source_id = id_template.format(uuid.uuid4().hex[:12])
    remove_after(source_id)
    response = api_client.post("/sources", json={"sources": [timetable_payload(source_id)]})
    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        pytest.param("/sources", {"sources": []}, id="empty-source-list"),
        pytest.param("/retrieve", {"query": ""}, id="blank-query"),
        pytest.param("/retrieve", {"query": CROSSING_QUERY, "mode": "fuzzy"}, id="unknown-mode"),
        pytest.param("/retrieve", {"query": CROSSING_QUERY, "k": 0}, id="zero-k"),
        pytest.param("/answer", {"question": DEPARTURE_QUESTION, "k": 21}, id="answer-k-over-20"),
    ],
)
def test_malformed_body_is_422(api_client, path, payload):
    """A body that breaks the request schema, such as an empty source list, is refused with 422."""
    assert api_client.post(path, json=payload).status_code == 422


@pytest.mark.usefixtures("harbour_token")
@pytest.mark.parametrize(
    "headers", [{}, {"X-API-Token": "low-tide"}], ids=["no-token", "wrong-token"]
)
@pytest.mark.parametrize(("method", "path", "payload"), GUARDED_CALLS)
def test_guarded_route_refuses_bad_token(api_client, remove_after, method, path, payload, headers):
    """With a token configured, each POST and DELETE route answers 401 to a missing or wrong one."""
    remove_after(GUARD_PROBE_ID)
    response = api_client.request(method, path, json=payload, headers=headers)
    assert response.status_code == 401


def test_right_token_opens_retrieve_and_reads_stay_open(api_client, harbour_token):
    """Once a token is set, /retrieve needs the matching header while the GET routes stay open."""
    query = {"query": CROSSING_QUERY, "rerank": False}
    assert api_client.post("/retrieve", json=query).status_code == 401
    response = api_client.post("/retrieve", json=query, headers={"X-API-Token": harbour_token})
    assert response.status_code == 200
    assert api_client.get("/healthz").status_code == 200
    assert api_client.get("/usage").status_code == 200
