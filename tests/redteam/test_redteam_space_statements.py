"""Red team, REF F10: attempts to break the promises of assistant.space_statements.SpaceStatements (hermetic)."""
import json

import pytest

from assistant.space_config import SpaceConfig, TopicSentence
from assistant.space_statements import FILE_NAME, SpaceStatements, texts_of


def test_two_instances_on_one_folder_lose_a_version(tmp_path):
    """Two processes (two workers, or the app and a script) each hold their own SpaceStatements and so their own
    threading.Lock. B's sync lands while A is between its read and its write; without a lock across store objects A's
    write drops B's version (and both are v2). B runs on its own thread, as another process would (rewritten from a
    nested call, which a real lock turns into a deadlock)."""
    import threading
    import time
    a, b = SpaceStatements(tmp_path), SpaceStatements(tmp_path)
    a.sync({"refusal": "v1"}, adopt_new=True)
    real_write, other = a._write, []

    def b_lands_meanwhile(data):
        other.append(threading.Thread(target=b.sync, args=({"refusal": "from b"},)))
        other[0].start()
        time.sleep(0.2)  # B tries now; with the lock it waits for A
        real_write(data)

    a._write = b_lands_meanwhile
    a.sync({"refusal": "from a"})
    other[0].join(5)
    versions = json.loads((tmp_path / FILE_NAME).read_text())["refusal"]
    assert sorted(v["text"] for v in versions) == ["from a", "from b", "v1"]
    assert [v["version"] for v in versions] == [1, 2, 3]


def test_store_behind_a_dangling_symlink_is_taken_for_empty(tmp_path):
    """The store is a symlink to another volume that is not mounted: Path.exists() is False, _read returns {}, and
    sync records the pending words as version 1 'approved as found', replacing the link. Promise: an unreadable
    store is an error, never empty; a pending version is never said."""
    elsewhere = tmp_path / "volume"
    real = SpaceStatements(elsewhere)
    real.sync({"refusal": "approved words"}, adopt_new=real.new)  # governance starts
    real.sync({"refusal": "pending words"})
    space = tmp_path / "space"
    space.mkdir()
    (space / FILE_NAME).symlink_to(elsewhere / FILE_NAME)
    s = SpaceStatements(space)
    assert s.approved("refusal")["text"] == "approved words"
    (elsewhere / FILE_NAME).rename(elsewhere / "unmounted")
    with pytest.raises(ValueError):
        s.sync({"refusal": "pending words"})
    with pytest.raises(ValueError):  # reading it is an error too: nothing is said from a store that is not there
        s.approved("refusal")
    assert (space / FILE_NAME).is_symlink()  # and the link was not written over


def test_a_statement_added_after_governance_began_is_said_unapproved(tmp_path):
    """Governance began with the refusal and scope message. The owner later adds a note to space-config.json; at
    the next start sync sees a new key and records it 'approved as found' (meant for the words in use once, at the
    start of governance), so governed() says words nobody approved."""
    s = SpaceStatements(tmp_path)
    s.sync(texts_of(SpaceConfig()), adopt_new=s.new)  # governance starts
    edited = SpaceConfig(notes=[TopicSentence(topics=["warranty"], sentence="Warranty is five years (unreviewed).")])
    s.sync(texts_of(edited))
    assert s.governed(edited).notes[0].sentence != "Warranty is five years (unreviewed)."


def test_removing_a_note_moves_another_notes_approved_sentence(tmp_path):
    """Notes are keyed by position (note.0, note.1). Removing the first note makes the delivery note note.0; its
    words differ from note.0's versions, become pending, and governed() ends delivery answers with the approved
    returns sentence, a sentence approved for other topics, while the delivery sentence (approved) is not said."""
    s = SpaceStatements(tmp_path)
    returns = TopicSentence(topics=["returns"], sentence="Returns: see the returns policy.")
    delivery = TopicSentence(topics=["delivery"], sentence="Delivery: see the delivery policy.")
    s.sync(texts_of(SpaceConfig(notes=[returns, delivery])), adopt_new=s.new)  # governance starts
    after = SpaceConfig(notes=[delivery])
    s.sync(texts_of(after))
    said = s.governed(after).notes[0]
    assert (said.topics, said.sentence) == (["delivery"], "Delivery: see the delivery policy.")
