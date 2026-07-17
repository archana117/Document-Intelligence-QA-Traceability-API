import pytest
import os
import json

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Welcome" in response.json()["message"]

def test_document_ingestion_and_browse(client):
    # Determine absolute path to the v1 manual PDF in the workspace
    pdf_path = os.path.abspath("ct200_manual.pdf")
    
    # 1. Ingest document v1
    response = client.post(
        f"/api/documents/ingest?filepath={pdf_path}&version=1&document_name=CardioTrack-CT-200"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["version"] == 1
    assert data["total_nodes"] > 0
    doc_id = data["document_id"]

    # 2. Browse hierarchy
    response_browse = client.get(f"/api/documents/{doc_id}/browse")
    assert response_browse.status_code == 200
    tree_data = response_browse.json()
    assert tree_data["document_id"] == doc_id
    assert tree_data["version"] == 1
    assert len(tree_data["sections"]) > 0

def test_version_matching_and_staleness_detection(client):
    pdf_path_v1 = os.path.abspath("ct200_manual.pdf")
    pdf_path_v2 = os.path.abspath("ct200_manual_v2.pdf")

    # 1. Ingest Version 1
    resp1 = client.post(
        f"/api/documents/ingest?filepath={pdf_path_v1}&version=1&document_name=Test-Monitor"
    )
    assert resp1.status_code == 200
    doc_id_v1 = resp1.json()["document_id"]

    # 2. Search for the battery specification section in v1 to create selection
    search_resp = client.get(f"/api/documents/{doc_id_v1}/search?q=battery")
    assert search_resp.status_code == 200
    search_results = search_resp.json()
    assert len(search_results) > 0
    
    # Let's find the stable node ID for the battery life section.
    # In ct200_manual, there's "2.1.1.1 Battery Life Under Typical Use"
    battery_node_id = None
    for item in search_results:
        if "Battery Life" in item["heading"]:
            battery_node_id = item["node_id"]
            break
            
    if not battery_node_id:
        # Fallback to the first search match
        battery_node_id = search_results[0]["node_id"]

    # 3. Create a selection pinned to version 1
    selection_payload = {
        "name": "Test-Monitor",
        "document_id": doc_id_v1,
        "version": 1,
        "node_ids": [battery_node_id]
    }
    sel_resp = client.post("/api/selections", json=selection_payload)
    assert sel_resp.status_code == 200
    selection_id = sel_resp.json()["id"]

    # 4. Generate QA test cases for the selection
    gen_resp = client.post(f"/api/selections/{selection_id}/generate-qa")
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["is_stale"] is False
    assert len(gen_data["generations"]) == 1
    assert len(gen_data["generations"][0]["test_cases"]) > 0

    # 5. Ingest Version 2
    # This document reduces battery cycles estimation (300 -> 250 cycles) and shifts Low Battery from 15% -> 10%
    resp2 = client.post(
        f"/api/documents/ingest?filepath={pdf_path_v2}&version=2&document_name=Test-Monitor"
    )
    assert resp2.status_code == 200

    # 6. Retrieve selection QA status to check for staleness
    # The selection is pinned to v1. However, the system checks if the referenced node
    # in the LATEST version (v2) has a different content hash.
    # Because the battery text changed, the hash should differ, making the selection QA stale!
    status_resp = client.get(f"/api/selections/{selection_id}/qa-status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    
    # Assert selection is recognized as stale
    assert status_data["is_stale"] is True
    assert status_data["generations"][0]["is_stale"] is True

def test_version_diffing(client):
    pdf_path_v1 = os.path.abspath("ct200_manual.pdf")
    pdf_path_v2 = os.path.abspath("ct200_manual_v2.pdf")

    # Ingest both versions
    client.post(f"/api/documents/ingest?filepath={pdf_path_v1}&version=1&document_name=Diff-Test")
    client.post(f"/api/documents/ingest?filepath={pdf_path_v2}&version=2&document_name=Diff-Test")

    # Query diff for the battery life section which we know has changed
    # Stable node ID: "sec_2_1_1_1" for "2.1.1.1"
    response = client.get("/api/nodes/sec_2_1_1_1/diff?document_name=Diff-Test&v1=1&v2=2")
    assert response.status_code == 200
    diff_data = response.json()
    assert diff_data["node_id"] == "sec_2_1_1_1"
    assert diff_data["changed"] is True
    assert len(diff_data["diff_details"]) > 0
    # The diff should flag body change
    body_diff = [d for d in diff_data["diff_details"] if d["field"] == "body"]
    assert len(body_diff) == 1
    assert "300" in body_diff[0]["v1_value"]
    assert "250" in body_diff[0]["v2_value"]
