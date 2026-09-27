"""The Tibi service's manifest records what the engine version does not (audit F10)."""
import os

from services.sme_interviewer import manifest as manifest_module
from services.sme_interviewer.manifest import build


def test_voice_and_recognition_settings_change_the_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    monkeypatch.setattr(manifest_module, 'ollama_models', lambda names: {n: {'digest': 'sha256:fixed'} for n in names})
    base = build(tmp_path)
    assert base['id'] == build(tmp_path)['id']  # the same process and settings: the same manifest
    os.environ['SME_HIGGS_BITS'] = '8'
    eight_bit = build(tmp_path)
    assert eight_bit['speech']['voice']['precision'] == '8-bit backbone' and eight_bit['id'] != base['id']
    os.environ['SME_ASR_VOCABULARY'] = 'OpsAtlas, Tibi, something new'
    assert build(tmp_path)['id'] != eight_bit['id']
    assert {'knowledge', 'governance', 'retrieval', 'client'} <= set(base['code']['components'])
    assert base['engine']['fingerprint'] and base['platform']['python'] and 'fastapi' in base['packages']


def test_model_builds_are_named_by_digest_and_a_missing_server_is_said_plainly(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest_module, 'OLLAMA', 'http://127.0.0.1:9')
    missing = build(tmp_path)
    assert all(m['digest'] is None and 'not reachable' in m['note'] for m in missing['models'].values())
    monkeypatch.setattr(manifest_module, 'ollama_models', lambda names: {n: {'digest': f'sha256:{n}'} for n in names})
    assert build(tmp_path)['id'] != missing['id']


def test_a_large_file_is_hashed_once_and_again_when_it_changes(tmp_path):
    path = tmp_path / 'model.bin'
    path.write_bytes(b'weights')
    cache = {}
    first = manifest_module.file_identity(path, cache)
    assert manifest_module.file_identity(path, cache) == first and len(cache) == 1
    path.write_bytes(b'other weights')
    assert manifest_module.file_identity(path, cache)['sha256'] != first['sha256']


def test_the_service_serves_the_manifest_it_started_with(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from services.sme_interviewer.sales_preview import sales_app
    monkeypatch.setattr(os, 'environ', os.environ.copy())
    app = sales_app(tmp_path / 'sales', 'http://core')
    with TestClient(app, base_url='http://127.0.0.1') as client:
        health = client.get('/api/health').json()
        served = client.get('/api/manifest').json()
    assert health['manifest'] == served['id'] and health['changed_on_disk'] is False
    assert (tmp_path / 'sales' / 'logs' / 'manifests' / f"{served['id']}.json").exists()
