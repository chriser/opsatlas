"""The OpsAtlas product ontology: governed product facts for Tibi and the sales pitch.

Curated objects (capabilities, components, limitations, and broad topics with their aspects) live in
``corpus/product_ontology.json``. Each names the curated records that establish it. The graph is
rebuilt in the platform's OntologyStore, in its own database and schema, whenever the enabled records
change: an object exists only while every record it rests on is enabled. A topic exists while at
least two of its aspects do.

``match`` answers one question cheaply from memory: product-specific names it mentions (a routing
signal), a broad topic it raises without choosing an aspect (a clarification signal), compact facts
for the evidence pack, and the records behind the strongest matches.
"""
import hashlib
import json
import re
import threading
from pathlib import Path

from assistant.ontology.schema import SchemaRegistry
from assistant.ontology.store import OntologyStore, object_id_for

CORPUS = Path(__file__).parent / 'corpus'
SCHEMA = CORPUS / 'product_schema.json'
CONTENT = CORPUS / 'product_ontology.json'
EVIDENCED_BY = {'capability': 'capability_evidenced_by', 'component': 'component_evidenced_by',
                'limitation': 'limitation_evidenced_by', 'aspect': 'aspect_evidenced_by'}
PROPERTIES = {'capability': ('name', 'status', 'summary', 'aliases', 'keywords'),
              'component': ('name', 'technology', 'runs', 'aliases', 'keywords'),
              'limitation': ('name', 'scope', 'aliases', 'keywords'),
              'topic': ('name', 'aliases', 'keywords'),
              'aspect': ('name', 'aliases', 'keywords')}
# Questions about the whole product rather than one part of it.
STATUS_CUE = re.compile(r"\b(?:delivered|planned|roadmap|experimental|status|what(?:'s| is) (?:ready|built|done))\b")
HOSTING_CUE = re.compile(r"\b(?:locally|local|cloud|internet|offline|on[- ]?prem\w*|hosted|hosting|external|run|runs|running)\b")
LIMIT_CUE = re.compile(r"\b(?:limitations?|limits?|boundar(?:y|ies)|weakness\w*|not include|missing)\b")
PARTS_CUE = re.compile(r"\b(?:components?|architecture|stack|technolog\w+|built with|made of)\b")
FACT_LIMIT = 900


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normal(text):
    return ' ' + re.sub(r"[^a-z0-9.'-]+", ' ', text.lower().replace('’', "'")).strip() + ' '


def mentions(text, term):
    """Whole-word (or whole-phrase) mention in normalised text; a trailing plural s is allowed."""
    return re.search(r'(?<![a-z0-9])' + re.escape(term.lower()) + r"(?:s|es)?(?![a-z0-9])", text) is not None


class ProductOntology:
    def __init__(self, db_path, content=CONTENT, schema=SCHEMA):
        self.store = OntologyStore(db_path, SchemaRegistry.load(schema))
        self.content = json.loads(Path(content).read_text())
        self.order = {item['id']: n for n, item in enumerate(self.content['objects'])}
        self.lock = threading.Lock()
        self.key = None
        self.graph = {'objects': {}, 'links': [], 'unusable': [], 'counts': {}}

    # ---- build ---------------------------------------------------------------------

    def ensure(self, rows):
        """Rebuild when the enabled records change; return the in-memory graph."""
        enabled = {r['id']: r for r in rows if r['eligible']}
        key = sha(json.dumps(sorted((i, r['sha256']) for i, r in enabled.items())).encode())
        with self.lock:
            if key != self.key:
                self.graph = self._rebuild(enabled)
                self.key = key
            return self.graph

    def _rebuild(self, enabled):
        store = self.store
        store.clear()
        for record in enabled.values():
            store.upsert_object('record', record['id'], {'record_id': record['id'], 'title': record['title'],
                                                         'status': record['status']}, source_ref=record['source_id'])
        curated = {item['id']: item for item in self.content['objects']}
        usable, unusable = {}, []
        for item in curated.values():
            if item['type'] == 'topic':
                continue
            missing = [r for r in item['evidence'] if r not in enabled]
            if missing or not item['evidence']:
                unusable.append({'id': item['id'], 'type': item['type'], 'name': item['name'], 'missing': missing})
                continue
            usable[item['id']] = self._upsert(item)
            for record_id in item['evidence']:
                store.link(EVIDENCED_BY[item['type']], usable[item['id']], object_id_for('record', record_id))
        for item in curated.values():
            if item['type'] != 'topic':
                continue
            aspects = [to for kind, source, to in self.content['links'] if kind == 'topic_has_aspect'
                       and source == item['id'] and to in usable]
            if len(aspects) < 2:
                unusable.append({'id': item['id'], 'type': 'topic', 'name': item['name'], 'missing': ['two enabled aspects']})
                continue
            usable[item['id']] = self._upsert(item)
        for kind, source, target in self.content['links']:
            if source in usable and target in usable:
                store.link(kind, usable[source], usable[target])
        return self._read(usable, unusable)

    def _upsert(self, item):
        kind = item['type']
        key = self.store.registry.require_object_type(kind).primary_key
        properties = {name: item.get(name, [] if name in ('aliases', 'keywords') else '') for name in PROPERTIES[kind]}
        return self.store.upsert_object(kind, item['id'], {key: item['id'], **properties},
                                        source_ref=','.join(item.get('evidence', []))).id

    def _read(self, usable, unusable):
        """The graph as the store holds it, so every answer reflects the governed store."""
        objects, links = {}, []
        for store_id in usable.values():
            found = self.store.get(store_id)
            objects[store_id] = {'id': store_id, 'type': found.object_type, **found.properties,
                                 'evidence': [r for r in found.source_ref.split(',') if r]}
        for store_id in usable.values():
            for kind, sides in self.store.neighbors(store_id).items():
                links.extend((kind, store_id, other.id) for other in sides['out'] if not kind.endswith('_evidenced_by'))
        return {'objects': objects, 'links': links, 'unusable': unusable, 'counts': self.store.counts()}

    # ---- use -------------------------------------------------------------------------

    def targets(self, store_id, kind):
        return [self.graph['objects'][to] for k, source, to in self.graph['links'] if k == kind and source == store_id]

    def sources(self, store_id, kind):
        return [self.graph['objects'][source] for k, source, to in self.graph['links'] if k == kind and to == store_id]

    def fact(self, item):
        if item['type'] == 'capability':
            parts = [f"{item['name']} ({item['status']}): {item['summary']}."]
            if built := self.targets(item['id'], 'capability_builds_on'):
                parts.append('Built on: ' + '; '.join(c['name'] for c in built) + '.')
            if parts_used := self.targets(item['id'], 'capability_uses_component'):
                parts.append('Works through: ' + '; '.join(f"{c['name']} ({c['technology']}, {c['runs']})"
                                                           for c in parts_used) + '.')
            if limits := self.targets(item['id'], 'capability_limited_by'):
                parts.append('Boundary: ' + '; '.join(c['name'] for c in limits) + '.')
            return ' '.join(parts)
        if item['type'] == 'component':
            users = self.sources(item['id'], 'capability_uses_component')
            return (f"{item['name']}: {item['technology']}; {item['runs']}."
                    + (' Used for: ' + ', '.join(c['name'] for c in users) + '.' if users else ''))
        if item['type'] == 'limitation':
            return f"{item['name']} ({item['scope']})."
        return ''

    @staticmethod
    def status(item):
        """A fact's record status: a capability speaks for its own delivery status."""
        return {'delivered': 'available'}.get(item.get('status'), item.get('status')) or 'available'

    def overview(self, text):
        """Whole-product facts for questions about status, hosting, boundaries or parts."""
        objects = list(self.graph['objects'].values())
        lines = []
        if STATUS_CUE.search(text):
            groups = {}
            for c in (o for o in objects if o['type'] == 'capability'):
                groups.setdefault(c['status'], []).append(c['name'])
            lines.append(' '.join(f"{status.capitalize()}: {', '.join(names)}." for status, names in sorted(groups.items())))
        if HOSTING_CUE.search(text):
            groups = {}
            for c in (o for o in objects if o['type'] == 'component'):
                groups.setdefault(c['runs'], []).append(c['name'])
            lines.append(' '.join(f"{where.capitalize()}: {', '.join(names)}." for where, names in groups.items()))
        if LIMIT_CUE.search(text):
            lines.append('Proof-of-concept boundaries: ' + '; '.join(
                o['name'] for o in objects if o['type'] == 'limitation') + '.')
        if PARTS_CUE.search(text):
            lines.append('Components: ' + '; '.join(f"{o['name']} ({o['technology']})"
                                                     for o in objects if o['type'] == 'component') + '.')
        return [line for line in lines if line]

    def match(self, query):
        text = normal(query)
        items = list(self.graph['objects'].values())
        names, scores, rest = [], {}, text
        for item in items:
            for alias in item.get('aliases', []):
                if mentions(text, alias):
                    scores[item['id']] = scores.get(item['id'], 0) + 3
                    names.append({'id': item['id'], 'type': item['type'], 'name': item['name'], 'alias': alias})
                    rest = rest.replace(' ' + alias.lower() + ' ', '  ')
        # A named part's words are spent: "activity model" is not also a question about language models.
        for item in items:
            if hits := sum(2 if ' ' in kw else 1 for kw in item.get('keywords', []) if mentions(rest, kw)):
                scores[item['id']] = scores.get(item['id'], 0) + hits
        scored = [(score, self.graph['objects'][i]) for i, score in scores.items()]
        scored.sort(key=lambda pair: -pair[0])
        topic = next((item for _, item in scored if item['type'] == 'topic'), None)
        aspects = [{'id': item['id'], 'name': item['name'], 'records': item['evidence'], 'score': score}
                   for score, item in scored if item['type'] == 'aspect']
        topic_view = None
        if topic:
            # Aspects in their curated order: the most commonly meant area first.
            aspects_of = sorted(self.targets(topic['id'], 'topic_has_aspect'), key=lambda a: self.order[a['aspect_id']])
            topic_view = {'id': topic['id'], 'name': topic['name'], 'aspects': [
                {'id': a['id'], 'name': a['name'], 'records': a['evidence']} for a in aspects_of]}
            topic_aspects = {a['id'] for a in topic_view['aspects']}
            aspects = [a for a in aspects if a['id'] in topic_aspects]
        facts, status, size = [], [], 0
        # Each fact carries the delivery status it speaks for; overview lines name their own statuses.
        lines = [*((self.fact(item), self.status(item)) for _, item in scored[:3]),
                 *((line, 'available') for line in self.overview(text))]
        for line, state in lines:
            if line and line not in facts and size + len(line) <= FACT_LIMIT:
                facts.append(line)
                status.append(state)
                size += len(line)
        # A chosen aspect of a raised topic, then strong matches (a name or a phrase), bring their records.
        chosen = [a['records'] for a in aspects[:1]] if topic_view else []
        strong = [item['evidence'] for score, item in scored
                  if score >= 2 and item['type'] in ('capability', 'component', 'limitation')]
        records = []
        for evidence in [*chosen, *strong]:
            records.extend(r for r in evidence if r not in records)
        overview = [name for name, cue in (('status', STATUS_CUE), ('limits', LIMIT_CUE), ('parts', PARTS_CUE))
                    if cue.search(text)]
        return {'names': names, 'topic': topic_view, 'aspects': aspects, 'facts': facts, 'fact_status': status,
                'records': records, 'overview': overview}

    def export(self):
        graph = self.graph
        return {'objects': sorted(graph['objects'].values(), key=lambda o: (o['type'], o['name'])),
                'links': [{'type': k, 'from': a, 'to': b} for k, a, b in graph['links']],
                'unusable': graph['unusable'], 'counts': graph['counts']}
