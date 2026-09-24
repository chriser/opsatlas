"""One explicit writable workspace; never fall back to the existing Atlas data."""
import json
import secrets
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / '.runtime/opsatlas-sales'


def workspace(root=ROOT):
    root = Path(root).absolute()
    # Reject links in ancestors and descendants before any store is opened.
    for path in [root, *root.parents]:
        if path.is_symlink():
            raise ValueError('Sales workspace cannot contain symlinks')
    if root == REPO / 'data' or (REPO / 'data') in root.parents:
        raise ValueError('Existing Atlas data is not a sales workspace')
    assets = REPO / 'services/sme_interviewer/.runtime'
    allowed = {root / 'voice' / n: assets / n for n in ('models', 'experience', 'experience-env')}
    allowed[root / 'voice/conversation-recognizer'] = assets / 'recognition-check/conversation-recognizer'
    if root.exists():
        for p in root.rglob('*'):
            if p.is_symlink() and (p not in allowed or p.resolve() != allowed[p].resolve()):
                raise ValueError('Sales workspace contains an unexpected symlink')
    marker = root / 'workspace.json'
    if root.exists() and any(root.iterdir()) and not marker.exists():
        raise ValueError('Refusing an unmarked non-empty workspace')
    root.mkdir(parents=True, exist_ok=True)
    if marker.exists():
        if json.loads(marker.read_text()) != {'schema': 1, 'workspace': 'opsatlas-sales'}:
            raise ValueError('Wrong workspace identity')
    else:
        marker.write_text(json.dumps({'schema': 1, 'workspace': 'opsatlas-sales'}))
    for name in ('core', 'voice'):
        (root / name).mkdir(exist_ok=True)
    credential = root / 'local-access.key'
    if not credential.exists():
        with credential.open('x') as f:
            credential.chmod(0o600)
            f.write(secrets.token_urlsafe(32))
    return root
