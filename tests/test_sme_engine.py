"""Tibi's engine versions (OBS S9): a change to the engine cannot ship without a new version."""
from services.sme_interviewer import engine


def test_the_engine_version_changes_when_the_engine_does():
    record = engine.registry()
    released = next(v for v in record['versions'] if v['version'] == record['current'])
    assert engine.fingerprint() == released['fingerprint'], (
        'The Tibi engine changed. Add a version to docs/initiatives/sme-interviewer/tibi-engine-versions.json with '
        f'fingerprint {engine.fingerprint()} and a line on what changed, and make it current.')
    assert released['models'] == engine.models()


def test_versions_are_unique_ordered_and_explained():
    versions = engine.registry()['versions']
    numbers = [tuple(int(p) for p in v['version'].split('.')) for v in versions]
    assert numbers == sorted(set(numbers)) and all(v['changes'].strip() and v['fingerprint'] for v in versions)


def test_the_engine_is_the_voice_service_not_its_tools():
    files = engine.engine_files(['tibi.py', 'continuous.py', 'evaluate_engine.py', 'replay_latency.py', 'engine.py'])
    assert files == ['services/sme_interviewer/continuous.py', 'services/sme_interviewer/tibi.py',
                     'services/opsatlas_sales/claims.py']
    # A change to any engine file changes the fingerprint.
    same = engine.fingerprint(lambda p: b'x', ['tibi.py'], {'conversation': 'm'})
    assert same == engine.fingerprint(lambda p: b'x', ['tibi.py'], {'conversation': 'm'})
    assert same != engine.fingerprint(lambda p: b'y', ['tibi.py'], {'conversation': 'm'})
    assert same != engine.fingerprint(lambda p: b'x', ['tibi.py'], {'conversation': 'other'})
