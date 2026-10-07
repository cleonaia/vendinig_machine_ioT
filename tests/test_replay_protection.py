import time

from app.security.hmac_signing import build_payload, sign_message


def test_replay_rejected(client):
    txid = client.post('/transactions', json={'expected_amount': '1.50'}).json()['data']['transaction']['transaction_id']
    nonce = 'nonce-replay'
    issued_at = int(time.time())
    payload = build_payload(txid, '1.50', nonce, issued_at)
    signature = sign_message('change-me-local-only', payload)

    first = client.post(f'/transactions/{txid}/payment', json={
        'amount': '1.50', 'nonce': nonce, 'issued_at': issued_at, 'signature': signature
    })
    assert first.status_code == 200

    second = client.post(f'/transactions/{txid}/payment', json={
        'amount': '1.50', 'nonce': nonce, 'issued_at': issued_at, 'signature': signature
    })
    assert second.status_code == 409
    assert second.json()['error']['code'] in {'replay_detected', 'invalid_state'}
