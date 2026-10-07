import time

from app.security.hmac_signing import build_payload, sign_message


def test_dispensing_interrupt_fail_secure(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']

    nonce = 'nonce-i'
    issued_at = int(time.time())
    payload = build_payload(txid, '1.50', nonce, issued_at)
    signature = sign_message('change-me-local-only', payload)

    client.post(f'/transactions/{txid}/payment', json={
        'amount': '1.50', 'nonce': nonce, 'issued_at': issued_at, 'signature': signature
    })
    client.post(f'/transactions/{txid}/select', json={'product_id': 'A1'})
    response = client.post(f'/transactions/{txid}/interrupt')
    assert response.status_code == 200
    assert response.json()['data']['transaction']['state'] == 'ERROR'
