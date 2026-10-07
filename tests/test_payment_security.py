import time

from app.security.hmac_signing import build_payload, sign_message


def test_tampered_message_rejected(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    nonce = 'nonce-x'
    issued_at = int(time.time())
    payload = build_payload(txid, '1.50', nonce, issued_at)
    signature = sign_message('wrong-secret', payload)

    response = client.post(f'/transactions/{txid}/payment', json={
        'amount': '1.50', 'nonce': nonce, 'issued_at': issued_at, 'signature': signature
    })
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'invalid_signature'
