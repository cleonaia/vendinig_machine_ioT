def test_audit_has_required_fields(client):
    client.post('/transactions', json={'expected_amount': '1.50'})
    events = client.get('/audit').json()['data']['events']
    assert events
    event = events[0]
    for key in ['timestamp', 'transaction_id', 'event_type', 'actor', 'status', 'reason', 'metadata']:
        assert key in event
