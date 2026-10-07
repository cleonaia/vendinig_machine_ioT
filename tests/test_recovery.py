def test_timeout_cancels_transaction(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    response = client.post(f'/transactions/{txid}/timeout')
    assert response.status_code == 200
    assert response.json()['data']['transaction']['state'] == 'CANCELLED'


def test_restart_active_tx_to_error(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    response = client.post(f'/transactions/{txid}/restart')
    assert response.status_code == 200
    assert response.json()['data']['transaction']['state'] == 'ERROR'
