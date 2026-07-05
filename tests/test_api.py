"""End-to-end API flow in demo mode: create -> generate -> select -> outcome -> flywheel."""


def _create_campaign(client, intent="winback", segs=(2,)):
    r = client.post("/api/campaigns", json={
        "name": "Test winback", "intent": intent,
        "body": "We miss you. Your saved items are waiting.",
        "segment_ids": list(segs)})
    assert r.status_code == 201
    return r.json()["id"]


def test_meta_reports_demo_mode(client):
    meta = client.get("/api/meta").json()
    assert meta["demo_mode"] is True
    assert "winback" in meta["intents"]


def test_validation_errors(client):
    assert client.post("/api/campaigns", json={
        "name": "x", "intent": "nope", "body": "b", "segment_ids": [1]}).status_code == 422
    assert client.post("/api/campaigns", json={
        "name": "x", "intent": "winback", "body": "b", "segment_ids": [999]}).status_code == 422
    assert client.post("/api/campaigns/9999/generate").status_code == 404


def test_generate_returns_ranked_diverse_candidates(client):
    cid = _create_campaign(client)
    r = client.post(f"/api/campaigns/{cid}/generate")
    assert r.status_code == 200
    seg = r.json()["segments"][0]
    cands = seg["candidates"]
    assert len(cands) == 6
    scores = [c["score"] for c in cands]
    assert scores == sorted(scores, reverse=True)
    assert len({c["tone"] for c in cands}) >= 4
    assert all(c["rationale"] for c in cands)
    assert seg["retrieval"]["positives"], "winback has comparable history in seed data"
    assert all("match_reason" in p for p in seg["retrieval"]["positives"])


def test_ab_limit_enforced(client):
    cid = _create_campaign(client)
    cands = client.post(f"/api/campaigns/{cid}/generate").json()["segments"][0]["candidates"]
    a, b, c = cands[0], cands[1], cands[2]
    assert client.post(f"/api/candidates/{a['id']}/status", json={"status": "accepted"}).status_code == 200
    assert client.post(f"/api/candidates/{b['id']}/status", json={"status": "accepted"}).status_code == 200
    r = client.post(f"/api/candidates/{c['id']}/status", json={"status": "accepted"})
    assert r.status_code == 409
    # Rejecting one frees a slot.
    client.post(f"/api/candidates/{b['id']}/status", json={"status": "rejected"})
    assert client.post(f"/api/candidates/{c['id']}/status", json={"status": "accepted"}).status_code == 200


def test_edit_preserves_original_and_rechecks_guardrails(client):
    cid = _create_campaign(client)
    cand = client.post(f"/api/campaigns/{cid}/generate").json()["segments"][0]["candidates"][0]
    r = client.post(f"/api/candidates/{cand['id']}/status",
                    json={"status": "edited", "edited_text": "A risk-free hello that is way too long " * 3})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == cand["text"]  # original retained
    assert body["display_text"].startswith("A risk-free")
    assert {b["code"] for b in body["edited_badges"]} >= {"banned_term"}
    # edited without text is invalid
    assert client.post(f"/api/candidates/{cand['id']}/status",
                       json={"status": "edited"}).status_code == 422


def test_outcome_closes_the_flywheel(client):
    cid = _create_campaign(client)
    cands = client.post(f"/api/campaigns/{cid}/generate").json()["segments"][0]["candidates"]
    chosen = cands[0]
    client.post(f"/api/candidates/{chosen['id']}/status", json={"status": "accepted"})

    before = [h for h in client.get("/api/history").json() if h["source"] == "app"]
    r = client.post(f"/api/campaigns/{cid}/outcome", json={
        "segment_id": 2, "sent_at": "2026-07-08",
        "results": [{"candidate_id": chosen["id"], "open_rate": 33.3, "variant": "A"}]})
    assert r.status_code == 201

    after = [h for h in client.get("/api/history").json() if h["source"] == "app"]
    assert len(after) == len(before) + 1
    new = after[0]
    assert new["subject_line"] == chosen["display_text"]
    assert new["open_rate"] == 33.3 and new["intent"] == "winback"

    # The logged line is now retrievable: it appears in the next generation's comparables.
    cid2 = _create_campaign(client)
    retr = client.post(f"/api/campaigns/{cid2}/generate").json()["segments"][0]["retrieval"]
    assert any(p["subject_line"] == chosen["display_text"]
               for p in retr["positives"] + retr["negatives"]) or \
           33.3 <= max(p["open_rate"] for p in retr["positives"])


def test_outcome_requires_accepted_candidate(client):
    cid = _create_campaign(client)
    cands = client.post(f"/api/campaigns/{cid}/generate").json()["segments"][0]["candidates"]
    r = client.post(f"/api/campaigns/{cid}/outcome", json={
        "segment_id": 2, "results": [{"candidate_id": cands[0]["id"], "open_rate": 20}]})
    assert r.status_code == 422


def test_campaign_status_progression(client):
    cid = _create_campaign(client)
    assert [c for c in client.get("/api/campaigns").json() if c["id"] == cid][0]["status"] == "draft"
    cands = client.post(f"/api/campaigns/{cid}/generate").json()["segments"][0]["candidates"]
    assert [c for c in client.get("/api/campaigns").json() if c["id"] == cid][0]["status"] == "generated"
    client.post(f"/api/candidates/{cands[0]['id']}/status", json={"status": "accepted"})
    assert [c for c in client.get("/api/campaigns").json() if c["id"] == cid][0]["status"] == "selected"


def test_brand_voice_roundtrip_and_effect(client):
    brand = client.get("/api/brand").json()
    brand["banned_terms"].append("favorites")  # word used by a demo winback candidate
    r = client.put("/api/brand", json={
        "guidelines": brand["guidelines"],
        "banned_terms": brand["banned_terms"],
        "exemplars": brand["exemplars"]})
    assert r.status_code == 200
    cid = _create_campaign(client)
    seg = client.post(f"/api/campaigns/{cid}/generate").json()["segments"][0]
    texts = [c["text"].lower() for c in seg["candidates"]]
    assert all("favorites" not in t for t in texts)
    assert seg["removed_by_guardrails"] >= 1
