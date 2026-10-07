import time

from app.security.hmac_signing import build_payload, sign_message


def _auth(client, txid: str, amount: str = '1.50'):
    nonce = f'nonce-{txid}'
    issued_at = int(time.time())
    payload = build_payload(txid, amount, nonce, issued_at)
    signature = sign_message('change-me-local-only', payload)
    return client.post(f'/transactions/{txid}/payment', json={
        'amount': amount, 'nonce': nonce, 'issued_at': issued_at, 'signature': signature
    })


def test_nonexistent_product_rejected(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    _auth(client, txid)
    response = client.post(f'/transactions/{txid}/select', json={'product_id': 'X99'})
    assert response.status_code == 404


def test_out_of_stock_rejected(client):
    txid = client.post('/transactions', json={'expected_amount': '2.20'}).json()['data']['transaction']['transaction_id']
    _auth(client, txid, amount='2.20')
    client.post(f'/transactions/{txid}/select', json={'product_id': 'B2'})

    app = client.app
    item = app.state.repository.get_inventory_item('B2')
    item.stock = 0
    app.state.repository.save_inventory_item(item)

    response = client.post(f'/transactions/{txid}/dispense')
    assert response.status_code == 409
