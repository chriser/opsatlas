"""Deterministic product-claim vocabulary and support checks for spoken OpsAtlas answers.

This module decides two things without a model call:

* whether a user turn or a drafted sentence concerns an OpsAtlas product claim
  (used to route turns and to guard conversational replies), and
* whether a spoken sentence stays within the evidence it cites: every number, price,
  percentage, standard, named product and claim term must appear in the evidence, and
  a term the evidence negates must not be spoken affirmatively.

The vocabulary is generic to product claims. It is deliberately not tuned to specific
test transcripts; add terms by category, never by example sentence.
"""
import re

PRODUCT_NAMES = re.compile(
    r"\b(?:ops\s*-?\s*atlas|atlas|tiberius|tibi|"
    r"(?:the|this|your|our|that) (?:product|platform|system|tool|software|solution|assistant|service))\b", re.I)

# Claim vocabulary by category. Terms of five or more letters also match their inflections
# ("certif" matches "certified"); shorter terms ("api", "sso") match whole words only.
CLAIM_TERMS = {
    'commercial': ['price', 'pricing', 'priced', 'cost', 'costs', 'costing', 'fee', 'fees', 'licence', 'license',
                   'licensing', 'subscription', 'discount', 'roi', 'return on investment', 'saving', 'savings',
                   'payback', 'per seat', 'per user', 'per month', 'per year', 'per annum', 'budget', 'cheap',
                   'expensive', 'afford', 'invoice', 'contract'],
    'assurance': ['guarantee', 'guaranteed', 'guarantees', 'warranty', 'sla', 'service level', 'uptime',
                  'availability target', 'certif', 'accredit', 'compliant', 'compliance', 'iso', 'soc 2', 'soc2',
                  'gdpr', 'hipaa', 'pci', 'cyber essentials', 'penetration test', 'pen test', 'audited',
                  'accurate', 'accuracy', 'hallucinat', 'error rate', 'perfect'],
    'security': ['secure', 'security', 'sso', 'single sign-on', 'single sign on', 'saml', 'oauth', 'mfa',
                 'multi-factor', 'two-factor', 'rbac', 'role-based', 'roles', 'permission', 'access control',
                 'multi-user', 'multi user', 'encrypt', 'authentication', 'authorisation', 'authorization',
                 'data residency', 'privacy', 'confidential'],
    'deployment': ['cloud', 'saas', 'on-premise', 'on premise', 'on-prem', 'offline', 'air-gapped', 'air gapped',
                   'internet', 'deploy', 'hosting', 'hosted', 'install', 'kubernetes', 'scalab', 'enterprise',
                   'production', 'ready for', 'mobile app', 'windows server', 'linux', 'macos'],
    'integration': ['integrat', 'api', 'connector', 'plugin', 'plug-in', 'sharepoint', 'salesforce', 'sap',
                    'servicenow', 'microsoft teams', 'slack integration', 'jira', 'confluence', 'workday', 'oracle',
                    'google drive',
                    'onedrive', 'outlook'],
    'customers': ['customer', 'client', 'reference site', 'case study', 'case studies', 'used by', 'deployed at',
                  'testimonial', 'partner'],
    'timeline': ['roadmap', 'release', 'launch', 'next version', 'next quarter', 'next month', 'next year',
                 'coming soon', 'eta', 'delivery date'],
}
_TERM_PATTERNS = {
    category: [(term, re.compile(r'\b' + re.escape(term).replace(r'\ ', r'[\s-]+') + (r'\w*' if len(term) >= 5 else r'\b'),
                                 re.I)) for term in terms]
    for category, terms in CLAIM_TERMS.items()
}
NUMBER_WORDS = ('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen '
                'sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety '
                'hundred thousand million billion dozen half double triple percent').split()
NUMBER = re.compile(r'(?:[£$€]\s?)?\d[\d,.]*\s?(?:%|k\b|m\b|bn\b)?|\b(?:' + '|'.join(NUMBER_WORDS) + r')\b', re.I)
CURRENCY = re.compile(r'[£$€]|\b(?:pounds?|dollars?|euros?|gbp|usd|eur)\b', re.I)
ACRONYM = re.compile(r'\b[A-Z][A-Z0-9]{1,}\b')
NEGATION = re.compile(r"\b(?:not|no|never|none|cannot|can't|won't|isn't|aren't|doesn't|don't|didn't|without|nor|"
                      r"neither|lacks?|unavailable|unsupported|yet to)\b", re.I)
CAPABILITY_VERB = re.compile(r"\b(?:is|are|has|have|can|could|will|supports?|provides?|offers?|includes?|uses?|runs?|"
                             r"works?|helps?|lets|allows?|integrates?|costs?|guarantees?|delivers?|handles?|stores?|"
                             r"keeps|combines|connects)\b", re.I)
CAPABILITY_QUESTION = re.compile(
    r"\b(?:can|could|does|do|will|would|has|have)\s+(?:it|you|they|this|that)\b|\b(?:is|are)\s+(?:it|they)\b|"
    r"\bhow (?:does|do|would|will|can|could) (?:it|you|this|that)\b|\b(?:your|its)\b", re.I)
DEFINITION = re.compile(r"^(?:so\s+|and\s+|ok(?:ay)?,?\s+)?(?:what(?:'s| is| are| does)|define|explain|"
                        r"can you explain|could you explain|tell me what|what do you mean by)\b", re.I)
QUALIFIER = re.compile(r"\b(?:planned|plan to|experimental|prototype|proof of concept|not (?:yet )?(?:confirmed|verified|"
                       r"delivered|available|established)|not yet|pilot|early|future|in development|don't (?:yet )?have|"
                       r"doesn't (?:yet )?establish|isn't (?:yet )?(?:available|established|confirmed))\b", re.I)
QUALIFIED_STATUS = {
    'planned': "That's planned rather than available today.",
    'experimental': 'That part is still experimental.',
    'uncertain': "That hasn't been verified yet.",
    'unknown': "I don't have approved details on that yet.",
}
_ALLOWED_ACRONYMS = {'I', 'AI', 'OK', 'UK', 'US', 'OPSATLAS', 'TIBI'}


def normal(text):
    return re.sub(r'[\s\-]+', ' ', text.lower()).strip()


def claim_terms(text):
    """(category, vocabulary term) pairs for claim vocabulary in ``text``; stems stand for their inflections."""
    return [(category, term) for category, patterns in _TERM_PATTERNS.items()
            for term, pattern in patterns if pattern.search(text)]


def mentions_product(text):
    return bool(PRODUCT_NAMES.search(text))


def product_turn(text):
    """True when a user turn names the product or raises a product-claim topic."""
    return mentions_product(text) or bool(claim_terms(text))


def capability_question(text):
    return bool(CAPABILITY_QUESTION.search(text))


def definition_question(text):
    return bool(DEFINITION.search(text.strip()))


def product_claim(sentence):
    """True when generated wording asserts something about the product or a claim topic.

    Naming the product in passing ("happy to tell you about OpsAtlas") is not a claim;
    naming it with a capability verb, or using claim vocabulary or figures, is.
    """
    if claim_terms(sentence) or (NUMBER.search(sentence) and CURRENCY.search(sentence)):
        return True
    match = PRODUCT_NAMES.search(sentence)
    return bool(match and CAPABILITY_VERB.search(sentence[match.end():match.end() + 60]))


def _numbers(text):
    return {re.sub(r'[\s,£$€]', '', m.group(0).lower()) for m in NUMBER.finditer(text)}


def _negated(text, term):
    """Whether every occurrence of ``term`` in ``text`` sits under a nearby negation in its sentence."""
    value = normal(text)
    positions = [m.start() for m in re.finditer(re.escape(normal(term)), value)]
    if not positions:
        return False
    for position in positions:
        sentence_start = max(value.rfind('.', 0, position), value.rfind('?', 0, position), value.rfind(';', 0, position))
        window = value[max(sentence_start + 1, position - 110):position]
        if not NEGATION.search(window):
            return False
    return True


def unsupported(sentence, evidence_text, question=''):
    """Reasons the sentence is not supported by ``evidence_text``; empty when supported.

    ``question`` lets a sentence repeat the user's own words (for example, stating that
    a figure they named is not established) without that echo counting as a new claim.
    """
    evidence = normal(evidence_text)
    heard = normal(question)
    reasons = []
    for number in _numbers(sentence) - _numbers(evidence_text) - _numbers(question):
        reasons.append(f'figure "{number}" is not in the evidence')
    if CURRENCY.search(sentence) and not CURRENCY.search(evidence_text) and not CURRENCY.search(question):
        reasons.append('currency is not in the evidence')
    for acronym in set(ACRONYM.findall(sentence)) - _ALLOWED_ACRONYMS:
        if acronym.lower() not in evidence and acronym.lower() not in heard:
            reasons.append(f'"{acronym}" is not in the evidence')
    negated_sentence = bool(NEGATION.search(sentence)) or bool(QUALIFIER.search(sentence))
    for category, term in dict.fromkeys(claim_terms(sentence)):
        key = normal(term)
        if key not in evidence:
            if key in heard and negated_sentence:
                continue  # "I can't confirm the SSO support you asked about" repeats, not asserts.
            reasons.append(f'{category} term "{term}" is not in the evidence')
        elif _negated(evidence_text, term) and not _negated(sentence, term) and not negated_sentence:
            reasons.append(f'the evidence negates "{term}" but the answer asserts it')
    return reasons


def qualifier_for(records):
    """The spoken qualification a cited set of records requires, or None."""
    for status in ('unknown', 'uncertain', 'planned', 'experimental'):
        if any(r.get('status') == status for r in records):
            return QUALIFIED_STATUS[status]
    return None


def has_qualifier(text):
    return bool(QUALIFIER.search(text))
