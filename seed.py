"""Seed the document store with generated contracts.

Generates contracts from 4 templates (NDA, MSA, Services Agreement,
License Agreement) with randomized counterparty names, effective dates,
and governing states. About 15% of contracts get a second, negotiated
revision that swaps in a deliberately non-standard indemnification or
limitation-of-liability clause — exercising the `edits` history table.

The current text of a document is always the `edits` row with the
highest `change_id` ("version") for that `doc_id`; `docs.content` is
kept in sync with that row so reads don't need a join.

Uses only the stdlib `sqlite3` module — no ORM.

Usage:
    python seed.py [--count 300] [--db-path assessment.db] [--seed 42]
"""

import argparse
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from app.db import DEFAULT_DB_PATH, SCHEMA_PATH, get_connection

# ---------------------------------------------------------------------------
# Randomized field generators
# ---------------------------------------------------------------------------

COMPANY_ADJECTIVES = [
    "Blue", "Summit", "Cedar", "Northgate", "Silver", "Redwood", "Harbor",
    "Pinnacle", "Crestline", "Vertex", "Meridian", "Lodestar", "Ironwood",
    "Brightline", "Anchor", "Granite", "Bluewave", "Highfield", "Cobalt",
    "Windmere",
]

COMPANY_NOUNS = [
    "Technologies", "Solutions", "Partners", "Industries", "Systems",
    "Holdings", "Ventures", "Dynamics", "Logistics", "Consulting",
    "Analytics", "Media", "Networks", "Capital", "Robotics", "Biosciences",
    "Energy", "Interactive", "Labs", "Materials",
]

COMPANY_SUFFIXES = ["Inc.", "LLC", "Corp.", "Ltd.", "Co."]

US_STATES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming",
]

DATE_RANGE_START = date(2021, 1, 1)
DATE_RANGE_END = date(2026, 7, 19)


def random_company_name(rng: random.Random) -> str:
    """Generate a plausible, randomized company name.

    Args:
        rng: Source of randomness to use.

    Returns:
        A name like "Cedar Analytics LLC".
    """
    return (
        f"{rng.choice(COMPANY_ADJECTIVES)} {rng.choice(COMPANY_NOUNS)} "
        f"{rng.choice(COMPANY_SUFFIXES)}"
    )


def random_counterparties(rng: random.Random) -> tuple[str, str]:
    """Generate two distinct company names.

    Args:
        rng: Source of randomness to use.

    Returns:
        A (party_a, party_b) pair of distinct company names.
    """
    party_a = random_company_name(rng)
    party_b = random_company_name(rng)
    while party_b == party_a:
        party_b = random_company_name(rng)
    return party_a, party_b


def random_effective_date(rng: random.Random) -> str:
    """Generate a random effective date within DATE_RANGE.

    Args:
        rng: Source of randomness to use.

    Returns:
        An ISO-formatted (YYYY-MM-DD) date string.
    """
    span_days = (DATE_RANGE_END - DATE_RANGE_START).days
    return str(DATE_RANGE_START + timedelta(days=rng.randint(0, span_days)))


# ---------------------------------------------------------------------------
# Indemnification / limitation-of-liability clauses
# ---------------------------------------------------------------------------

STANDARD_INDEMNIFICATION = (
    "Each party shall indemnify, defend, and hold harmless the other party "
    "and its officers, directors, employees, and agents from and against "
    "any and all third-party claims, damages, losses, and reasonable "
    "expenses (including reasonable attorneys' fees) arising out of or "
    "resulting from the indemnifying party's breach of this Agreement or "
    "its negligent acts or omissions, provided that the indemnified party "
    "gives prompt written notice of any such claim."
)

NONSTANDARD_INDEMNIFICATION_VARIANTS = [
    "{party_b} shall indemnify, defend, and hold harmless {party_a}, its "
    "affiliates, officers, and employees from any and all claims "
    "whatsoever, without limitation, including claims arising from "
    "{party_a}'s own negligence or willful misconduct, with no cap on the "
    "amount of indemnifiable losses.",
    "Except as expressly required by applicable law, neither party shall "
    "have any obligation to indemnify the other party under this "
    "Agreement.",
    "{party_b} shall indemnify, defend, and hold harmless {party_a} from "
    "any and all claims of any kind, including claims for intellectual "
    "property infringement, personal injury, and property damage, "
    "regardless of the cause and regardless of whether {party_a} was "
    "itself negligent.",
]

STANDARD_LIMITATION_OF_LIABILITY = (
    "IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY ARISING OUT OF "
    "OR RELATED TO THIS AGREEMENT EXCEED THE TOTAL FEES PAID OR PAYABLE "
    "UNDER THIS AGREEMENT IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM. "
    "IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, "
    "INCIDENTAL, CONSEQUENTIAL, SPECIAL, OR PUNITIVE DAMAGES, EVEN IF "
    "ADVISED OF THE POSSIBILITY OF SUCH DAMAGES."
)

NONSTANDARD_LIMITATION_OF_LIABILITY_VARIANTS = [
    "{party_b}'s aggregate liability under this Agreement shall be "
    "UNCAPPED and shall include all direct, indirect, incidental, "
    "consequential, special, and punitive damages, without limitation.",
    "IN NO EVENT SHALL {party_a}'s AGGREGATE LIABILITY UNDER THIS "
    "AGREEMENT EXCEED ONE HUNDRED DOLLARS ($100), REGARDLESS OF THE FORM "
    "OF ACTION, WHETHER IN CONTRACT, TORT, OR OTHERWISE.",
    "This Agreement contains no limitation of liability. Each party shall "
    "be fully liable for all damages of any kind, including indirect, "
    "consequential, and punitive damages, arising from this Agreement.",
]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_SIGNATURE_BLOCK = """
IN WITNESS WHEREOF, the parties have executed this Agreement as of the
Effective Date first written above.

{party_a}                              {party_b}

By: _______________________            By: _______________________
Name:                                  Name:
Title:                                 Title:
"""

_GOVERNING_LAW_SECTION = """
GOVERNING LAW
This Agreement shall be governed by and construed in accordance with the
laws of the State of {governing_state}, without regard to its conflict of
laws principles.
"""


def _nda_template() -> str:
    return """MUTUAL NON-DISCLOSURE AGREEMENT

This Mutual Non-Disclosure Agreement ("Agreement") is entered into as of
{effective_date} (the "Effective Date") by and between {party_a}
("Disclosing Party") and {party_b} ("Receiving Party").

1. CONFIDENTIAL INFORMATION
"Confidential Information" means any non-public information disclosed by
either party to the other, whether orally, in writing, or in any other
form, that is designated as confidential or that reasonably should be
understood to be confidential given the nature of the information.

2. OBLIGATIONS OF RECEIVING PARTY
The Receiving Party shall use the Confidential Information solely to
evaluate a potential business relationship between the parties, and shall
not disclose such information to any third party without the Disclosing
Party's prior written consent.

3. TERM
This Agreement shall remain in effect for a period of three (3) years
from the Effective Date, unless earlier terminated by either party upon
thirty (30) days' written notice.

4. INDEMNIFICATION
{indemnification_clause}

5. LIMITATION OF LIABILITY
{limitation_of_liability_clause}
""" + _GOVERNING_LAW_SECTION + _SIGNATURE_BLOCK


def _msa_template() -> str:
    return """MASTER SERVICES AGREEMENT

This Master Services Agreement ("Agreement") is entered into as of
{effective_date} (the "Effective Date") by and between {party_a}
("Company") and {party_b} ("Contractor").

1. SERVICES
Contractor shall provide the services described in one or more Statements
of Work ("SOWs") executed by both parties and incorporated herein by
reference.

2. FEES AND PAYMENT
Company shall pay Contractor the fees set forth in each applicable SOW
within thirty (30) days of receipt of a correct invoice.

3. TERM AND TERMINATION
This Agreement shall commence on the Effective Date and continue until
terminated by either party upon sixty (60) days' written notice.

4. INTELLECTUAL PROPERTY
All work product created by Contractor under an SOW shall be a
"work made for hire" and shall be owned exclusively by Company upon full
payment therefor.

5. INDEMNIFICATION
{indemnification_clause}

6. LIMITATION OF LIABILITY
{limitation_of_liability_clause}
""" + _GOVERNING_LAW_SECTION + _SIGNATURE_BLOCK


def _services_agreement_template() -> str:
    return """SERVICES AGREEMENT

This Services Agreement ("Agreement") is entered into as of
{effective_date} (the "Effective Date") by and between {party_a}
("Client") and {party_b} ("Service Provider").

1. SCOPE OF SERVICES
Service Provider shall perform the services described in Exhibit A
attached hereto (the "Services") in a professional and workmanlike
manner consistent with industry standards.

2. COMPENSATION
Client shall pay Service Provider the fees set forth in Exhibit A
according to the payment schedule specified therein.

3. INDEPENDENT CONTRACTOR
Service Provider is an independent contractor and not an employee, agent,
or partner of Client for any purpose.

4. TERM AND TERMINATION
This Agreement shall commence on the Effective Date and continue for one
(1) year, automatically renewing for successive one (1) year terms unless
either party provides notice of non-renewal at least thirty (30) days
prior to the end of the then-current term.

5. INDEMNIFICATION
{indemnification_clause}

6. LIMITATION OF LIABILITY
{limitation_of_liability_clause}
""" + _GOVERNING_LAW_SECTION + _SIGNATURE_BLOCK


def _license_agreement_template() -> str:
    return """SOFTWARE LICENSE AGREEMENT

This Software License Agreement ("Agreement") is entered into as of
{effective_date} (the "Effective Date") by and between {party_a}
("Licensor") and {party_b} ("Licensee").

1. LICENSE GRANT
Subject to the terms of this Agreement, Licensor grants Licensee a
non-exclusive, non-transferable license to use Licensor's software
solely for Licensee's internal business purposes.

2. ROYALTIES
Licensee shall pay Licensor the royalties set forth in Schedule 1,
payable quarterly in arrears within thirty (30) days of the end of each
calendar quarter.

3. RESTRICTIONS
Licensee shall not sublicense, reverse engineer, or distribute the
licensed software except as expressly permitted by this Agreement.

4. TERM AND TERMINATION
This Agreement shall remain in effect for a period of two (2) years from
the Effective Date, unless earlier terminated in accordance with this
Agreement.

5. INDEMNIFICATION
{indemnification_clause}

6. LIMITATION OF LIABILITY
{limitation_of_liability_clause}
""" + _GOVERNING_LAW_SECTION + _SIGNATURE_BLOCK


TEMPLATES: dict[str, str] = {
    "NDA": _nda_template(),
    "MSA": _msa_template(),
    "Services Agreement": _services_agreement_template(),
    "License Agreement": _license_agreement_template(),
}

NONSTANDARD_CLAUSE_PROBABILITY = 0.15


def render_contract(
    template_key: str,
    party_a: str,
    party_b: str,
    effective_date: str,
    governing_state: str,
    indemnification_clause: str,
    limitation_of_liability_clause: str,
) -> str:
    """Fill in a contract template with the given field values.

    Args:
        template_key: One of the keys in `TEMPLATES`.
        party_a: Name of the first counterparty.
        party_b: Name of the second counterparty.
        effective_date: ISO-formatted effective date.
        governing_state: US state whose law governs the contract.
        indemnification_clause: Text of the indemnification section, with
            `{party_a}`/`{party_b}` placeholders already resolved.
        limitation_of_liability_clause: Text of the limitation-of-liability
            section, with `{party_a}`/`{party_b}` placeholders already
            resolved.

    Returns:
        The fully rendered contract text.
    """
    return TEMPLATES[template_key].format(
        party_a=party_a,
        party_b=party_b,
        effective_date=effective_date,
        governing_state=governing_state,
        indemnification_clause=indemnification_clause,
        limitation_of_liability_clause=limitation_of_liability_clause,
    )


def generate_contract(rng: random.Random, template_key: str) -> tuple[str, str, str | None]:
    """Generate one contract's title, standard text, and (maybe) revised text.

    ~15% of contracts get a second, negotiated version in which either the
    indemnification clause or the limitation-of-liability clause is
    replaced with a deliberately non-standard variant — everything else
    stays identical between the two versions.

    Args:
        rng: Source of randomness to use.
        template_key: One of the keys in `TEMPLATES`.

    Returns:
        A `(title, standard_text, revised_text)` tuple. `revised_text` is
        `None` for the ~85% of contracts that only ever had one version.
    """
    party_a, party_b = random_counterparties(rng)
    effective_date = random_effective_date(rng)
    governing_state = rng.choice(US_STATES)
    title = f"{template_key} — {party_a} / {party_b}"

    standard_text = render_contract(
        template_key,
        party_a,
        party_b,
        effective_date,
        governing_state,
        STANDARD_INDEMNIFICATION,
        STANDARD_LIMITATION_OF_LIABILITY,
    )

    if rng.random() >= NONSTANDARD_CLAUSE_PROBABILITY:
        return title, standard_text, None

    indemnification_clause = STANDARD_INDEMNIFICATION
    limitation_of_liability_clause = STANDARD_LIMITATION_OF_LIABILITY
    if rng.choice(["indemnification", "limitation_of_liability"]) == "indemnification":
        indemnification_clause = rng.choice(
            NONSTANDARD_INDEMNIFICATION_VARIANTS
        ).format(party_a=party_a, party_b=party_b)
    else:
        limitation_of_liability_clause = rng.choice(
            NONSTANDARD_LIMITATION_OF_LIABILITY_VARIANTS
        ).format(party_a=party_a, party_b=party_b)

    revised_text = render_contract(
        template_key,
        party_a,
        party_b,
        effective_date,
        governing_state,
        indemnification_clause,
        limitation_of_liability_clause,
    )
    return title, standard_text, revised_text


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------


def reset_schema(conn: sqlite3.Connection) -> None:
    """Drop and recreate docs/edits/docs_fts so seeding starts from empty tables.

    Args:
        conn: Open SQLite connection.
    """
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS edits_sync_fts;
        DROP TRIGGER IF EXISTS docs_soft_delete_sync_fts;
        DROP TABLE IF EXISTS docs_fts;
        DROP TABLE IF EXISTS edits;
        DROP TABLE IF EXISTS docs;
        """
    )
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


def insert_contract(
    conn: sqlite3.Connection, title: str, standard_text: str, revised_text: str | None
) -> int:
    """Insert one seeded contract and its edit history.

    The document's current text (`docs.content`) always matches the
    highest-`change_id` row in `edits` for that document: version 1 is the
    as-signed standard draft, and version 2 (when present) is the
    negotiated revision with a non-standard clause. The FTS5 index is kept
    in sync automatically by the `edits_sync_fts` trigger (see
    schema.sql) as each edits row below is inserted.

    Args:
        conn: Open SQLite connection.
        title: Document title.
        standard_text: Version 1 (as-signed) contract text.
        revised_text: Version 2 (negotiated) contract text, or `None` if
            this contract was never revised.

    Returns:
        The new document's doc_id.
    """
    current_text = revised_text if revised_text is not None else standard_text

    cur = conn.execute(
        "INSERT INTO docs (title, content) VALUES (?, ?)", (title, current_text)
    )
    doc_id = cur.lastrowid

    conn.execute(
        "INSERT INTO edits (doc_id, change_id, current_text) VALUES (?, 1, ?)",
        (doc_id, standard_text),
    )
    if revised_text is not None:
        conn.execute(
            "INSERT INTO edits (doc_id, change_id, current_text) VALUES (?, 2, ?)",
            (doc_id, revised_text),
        )
    return doc_id


def seed(conn: sqlite3.Connection, count: int, rng: random.Random) -> dict[str, int]:
    """Generate and insert `count` contracts, evenly spread across templates.

    Args:
        conn: Open SQLite connection.
        count: Number of contracts to generate.
        rng: Source of randomness to use.

    Returns:
        Summary counts: `total`, `revised` (contracts with a non-standard
        v2), and one entry per template key with how many were generated.
    """
    template_keys = list(TEMPLATES.keys())
    assignments = [template_keys[i % len(template_keys)] for i in range(count)]
    rng.shuffle(assignments)

    summary = {"total": 0, "revised": 0, **{key: 0 for key in template_keys}}
    for template_key in assignments:
        title, standard_text, revised_text = generate_contract(rng, template_key)
        insert_contract(conn, title, standard_text, revised_text)
        summary["total"] += 1
        summary[template_key] += 1
        if revised_text is not None:
            summary["revised"] += 1
    conn.commit()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=300, help="Number of contracts to generate")
    parser.add_argument("--db-path", type=Path, default=None, help="SQLite DB file (defaults to app's DEFAULT_DB_PATH)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    conn = get_connection(args.db_path or DEFAULT_DB_PATH)
    try:
        reset_schema(conn)
        summary = seed(conn, args.count, rng)
    finally:
        conn.close()

    print(f"Seeded {summary['total']} contracts:")
    for key in TEMPLATES:
        print(f"  {key}: {summary[key]}")
    pct = 100 * summary["revised"] / summary["total"]
    print(f"  Non-standard clause revisions: {summary['revised']} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
