def test_inventory_endpoint(client):
    response = client.get('/machine/inventory')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'ok'
    assert len(body['data']['items']) >= 1


def test_validation_error_shape(client):
    response = client.post('/transactions', json={'expected_amount': 0})
    assert response.status_code == 422
