import json
from pathlib import Path

import pytest

from services.opsatlas_sales import claims

RECORDS = {r['id']: r for r in json.loads(
    (Path(__file__).parents[1] / 'services/opsatlas_sales/corpus/product.json').read_text())}


def test_every_record_supports_its_own_wording():
    for record in RECORDS.values():
        assert not claims.unsupported(record['text'], record['text']), record['id']


@pytest.mark.parametrize('sentence, record', [
    ('OpsAtlas supports enterprise multi-user roles and SSO today.', 'limitations'),
    ('It has per-source access controls.', 'limitations'),
    ("It's normally 500 pounds per seat per month.", 'commercial'),
    ('That would be about 40 thousand pounds a year, with a 300 percent ROI.', 'commercial'),
    ('OpsAtlas is ISO 27001 certified.', 'limitations'),
    ('Source approval guarantees every statement is correct.', 'governance'),
    ('It gives perfect answers every time.', 'retrieval'),
    ('Everything including the avatar runs fully offline.', 'deployment'),
    ('It is production ready for enterprise use.', 'limitations'),
    ("It doesn't need setup and supports SSO.", 'limitations'),
    ('It has enterprise multi-user roles.', 'limitations'),
    ('The platform can run offline, but not all optional integrations operate offline.', 'deployment'),
    ('OpsAtlas can be integrated with SharePoint.', 'limitations'),
    ('It runs locally to ensure data privacy and security.', 'deployment'),
    ('The ROI is 300 percent.', 'commercial'),
])
def test_review_probes_are_blocked(sentence, record):
    assert claims.unsupported(sentence, RECORDS[record]['text'])


@pytest.mark.parametrize('sentence, record, question', [
    ("The current core is a proof of concept with single-operator authentication, so it doesn't yet establish "
     'enterprise multi-user roles.', 'limitations', ''),
    ("I don't have approved pricing yet, so I can't give you a figure.", 'commercial', 'How much would it cost?'),
    ('OpsAtlas brings approved company knowledge together so people get cited answers.', 'overview', ''),
    ('It does not have per-source access controls yet.', 'limitations', ''),
    ("I can't confirm the SSO support you asked about.", 'limitations', 'Does it support SSO?'),
    ('The core runs locally, while the optional avatar uses Anam as a managed service.', 'deployment', ''),
    ('Pricing details need explicit owner evidence and approval before they can be represented to customers.', 'commercial', ''),
    ('Pricing and other details like customer references are unknown at this time.', 'commercial', ''),
    ("Source approval doesn't guarantee the accuracy of every statement.", 'governance', ''),
    ('The core runs locally, but optional integrations are not guaranteed to work offline.', 'deployment', ''),
    ("SharePoint integration isn't established in the records.", 'limitations', 'Can it integrate with SharePoint?'),
    ("For a bank, you'd need to assess production readiness and security separately.", 'limitations', ''),
    ("Pricing and savings details haven't been confirmed.", 'commercial', ''),
    ('You would need owner approval and evidence to determine ROI.', 'commercial', 'What is the return on investment?'),
    ('Human review is still needed to ensure accuracy.', 'governance', ''),
])
def test_faithful_paraphrases_pass(sentence, record, question):
    assert not claims.unsupported(sentence, RECORDS[record]['text'], question)


def test_routing_vocabulary_is_generic():
    assert claims.product_turn('How much would it cost us per year?')
    assert claims.product_turn('Is the platform secure enough for a bank?')
    assert claims.product_turn('What is Atlas really?')
    assert not claims.product_turn('Tell me a joke.')
    assert claims.capability_question('Can it draw process diagrams?') and claims.capability_question('How does it work?')
    assert not claims.capability_question('Hello, how are you?')
    assert claims.definition_question('What is an ontology?') and not claims.definition_question('Tell me a joke.')
    assert not claims.claim_terms('The core runs on your own machine and helps teams find answers.')


def test_conversation_guard_detects_claims_but_not_passing_mentions():
    assert claims.product_claim('OpsAtlas can connect to SharePoint.')
    assert claims.product_claim('It usually costs around £40k a year.')
    assert not claims.product_claim('Happy to tell you about OpsAtlas whenever you like.')
    assert not claims.product_claim('My week has been fine, thanks!')


def test_qualifiers_follow_record_status():
    assert claims.qualifier_for([RECORDS['tiberius']]) == 'That part is still experimental.'
    assert claims.qualifier_for([RECORDS['commercial']]).startswith("I don't have approved details")
    assert claims.qualifier_for([RECORDS['overview']]) is None
    assert claims.has_qualifier('Tibi is the experimental voice companion.')
