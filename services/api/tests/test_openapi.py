from api.main import app


def test_openapi_exposes_expected_contract() -> None:
    spec = app.openapi()
    assert "/api/v1/tools" in spec["paths"]
    assert "/api/v1/sentiment/{tool}" in spec["paths"]
    schemas = spec["components"]["schemas"]
    assert {"Tool", "SentimentSeries", "SentimentPoint"} <= set(schemas)
