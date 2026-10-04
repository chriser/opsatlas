"""Passwords (IAM F2): Argon2id hashes, and a policy that follows NIST SP 800-63B-4 §3.1.1.

At least 15 characters and at most 128 code points, spaces and Unicode allowed, NFC-normalised before hashing, no
composition rules, no forced rotation, and a block on common, repeated and context-specific passwords. Hashing
is argon2id at m=64 MiB, t=3, p=1 (above OWASP's minimum of 19 MiB, t=2); the parameters travel with each hash and
a login rehashes when they change. Verifying against a dummy hash for an unknown account keeps the timing alike.
"""

from __future__ import annotations

import re
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH, MAX_LENGTH = 15, 128
PARAMS = {"memory_cost": 65536, "time_cost": 3, "parallelism": 1}
FAST_PARAMS = {"memory_cost": 8192, "time_cost": 1, "parallelism": 1}  # the test suite and the single-operator dev core only
_hasher = PasswordHasher(**PARAMS)
_fast = False
_DUMMY = _hasher.hash("a dummy hash, verified when the account does not exist")


def use_fast_profile() -> None:
    """Cheap argon2id parameters for tests and the single-operator development core; never the secured deployment."""
    global _hasher, _fast, _DUMMY
    if not _fast:
        _hasher, _fast = PasswordHasher(**FAST_PARAMS), True
        _DUMMY = _hasher.hash("a dummy hash, verified when the account does not exist")


def current_params() -> dict:
    return FAST_PARAMS if _fast else PARAMS

# The most common long passwords and phrases, compared against the letters of the password (case-folded, digits
# and punctuation removed), so "Password12345678!" is caught as well as "password".
COMMON = frozenset("""password passwords passphrase letmein welcome qwertyuiop qwertyuiopasdfgh asdfghjkl zxcvbnm
iloveyou admin administrator changeme trustno1 monkey dragon football baseball superman batman master sunshine
princess shadow michael jennifer computer internet abcdefg abcdefghijklmnop correcthorsebatterystaple
correcthorse batterystaple thequickbrownfox thequickbrownfoxjumpsoverthelazydog helloworld whatever nothing
starwars pokemon secret access login default guest root user test testing example sample temporary temp
opsatlas tiberius tibi operator knowledgedemo knowledge demo welcometoopsatlas""".split())
CONTEXT = ("opsatlas", "tiberius", "tibi", "operator")


def normalise(password: str) -> str:
    return unicodedata.normalize("NFC", password)


def _letters(password: str) -> str:
    return re.sub(r"[^a-z]", "", password.casefold())


def problems(password: str, *, login: str = "", display_name: str = "") -> list[str]:
    """Why a password is not acceptable; an empty list means it is."""
    password = normalise(password)
    found: list[str] = []
    if len(password) < MIN_LENGTH:
        found.append(f"Use at least {MIN_LENGTH} characters; a sentence or a few words work well.")
    if len(password) > MAX_LENGTH:
        found.append(f"Use at most {MAX_LENGTH} characters.")
    if found:
        return found
    letters = _letters(password)
    if letters in COMMON or any(letters == word * n for word in COMMON for n in (2, 3)):
        found.append("That password is too common.")
    for unit in range(1, 5):
        if len(password) % unit == 0 and password == password[:unit] * (len(password) // unit):
            found.append("That password repeats one short pattern.")
            break
    digits = re.sub(r"\D", "", password)
    if len(digits) == len(password) and (digits in "01234567890123456789" or digits in "98765432109876543210"):
        found.append("That password is a number sequence.")
    words = [w for w in re.split(r"[^a-z]+", (login.split("@")[0] + " " + display_name).casefold()) if len(w) >= 4]
    if any(w in password.casefold() for w in words + list(CONTEXT)):
        found.append("Do not use your name, your login or the product's name in the password.")
    return found


def hash_password(password: str) -> str:
    return _hasher.hash(normalise(password))


def verify(stored: str, password: str) -> tuple[bool, bool]:
    """(matches, needs a rehash under the current parameters)."""
    try:
        _hasher.verify(stored, normalise(password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False, False
    return True, (not _fast and _hasher.check_needs_rehash(stored))


def dummy_verify(password: str) -> None:
    """The same work as a real check, for an account that does not exist."""
    verify(_DUMMY, password)
