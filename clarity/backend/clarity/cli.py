"""Command line entry points.

Two jobs: print the analysis in a terminal (a demo that works even if the API
or the browser does not), and freeze fixtures so the frontend and the tests have
a stable payload to work against.

    python -m clarity.cli book
    python -m clarity.cli client CL-0014
    python -m clarity.cli brief CL-0014
    python -m clarity.cli fixtures
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import config
from .dossier import all_events, book_view, client_dossier
from .loaders import get_book

DEMO_CLIENTS = ("CL-0014", "CL-0002", "CL-0017", "CL-0003", "CL-0005")


def _rule(char: str = "-", width: int = 96) -> str:
    return char * width


def print_book() -> None:
    view = book_view()
    print(_rule("="))
    print(f"CLARITY - {view['rm']['rm_name']} - book as at {view['as_of']}")
    print(
        f"{view['totals']['clients']} clients - USD {view['totals']['aum_usd']:,.0f} - "
        f"{view['totals']['insights']} open findings "
        f"({view['totals']['critical']} critical, {view['totals']['high']} high)"
    )
    print(_rule("="))
    for row in view["clients"]:
        print(
            f"{row['rank']:>2}. {row['priority_score']:5.1f}  "
            f"{row['client_id']}  {row['client_name'][:30]:30}  "
            f"USD {row['total_usd']:>13,.0f}  {row['top_severity']:8}"
        )
        print(f"      {row['top_headline']}")
        print(f"      why: {' | '.join(row['why_now'])}")
    print()
    print("Ranking:", view["scoring"]["formula"])
    print("        ", view["scoring"]["note"])


def print_client(client_id: str) -> None:
    dossier = client_dossier(client_id)
    client = dossier["client"]
    print(_rule("="))
    print(f"{client['client_name']} ({client_id})")
    print(
        f"{client['risk_profile']} - {client['wealth_band']} - "
        f"{client['booking_centre']} - base {client['base_currency']} - "
        f"tax domicile {client['tax_domicile']}"
    )
    print(f"Objectives: {client['objectives']}")
    print(f"Household:  USD {dossier['wealth']['total_usd']:,.0f}")
    print(_rule("="))

    print("\nWHAT CHANGED AND WHY")
    for sentence in dossier["explanation"]["ytd"]["narrative"]:
        print(f"  {sentence}")

    print("\nEXPOSURE, LOOKED THROUGH")
    for exposure in dossier["exposures"]["issuers"][:4]:
        if len(exposure["legs"]) < 2:
            continue
        print(
            f"  {exposure['name']}: USD {exposure['attributed_usd']:,.0f} "
            f"({exposure['pct_of_household']:.1f}% of household) across "
            f"{len(exposure['legs'])} line items"
        )
        for leg in exposure["legs"]:
            print(
                f"      - {leg['instrument_name'][:52]:52} "
                f"USD {leg['attributed_usd']:>12,.0f}  via {leg['basis_field']}"
            )

    print("\nFINDINGS")
    for insight in dossier["insights"]:
        print(
            f"  [{insight['priority_score']:5.1f}] {insight['severity'].upper():8} "
            f"{insight['category']:14} {insight['headline']}"
        )
        print(f"          {insight['summary'][:180]}")
        options = dossier["options"].get(insight["id"], [])
        for option in options:
            print(f"          option: {option['label']}")
        print(f"          evidence: {len(insight['evidence'])} source rows")

    print("\nLIQUIDITY")
    liquidity = dossier["liquidity"]
    print(
        f"  readily realisable USD {liquidity['readily_realisable_usd']:,.0f} | "
        f"withdrawable USD {liquidity['withdrawable_usd']:,.0f} | "
        f"obligations USD {liquidity['obligations_total_usd']:,.0f} | "
        f"cover {liquidity['coverage_ratio']}"
    )
    for note in liquidity["notes"]:
        print(f"  note: {note}")


def print_brief(client_id: str) -> None:
    brief = client_dossier(client_id)["brief"]
    print(_rule("="))
    print(f"MEETING BRIEF - {client_id} - as at {brief['as_of']}")
    print(_rule("="))
    print(f"\nPurpose\n  {brief['purpose']}")
    print("\nWhat to say")
    for point in brief["talking_points"]:
        print(f"  - {point}")
    print("\nWhat to ask")
    for question in brief["questions_to_ask"]:
        print(f"  - {question}")
    if brief["contradictions"]:
        print("\nWhere the file disagrees with itself")
        for item in brief["contradictions"]:
            print(f"  - {item}")
    print("\nWhat not to say")
    for item in brief["do_not_say"]:
        print(f"  - {item}")
    print("\nDraft follow-up")
    for line in brief["draft_follow_up"].splitlines():
        print(f"  {line}")


def write_fixtures(destination: Path | None = None) -> None:
    """Freeze payloads so the UI and tests have something stable to work with."""
    target = destination or config.FIXTURES_DIR
    target.mkdir(parents=True, exist_ok=True)

    (target / "book.json").write_text(
        json.dumps(book_view(), indent=2, default=str), encoding="utf-8"
    )
    (target / "events.json").write_text(
        json.dumps(all_events(), indent=2, default=str), encoding="utf-8"
    )
    for client_id in DEMO_CLIENTS:
        (target / f"client_{client_id}.json").write_text(
            json.dumps(client_dossier(client_id), indent=2, default=str),
            encoding="utf-8",
        )
    print(f"Wrote {2 + len(DEMO_CLIENTS)} fixtures to {target}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="clarity", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("book", help="Print the ranked book")
    client = sub.add_parser("client", help="Print one client dossier")
    client.add_argument("client_id")
    brief = sub.add_parser("brief", help="Print one client's meeting brief")
    brief.add_argument("client_id")
    fixtures = sub.add_parser("fixtures", help="Freeze JSON payloads")
    fixtures.add_argument("--out", type=Path, default=None)

    args = parser.parse_args()
    get_book()

    if args.command == "book":
        print_book()
    elif args.command == "client":
        print_client(args.client_id)
    elif args.command == "brief":
        print_brief(args.client_id)
    elif args.command == "fixtures":
        write_fixtures(args.out)


if __name__ == "__main__":
    main()
