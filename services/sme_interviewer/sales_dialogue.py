"""Conversation scaffolding and general teaching examples, never product evidence."""
import re

OPENING = ('Hi. My name is Tiberius, or you can call me Tibi. '
           'Before we begin, may I ask your name? You can also jump straight to a question.')
# General concepts, not assertions about an OpsAtlas feature or customer data.
# Concept reference: https://www.w3.org/TR/rdf11-primer/ (classes and relationships).
EXPLANATIONS = {
    'ontology': (
        'An ontology is a shared description of the kinds of things in a subject, and how they relate. '
        'For example, a business might describe people, suppliers and approvals, with a relationship saying who approves what.',
        'Imagine a labelled map. It shows the kinds of things in a business, and what the connections mean. '
        'For example, a person approves a supplier. The ontology defines those categories and that relationship.'),
    'ontology_investigation': (
        'In general, ontology-assisted investigation means using defined relationships to explore a question. '
        'For example, you might follow a link from a supplier to its approver, then look for documents supporting that link. '
        'That is an illustration, not a claim about a particular customer record.',
        'Let me use an example. A document may mention a supplier. A structured relationship can connect that supplier to an approver. '
        'Following the connection helps you ask who approved it; the documents provide the supporting detail. '
        'This is an illustrative example.'),
    'retrieval': (
        'Document retrieval means finding relevant passages in a collection of documents. '
        'Those passages give an answer something to refer back to. Finding a passage does not, by itself, prove it is true.',
        'Think of looking up a passage in a library. You find the relevant page, then use what it says to help answer the question. '
        'You still need to consider whether the source is trustworthy.'),
}


def previous_reply(history):
    return next((m['content'] for m in reversed(history) if m['role'] == 'assistant'), '')


def explanation_request(text, history):
    """Resolve definition/repair requests before topical document selection."""
    lower = text.lower()
    if re.search(r'\b(price|cost|guarantee|customer|certified)\b|\b(?:does|can|will) opsatlas\b', lower):
        return None
    if re.search(r"what(?: is|'s)|mean|explain|simpl|clear|understand|answer.*question", lower):
        if 'ontology' in lower:
            return 'ontology_investigation' if re.search(r'assist|investigat', lower) else 'ontology'
        if re.search(r'what (?:is|does).*retrieval|retrieval mean', lower):
            return 'retrieval'
        if re.search(r'simpl|clear|understand|explain that|example|answer.*question', lower):
            previous = previous_reply(history)
            for term, variants in EXPLANATIONS.items():
                if any(v in previous for v in variants):
                    return term
    return None


def social_reply(text, history):
    """Only complete social utterances bypass factual routing; mixed questions do not."""
    words = text.strip().rstrip('.!?').strip()
    lower = words.lower()
    previous = previous_reply(history)
    if not history or 'ask your name' in previous:
        if lower in ('yes', 'yes please', 'sure', 'of course'):
            return ('What should I call you?', 'social')
        if lower in ('no', 'no thanks', 'no thank you', 'skip', 'rather not', 'skip the small talk'):
            return ('Of course. Would you like an introduction to OpsAtlas, or go straight to your question?', 'social')
    if re.fullmatch(r'(hi|hello|hey)( (tibi|tiberius))?', lower):
        return ('Hello. Good to hear from you. How are you today?', 'social')
    if re.fullmatch(r'(how are you|how are you doing)( today| tibi)?', lower):
        return ("I'm ready to listen, thank you. How are things with you?", 'social')
    if re.fullmatch(r"(?:i'm |i am |doing )?(?:fine|good|well|okay|ok|great)(?:,? (?:thanks|thank you))?", lower):
        return ('Good to hear. Would you like a short introduction to OpsAtlas, or is there something you want to explore?', 'social')
    if re.fullmatch(r"(?:i'm |i am |feeling )?(?:tired|stressed|overwhelmed|having a difficult day)", lower):
        return ('We can take our time. Would you prefer a short introduction, or go straight to your question?', 'social')
    if lower in ('thanks', 'thank you', 'thanks tibi', 'thank you tibi'):
        return ("You're welcome. Take your time if you have another question.", 'social')
    if lower in ('bye', 'goodbye', 'goodbye tibi'):
        return ('Thank you for your time. Speak again soon.', 'closed')
    if lower in ('yes', 'yes thanks', 'yes thank you', 'yes, that helps', 'that helps', 'that answered my question') and (
            'Does that' in previous or 'Was that' in previous):
        return ('Good. Would you like to explore another part of it?', 'social')
    name = re.fullmatch(r"(?:my name is|call me|i am|i'm|it's) ([A-Za-z][A-Za-z'’-]{0,24})", words, re.I)
    if not name and (not history or 'ask your name' in previous or 'What should I call you?' in previous):
        name = re.fullmatch(r"([A-Z][a-z'’-]{1,24})", words)
    if name and name[1].lower() not in ('fine', 'good', 'well', 'tired', 'sad', 'okay', 'ok', 'ready', 'great'):
        return (f'Good to meet you, {name[1]}. How are you today?', 'social')
    return None


def explanation(term, history):
    variants = EXPLANATIONS[term]
    count = sum(any(v in m['content'] for v in variants) for m in history if m['role'] == 'assistant')
    if count >= 2:
        return 'Let me find a different angle. Which part is unclear: the things being described, or the connections between them?'
    intro = "Of course. " if not count else "Sorry, I didn't make that clear. "
    return intro + variants[min(count, 1)] + ' Does that make the idea clearer?'
