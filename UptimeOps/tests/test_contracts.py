from uptimeops.contracts import inspect_contract


def test_json_keys_and_arrays():
    sample = {'status': 'ok', 'data': [{'ready': True, 'latency': 18}]}
    assert inspect_contract(sample, 'status', 'equals', 'ok') is None
    assert inspect_contract(sample, 'data.0.ready', 'equals', 'true') is None
    assert inspect_contract(sample, 'data.0.latency', 'lte', '20') is None
    assert inspect_contract(sample, 'data.0.latency', 'gte', '20')
    assert inspect_contract(sample, 'data.0.missing', 'exists', '') == 'Missing JSON field: data.0.missing'
    assert inspect_contract(sample, 'status', 'not_equals', 'down') is None
    assert inspect_contract(sample, 'status', 'equals', 'down')


def test_numeric_assertion_rejects_booleans_and_invalid_input():
    assert inspect_contract({'ready': True}, 'ready', 'gte', '1') == 'ready is not numeric'
    assert inspect_contract({'ready': 'yes'}, 'ready', 'gte', '10')


def test_empty_path_returns_missing_field():
    assert inspect_contract({}, 'x', 'equals', 'y')
