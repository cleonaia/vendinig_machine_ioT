import time

from app.security.hmac_signing import build_payload, sign_message


def test_normal_transaction_flow(client):
    create = client.post('/transactions', json={'expected_amount': '1.50'})
    tx = create.json()['data']['transaction']
    txid = tx['transaction_id']

    nonce = 'nonce-1'
    issued_at = int(time.time())
    payload = build_payload(txid, '1.50', nonce, issued_at)
    signature = sign_message('change-me-local-only', payload)

    pay = client.post(f'/transactions/{txid}/payment', json={
        'amount': '1.50', 'nonce': nonce, 'issued_at': issued_at, 'signature': signature
    })
    assert pay.status_code == 200

    selected = client.post(f'/transactions/{txid}/select', json={'product_id': 'A1'})
    assert selected.status_code == 200

    dispense = client.post(f'/transactions/{txid}/dispense')
    assert dispense.status_code == 200
    assert dispense.json()['data']['transaction']['state'] == 'COMPLETED'
