def test_cannot_select_before_payment(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    response = client.post(f'/transactions/{txid}/select', json={'product_id': 'A1'})
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'invalid_order'


def test_cannot_dispense_without_authorized_payment(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    response = client.post(f'/transactions/{txid}/dispense')
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'payment_not_authorized'
