"""Typed conversations with Tibi's engine, without audio: the Digital SME's channel (DSME S1).

The Digital SME avatar (Anam) is only a renderer: it speaks the text it is given. To give the same answers as Tibi,
the control panel's Ask Digital SME page asks Tibi's own engine through this channel. The routing, the approved
records and spoken answers, and the checks on every sentence are the same code and the same engine version as the
voice. Only the delivery differs: no speech recognition and no Higgs voice here, and the reply comes back as text.

Each avatar session is its own short conversation, so follow-ups ("Why is that?", "The first one") work. It never
shares the voice conversation's history, and it is held in memory only: forgotten after half an hour idle, when
closed, or when the service restarts. Each turn goes to the conversation log (mode ``digital_sme``) like a voice turn.
The activity log records the turn's route and timing, never its wording.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from collections import OrderedDict

from .tibi import EvidenceChanged

LIMIT = 8               # conversations held at once; the one idle longest is dropped first
IDLE_SECONDS = 30 * 60  # a conversation left this long is forgotten
TURN_SECONDS = 30       # a reply that takes longer is abandoned with a plain message
CHANGED = 'The evidence changed while I checked. Please ask again so I can use the current version.'


class TextChannel:
    def __init__(self, factory, conversation_log=None, activity=None):
        self.factory = factory                    # history -> a Tibi, exactly as the voice builds one
        self.conversation_log = conversation_log  # the workspace root, or None to keep no log
        self.activity = activity
        self.sessions: OrderedDict[str, dict] = OrderedDict()

    def log(self, event, **fields):
        if self.activity is not None:
            self.activity.write('text', event=event, **fields)

    def _prune(self):
        now = time.monotonic()
        for identifier in [k for k, s in self.sessions.items() if now - s['used'] > IDLE_SECONDS and not s['lock'].locked()]:
            self.sessions.pop(identifier)
        while len(self.sessions) >= LIMIT:
            identifier, _ = next((item for item in self.sessions.items() if not item[1]['lock'].locked()), (None, None))
            if identifier is None:
                raise OverflowError('Too many conversations with Tibi are open. Close one and try again.')
            self.sessions.pop(identifier)

    def open(self, channel='digital_sme') -> dict:
        """A new conversation. The engine starts warming its model straight away, so the first answer is quick."""
        self._prune()
        identifier = 'sme-' + secrets.token_hex(6)
        tibi = self.factory([])
        evidence = getattr(tibi, 'evidence', None)
        if evidence is not None and hasattr(evidence, 'conversation'):
            evidence.conversation = identifier  # OpsAtlas answers as this session's owner (REF S10)
        session = {'tibi': tibi, 'channel': channel, 'used': time.monotonic(), 'turns': 0, 'lock': asyncio.Lock()}
        session['warming'] = asyncio.create_task(self._warm(identifier, tibi))
        self.sessions[identifier] = session
        from .engine import current
        self.log('conversation opened', session=identifier, channel=channel)
        return {'id': identifier, 'channel': channel, 'engine': current()['version']}

    async def _warm(self, identifier, tibi):
        started = time.monotonic()
        try:
            await asyncio.wait_for(tibi.warm(), 150)
            self.log('ready', session=identifier, seconds=round(time.monotonic() - started, 2))
        except Exception as exc:  # the first turn reports it plainly if the model is still unavailable
            self.log('warm-up failed', session=identifier, error=type(exc).__name__)

    def close(self, identifier) -> bool:
        session = self.sessions.pop(identifier, None)
        if session and not session['warming'].done():
            session['warming'].cancel()
        if session:
            self.log('conversation closed', session=identifier, turns=session['turns'])
        return session is not None

    async def turn(self, identifier, text) -> dict:
        """One typed turn through Tibi's engine: the reply as the voice would speak it, and how it was reached."""
        session = self.sessions.get(identifier)
        if session is None:
            raise KeyError(identifier)
        async with session['lock']:  # one turn at a time, in order, as in a spoken conversation
            session['used'] = time.monotonic()
            self.sessions.move_to_end(identifier)
            tibi = session['tibi']
            started = time.perf_counter()
            turn = tibi.begin(text)
            segments = []
            try:
                async with asyncio.timeout(TURN_SECONDS):
                    while (segment := await turn.next()) is not None:
                        segments.append(segment.text)
                    await turn.task
                    # The reply goes to the avatar only if its evidence is still current (audit F02).
                    await tibi.authorise(turn)
            except EvidenceChanged:
                self.log('turn', session=identifier, route='evidence_changed')
                self._record(identifier, session, text, {'reply': CHANGED, 'route': 'evidence_changed'},
                             round((time.perf_counter() - started) * 1000, 1), outcome='refused')
                return {'reply': CHANGED, 'segments': [CHANGED], 'route': 'evidence_changed', 'route_reasons': [],
                        'grounding': 'evidence_changed', 'records': [], 'phase': 'social', 'reasoning_ms': None,
                        'total_ms': round((time.perf_counter() - started) * 1000, 1), 'engine': self._engine()}
            except Exception as exc:  # a failed turn is on record too (audit F08), then reported to the page
                self._record(identifier, session, text, {'reply': ' '.join(segments), 'route': None},
                             round((time.perf_counter() - started) * 1000, 1), outcome='failed',
                             failure={'error': type(exc).__name__})
                raise
            finally:
                if not turn.task.done():
                    turn.cancel()
            result = turn.result
            tibi.commit(text, result['reply'], result['route'], result.get('clarify'))
            session['turns'] += 1
            total = round((time.perf_counter() - started) * 1000, 1)
            self._record(identifier, session, text, result, total)
            return {'reply': result['reply'], 'segments': segments, 'route': result['route'],
                    'route_reasons': result.get('route_reasons') or [], 'grounding': result.get('grounding'),
                    'records': [{k: r.get(k) for k in ('id', 'title', 'source_id', 'status')} for r in result.get('evidence') or []],
                    'blocked': result.get('blocked'), 'phase': result.get('phase'), 'reasoning_ms': result.get('reasoning_ms'),
                    'total_ms': total, 'engine': self._engine()}

    @staticmethod
    def _engine():
        from .engine import current
        engine = current()
        return {'version': engine['version'], 'fingerprint': engine['fingerprint']}

    def _record(self, identifier, session, text, result, total, outcome='completed', failure=None):
        self.log('turn', session=identifier, route=result.get('route'), grounding=result.get('grounding'),
                 reasoning_ms=result.get('reasoning_ms'), total_ms=total)
        if self.conversation_log is None:
            return
        from services.opsatlas_sales.conversations import append
        try:
            append(self.conversation_log, {
                'at': time.strftime('%Y-%m-%dT%H:%M:%S%z'), 'session': identifier, 'turn': session.get('logged', 0),
                'mode': session['channel'], 'engine': self._engine(), 'outcome': outcome,
                **({'failure': failure} if failure else {}), 'voice': 'anam' if session['channel'] == 'digital_sme' else None,
                'typed': True, 'heard': text, 'reply': result.get('reply'), 'route': result.get('route'),
                'route_reasons': result.get('route_reasons'), 'grounding': result.get('grounding'),
                'records': [e.get('id') for e in result.get('evidence') or [] if isinstance(e, dict)],
                'guidance': result.get('guidance'), 'style': result.get('style'), 'phase': result.get('phase'),
                'timings': {**(result.get('marks') or {}), 'reasoning_ms': result.get('reasoning_ms'), 'total_ms': total},
                'issue': result.get('conversation_issue'), 'blocked': result.get('blocked'),
                'background_check': result.get('background_check'), 'interrupted': False})
            session['logged'] = session.get('logged', 0) + 1
        except Exception:  # a logging failure never breaks the turn
            logging.getLogger(__name__).warning('Could not log a Digital SME turn', exc_info=True)
