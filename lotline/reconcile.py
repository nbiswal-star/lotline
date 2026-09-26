"""Runtime reconciliation of the Treasury snapshot against the City advertisement.

Pure functions only: no file access, no pandas. The loader calls ``reconcile``
once at startup and stores the result on the ``Snapshot``.

Parcel identifier formats
-------------------------
A County PIN is 16 characters: ``MMMM`` map (4 digits), ``B`` block (1 letter),
``LLLLL`` lot (5 digits), ``SSSS`` supplemental lot (4 characters) and ``CC``
card (2 digits).

The City advertisement lists an *account* instead: ``1`` + a 2-digit ward
prefix + the same map/block/lot, followed either by the full 6-character
supplement+card, or by an abbreviated supplement, a space, and the card.
The abbreviated supplement is padded back to 4 characters:

- blank           -> ``0000``
- digits only     -> zero-filled on the left (``12`` -> ``0012``)
- letter + digits -> letter, then digits zero-filled (``B3`` -> ``B003``)
- letters only    -> zero-filled on the left (``A`` -> ``000A``)

These padding rules were derived from the advertisement rows themselves. The
loader asserts that every account-derived PIN equals the advertisement's own
``pin`` column, so a rule that does not fit the data fails loudly at startup.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from lotline.models import AdvertRecord, Reconciliation, TreasuryRecord

PIN_PATTERN = re.compile(r"^\d{4}[A-Z]\d{5}[0-9A-Z]{4}\d{2}$")

# 1 + ward (2 digits) + map + block + lot, then either the full 6-character
# supplement+card or "<abbreviated supplement><space(s)><card>".
_ACCOUNT_PATTERN = re.compile(
    r"^1(?P<ward>\d{2})(?P<map>\d{4})(?P<block>[A-Z])(?P<lot>\d{5})"
    r"(?:(?P<supp_full>[0-9A-Z]{4})(?P<card_full>\d{2})"
    r"|(?P<supp>[0-9A-Z]{0,4})\s+(?P<card>\d{2}))$"
)

PRICE_TOLERANCE_USD = 0.01


def normalize_supplement(text: str) -> str | None:
    """Pad an abbreviated supplemental-lot code to its 4-character PIN form.

    Returns None when the code does not follow one of the documented shapes.
    """
    s = text.strip().upper()
    if len(s) > 4:
        return None
    if s == "" or s.isdigit():
        return s.zfill(4)
    m = re.fullmatch(r"([A-Z]+)(\d*)", s)
    if m is None:
        return None
    letters, digits = m.groups()
    if not digits:
        return letters.rjust(4, "0")
    return letters + digits.zfill(4 - len(letters))


def pin_from_parts(map_no: str, block: str, lot: str, supp: str = "", card: str = "") -> str | None:
    """Assemble a 16-character PIN from its parts, zero-padding each segment.

    Returns None if any segment is malformed or too long.
    """
    if not (map_no.isdigit() and len(map_no) <= 4):
        return None
    if not (len(block) == 1 and block.isalpha()):
        return None
    if not (lot.isdigit() and len(lot) <= 5):
        return None
    supp_norm = normalize_supplement(supp)
    if supp_norm is None:
        return None
    if card and not (card.isdigit() and len(card) <= 2):
        return None
    pin = map_no.zfill(4) + block.upper() + lot.zfill(5) + supp_norm + (card or "").zfill(2)
    return pin if PIN_PATTERN.match(pin) else None


def account_to_pin(account: str) -> str | None:
    """Convert a City advertisement account number to a County PIN.

    The account is the PIN with a ``1`` + 2-digit ward prefix; see the module
    docstring for the abbreviated-supplement form. Returns None if the account
    does not parse (never guesses).
    """
    m = _ACCOUNT_PATTERN.match(account.strip().upper())
    if m is None:
        return None
    if m["supp_full"] is not None:
        return pin_from_parts(m["map"], m["block"], m["lot"], m["supp_full"], m["card_full"])
    return pin_from_parts(m["map"], m["block"], m["lot"], m["supp"], m["card"])


def account_ward(account: str) -> str | None:
    """The ward encoded in an advertisement account prefix (e.g. ``"4"``), or None."""
    m = _ACCOUNT_PATTERN.match(account.strip().upper())
    return str(int(m["ward"])) if m else None


def account_pin_mismatches(advert: Mapping[str, AdvertRecord]) -> frozenset[str]:
    """Advertisement PINs whose account number does not normalize to that same PIN."""
    return frozenset(pin for pin, rec in advert.items() if account_to_pin(rec.account) != rec.pin)


def prices_agree(upset: float, total_tax_due: float) -> bool:
    """Advertised upset price equals Treasury total tax due within one cent."""
    return abs(upset - total_tax_due) <= PRICE_TOLERANCE_USD + 1e-9


def reconcile(
    treasury: Mapping[str, TreasuryRecord], advert: Mapping[str, AdvertRecord]
) -> Reconciliation:
    """Match Treasury candidates to advertised accounts by PIN.

    An advertised record counts as matched only when its account number
    independently normalizes to its PIN *and* that PIN is in the Treasury
    snapshot. Price checks run on matched PINs only.
    """
    bad_accounts = account_pin_mismatches(advert)
    advert_pins = frozenset(advert) - bad_accounts
    treasury_pins = frozenset(treasury)
    matched = treasury_pins & advert_pins
    passed = frozenset(
        pin for pin in matched if prices_agree(advert[pin].upset, treasury[pin].total_tax_due)
    )
    return Reconciliation(
        treasury_count=len(treasury),
        advertised_count=len(advert),
        matched_pins=matched,
        unmatched_treasury_pins=treasury_pins - matched,
        unmatched_advert_pins=frozenset(advert) - matched,
        price_check_pass=passed,
        price_check_fail=matched - passed,
    )
