from api.main import app


def test_openapi_exposes_expected_contract() -> None:
    spec = app.openapi()
    assert "/api/v1/tools" in spec["paths"]
    assert "/api/v1/sentiment/{tool}" in spec["paths"]
    schemas = spec["components"]["schemas"]
    assert {"Tool", "SentimentSeries", "SentimentPoint"} <= set(schemas)
    # The unknown-tool 404 is part of the published contract (Phase 3 client).
    sentiment_responses = spec["paths"]["/api/v1/sentiment/{tool}"]["get"]["responses"]
    assert "404" in sentiment_responses


def test_openapi_marks_endpoints_public_and_bounds_arrays() -> None:
    spec = app.openapi()
    # Both data endpoints are intentionally public (no auth) — stated explicitly.
    assert spec["paths"]["/api/v1/tools"]["get"]["security"] == []
    assert spec["paths"]["/api/v1/sentiment/{tool}"]["get"]["security"] == []
    # Array responses carry advisory maxItems caps.
    schemas = spec["components"]["schemas"]
    assert schemas["Tool"]["properties"]["aliases"]["maxItems"] == 100
    assert schemas["SentimentSeries"]["properties"]["series"]["maxItems"] == 10_000
    tools_array = spec["paths"]["/api/v1/tools"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert tools_array["maxItems"] == 1_000
