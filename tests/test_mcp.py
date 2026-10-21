import asyncio
import time
from datetime import date
from unittest.mock import Mock

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from mcp.shared.memory import create_connected_server_and_client_session

from garmin_parse.mcp_server import OwnerTokenVerifier, create_server
from garmin_parse.query import QueryService
from garmin_parse.schema import normalize
from garmin_parse.storage import write_json


def save(directory, i=1):
    r = normalize({'summary': {'activityId': i, 'activityType': {'typeKey': 'running'}, 'startTimeLocal': '2026-09-01 08:00:00', 'distance': 5000, 'movingDuration': 1500}, 'detail': {}, 'splits': {}, 'hr_zones': []})
    write_json(directory / '2026' / f'2026-09-01_running_{i}.json', r.model_dump(mode='json'))


def test_mcp_protocol_all_tools_and_validation(tmp_path):
    save(tmp_path)
    save(tmp_path, 2)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    async def run():
        async with create_connected_server_and_client_session(create_server(tmp_path)) as client:
            listed = await client.list_tools()
            names = {t.name for t in listed.tools}
            assert names == {'list_activities', 'get_activity', 'get_training_summary', 'compare_training_periods', 'get_running_trends', 'get_data_freshness', 'get_activity_data'}
            assert all(t.annotations.readOnlyHint for t in listed.tools)
            assert all(t.outputSchema for t in listed.tools)
            for name, arguments in [
                ('list_activities', {'limit': 1, 'offset': 0}),
                ('get_activity', {'activity_id': '1'}),
                ('get_training_summary', {'start_date': '2026-09-01', 'end_date': '2026-09-02'}),
                ('compare_training_periods', {'period_a_start': '2026-08-01', 'period_a_end': '2026-08-31', 'period_b_start': '2026-09-01', 'period_b_end': '2026-09-30'}),
                ('get_running_trends', {'granularity': 'monthly'}),
                ('get_data_freshness', {}),
            ]:
                result = await client.call_tool(name, arguments)
                assert not result.isError, result
                assert result.structuredContent is not None
                if name == 'list_activities':
                    assert result.structuredContent['next_offset'] == 1
                    assert len(result.structuredContent['activities']) == 1
            for name, arguments in [
                ('get_activity', {'activity_id': '../../secret'}),
                ('get_activity', {'activity_id': '999'}),
                ('list_activities', {'limit': 101}),
                ('list_activities', {'offset': -1}),
                ('get_training_summary', {'start_date': 'invalid'}),
                ('get_training_summary', {'start_date': '2026-10-01', 'end_date': '2026-09-01'}),
                ('get_running_trends', {'granularity': 'daily'}),
            ]:
                assert (await client.call_tool(name, arguments)).isError
    asyncio.run(run())
    assert before == {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_empty_freshness_invalid_and_legacy_records(tmp_path):
    service = QueryService(tmp_path)
    assert service.list_activities()['total'] == 0
    assert service.get_data_freshness()['activity_count'] == 0
    assert service.get_data_freshness()['most_recent_activity_timestamp'] is None
    save(tmp_path)
    (tmp_path / '2026' / 'bad.json').write_text('{}')
    (tmp_path / '2026' / '2026-09-01_running_3.md').write_text('legacy')
    fresh = service.get_data_freshness()
    assert len(fresh['warnings']) >= 3
    write_json(tmp_path / '.sync-state.json', {'status': 'success', 'last_successful_sync_at': '2026-09-02T00:00:00Z'})
    assert service.get_data_freshness()['last_successful_sync_at'] == '2026-09-02T00:00:00Z'


def test_jwt_verifier_rejects_wrong_owner_audience_scope_and_expiry():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = OwnerTokenVerifier('https://issuer.example', 'https://mcp.example/mcp', 'https://issuer.example/jwks', 'owner')
    verifier.jwks.get_signing_key_from_jwt = Mock(return_value=Mock(key=private.public_key()))
    claims = {'iss': verifier.issuer, 'aud': verifier.audience, 'sub': 'owner', 'scope': 'activities:read', 'iat': int(time.time()), 'exp': int(time.time()) + 600}
    def check(data, algorithm='RS256'):
        token = jwt.encode(data, private, algorithm=algorithm)
        return asyncio.run(verifier.verify_token(token))
    assert check(claims)
    for change in [{'sub': 'other'}, {'aud': 'wrong'}, {'iss': 'wrong'}, {'scope': 'other'}, {'exp': 1}, {'nbf': int(time.time()) + 600}]:
        assert check({**claims, **change}) is None
    missing = dict(claims)
    missing.pop('exp')
    assert check(missing) is None
    assert asyncio.run(verifier.verify_token('garbage')) is None


def configure(monkeypatch):
    for key, value in {'ISSUER': 'https://issuer.example', 'RESOURCE_URL': 'https://mcp.example/mcp', 'JWKS_URL': 'https://issuer.example/jwks', 'OWNER_SUBJECT': 'owner'}.items():
        monkeypatch.setenv('GARMIN_MCP_' + key, value)


def test_http_requires_auth_and_advertises_discovery(monkeypatch, tmp_path):
    configure(monkeypatch)
    app = create_server(tmp_path, remote=True).streamable_http_app()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://mcp.example') as client:
            response = await client.post('/mcp', json={})
            assert response.status_code == 401
            assert 'resource_metadata' in response.headers['www-authenticate']
            response = await client.get('/.well-known/oauth-protected-resource/mcp')
            assert response.status_code == 200
            assert response.json()['authorization_servers'] == ['https://issuer.example/']
            response = await client.post('/mcp', headers={'Authorization': 'Bearer invalid'}, json={})
            assert response.status_code == 401
    asyncio.run(run())


def test_remote_configuration_rejects_http(monkeypatch, tmp_path):
    configure(monkeypatch)
    monkeypatch.setenv('GARMIN_MCP_RESOURCE_URL', 'http://mcp.example/mcp')
    with pytest.raises(ValueError, match='HTTPS'):
        create_server(tmp_path, remote=True)


def test_real_stdio_transport_and_import_isolation(tmp_path):
    import subprocess
    import sys
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    subprocess.run([sys.executable, '-c', 'import sys; import garmin_parse.cli; import garmin_parse.mcp_server; assert "garmin_parse.auth" not in sys.modules; assert "garminconnect" not in sys.modules'], check=True)

    async def run():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'garmin_parse.cli', 'mcp', '--activities-dir', str(tmp_path)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                result = await client.call_tool('get_data_freshness', {})
                assert not result.isError
                assert result.structuredContent['activity_count'] == 0
    asyncio.run(run())


def test_authenticated_http_tool_call_and_owner_boundary(monkeypatch, tmp_path):
    from mcp.types import LATEST_PROTOCOL_VERSION
    configure(monkeypatch)
    save(tmp_path)
    server = create_server(tmp_path, remote=True)
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    # The verifier remains real; substitute only the external JWKS network fetch.
    server._token_verifier.jwks.get_signing_key_from_jwt = Mock(return_value=Mock(key=private.public_key()))
    app = server.streamable_http_app()
    claims = {'iss': 'https://issuer.example', 'aud': 'https://mcp.example/mcp', 'sub': 'owner', 'scope': 'activities:read', 'iat': int(time.time()), 'exp': int(time.time()) + 600}

    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://mcp.example') as client:
                for owner, status in [('owner', 200), ('another-user', 401)]:
                    token = jwt.encode({**claims, 'sub': owner}, private, algorithm='RS256')
                    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': LATEST_PROTOCOL_VERSION}
                    response = await client.post('/mcp', headers=headers, json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'get_data_freshness', 'arguments': {}}})
                    assert response.status_code == status, response.text
                    if status == 200:
                        assert response.json()['result']['structuredContent']['activity_count'] == 1
    asyncio.run(run())


def test_symlink_records_cannot_escape_configured_root(tmp_path):
    outside = tmp_path / 'outside'
    save(outside)
    directory = tmp_path / 'data'
    (directory / '2026').mkdir(parents=True)
    (directory / '2026' / 'linked.json').symlink_to(next(outside.glob('*/*.json')))
    assert QueryService(directory).list_activities()['total'] == 0
    other = tmp_path / 'year-data'
    other.mkdir()
    (other / '2026').symlink_to(outside / '2026', target_is_directory=True)
    assert QueryService(other).list_activities()['total'] == 0


def test_stale_sync_and_malformed_state_warn(tmp_path):
    write_json(tmp_path / '.sync-state.json', {'status': 'success', 'last_successful_sync_at': '2000-01-01T00:00:00Z'})
    assert any('48 hours' in w for w in QueryService(tmp_path).get_data_freshness()['warnings'])
    write_json(tmp_path / '.sync-state.json', [])
    assert QueryService(tmp_path).get_data_freshness()['last_attempt_status'] is None
