"""Local dashboard boundaries and public catalog behavior."""
from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from atlas.config import load_config
from atlas.web.server import Dashboard, handler_for


def test_catalog_is_live_okx_inventory_and_cached(tmp_path, monkeypatch):
    config = load_config(tmp_path)
    calls = []

    class FakeAPI:
        def call(self, path, params):
            calls.append((path, params))
            return ([
                {'instId': 'BTC-USDT', 'baseCcy': 'BTC', 'quoteCcy': 'USDT', 'state': 'live'},
                {'instId': 'BTC-USD_UM-261030', 'baseCcy': 'BTC', 'state': 'live'},
                {'instId': 'ETH-USDT', 'baseCcy': 'ETH', 'quoteCcy': 'USDT', 'state': 'suspend'},
                {'instId': 'invalid/injection', 'state': 'live'},
            ], {'cached': False})

    class FakeService:
        def __init__(self, config): self.api = FakeAPI()
        def close(self): pass

    monkeypatch.setattr('atlas.web.server.DataService', FakeService)
    app = Dashboard(config)
    first = app.instruments('SPOT')
    assert first['count'] == 3
    assert [row['id'] for row in first['instruments']] == ['BTC-USDT', 'BTC-USD_UM-261030', 'ETH-USDT']
    assert app.instruments('SPOT') == first
    assert calls == [('/api/v5/public/instruments', {'instType': 'SPOT'})]
    assert app.verify_selection('BTC-USDT')['state'] == 'live'
    try:
        app.verify_selection('ETH-USDT')
    except ValueError as exc:
        assert 'not live' in str(exc)
    else:
        raise AssertionError('Suspended instrument was accepted')


def test_http_requires_local_host_token_and_same_origin(tmp_path):
    app = Dashboard(load_config(tmp_path))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(app))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'

    def request(path, *, token=False, origin=None, body=None, host=None):
        headers = {'Host': host or f'127.0.0.1:{server.server_port}'}
        if token: headers['X-ATLAS-Token'] = app.token
        if origin: headers['Origin'] = origin
        if body is not None: headers['Content-Type'] = 'application/json'
        req = Request(base + path, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
        try:
            with urlopen(req, timeout=3) as response:
                return response.status, response.read()
        except HTTPError as exc:
            return exc.code, exc.read()

    try:
        assert request('/')[0] == 200
        assert request('/api/bootstrap')[0] == 403
        assert request('/api/bootstrap', token=True)[0] == 200
        assert request('/api/bootstrap', token=True, host='evil.example')[0] == 403
        assert request('/api/profile', token=True, origin='http://evil.example', body={})[0] == 403
        assert request('/api/profile', token=True, origin=base, body={
            'language': 'zh', 'capital_usdt': 300, 'markets': ['BTC-USDT', 'ETH-USDT'],
            'no_open_positions': True,
        })[0] == 200
        assert (tmp_path / 'ui-journal.jsonl').is_file()
        assert json.loads((tmp_path / 'config.json').read_text())['capital_usdt'] == 300
        assert request('/api/audience', token=True, origin=base, body={'trader_level':'experienced'})[0] == 200
        assert json.loads((tmp_path / 'config.json').read_text())['trader_level'] == 'experienced'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
