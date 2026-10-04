"""Identity and access management (IAM E1).

Who is acting, which spaces and resources they may reach, what they may do there, and the record of it. The package
is the one place that holds security logic: the catalogue of permissions, the built-in roles, the store of identities
and sessions, password handling, the policy evaluator, the audit record, and the bootstrap and recovery procedures.
The API layer (``assistant.api.access``) only asks it questions.
"""
