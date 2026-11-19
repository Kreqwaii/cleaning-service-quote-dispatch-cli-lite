#!/usr/bin/env python3
"""Zero-dependency CLI quote & crew dispatch calculator for cleaning services."""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence

__version__ = "1.0.0"

CLEANING_TYPES: Dict[str, Dict[str, float]] = {
    "standard": {
        "rate_per_sqm": 1.60,
        "hours_per_100sqm": 2.4,
        "min_price": 75.0,
    },
    "deep": {
        "rate_per_sqm": 2.85,
        "hours_per_100sqm": 4.2,
        "min_price": 140.0,
    },
    "post_renovation": {
        "rate_per_sqm": 4.10,
        "hours_per_100sqm": 6.0,
        "min_price": 210.0,
    },
    "move_in_out": {
        "rate_per_sqm": 3.40,
        "hours_per_100sqm": 5.0,
        "min_price": 175.0,
    },
    "office": {
        "rate_per_sqm": 1.45,
        "hours_per_100sqm": 2.0,
        "min_price": 90.0,
    },
}

BATHROOM_PRICE = 22.0
BATHROOM_HOURS = 0.65
WINDOW_PRICE = 9.5
WINDOW_HOURS = 0.25
OVEN_PRICE = 28.0
OVEN_HOURS = 0.75
FRIDGE_PRICE = 24.0
FRIDGE_HOURS = 0.60

URGENCY_MULTIPLIERS: Dict[str, float] = {
    "normal": 1.00,
    "same_day": 1.25,
    "weekend": 1.15,
}

FREQUENCY_DISCOUNTS: Dict[str, float] = {
    "one_time": 0.00,
    "weekly": 0.15,
    "biweekly": 0.10,
    "monthly": 0.05,
}


@dataclass
class QuoteRequest:
    area_sqm: float
    cleaning_type: str = "standard"
    bathrooms: int = 1
    windows: int = 0
    include_oven: bool = False
    include_fridge: bool = False
    urgency: str = "normal"
    frequency: str = "one_time"
    hourly_crew_capacity: float = 8.0
    job_id: str = "JOB-001"
    client_name: str = "Walk-in Client"
    zone: str = "Central"


@dataclass
class QuoteResult:
    job_id: str
    client_name: str
    zone: str
    cleaning_type: str
    area_sqm: float
    bathrooms: int
    windows: int
    base_price: float
    extras_price: float
    urgency_multiplier: float
    discount_rate: float
    total_price: float
    estimated_man_hours: float
    recommended_crew_size: int
    estimated_duration_hours: float
    breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class DispatchAssignment:
    crew_id: str
    zone: str
    jobs: List[str]
    total_man_hours: float
    total_revenue: float
    utilization_pct: float


def validate_request(req: QuoteRequest) -> None:
    if req.area_sqm <= 0:
        raise ValueError("area_sqm must be greater than 0")
    if req.cleaning_type not in CLEANING_TYPES:
        raise ValueError(
            f"Unsupported cleaning_type '{req.cleaning_type}'. "
            f"Choose from: {', '.join(sorted(CLEANING_TYPES))}"
        )
    if req.bathrooms < 0:
        raise ValueError("bathrooms cannot be negative")
    if req.windows < 0:
        raise ValueError("windows cannot be negative")
    if req.urgency not in URGENCY_MULTIPLIERS:
        raise ValueError(
            f"Unsupported urgency '{req.urgency}'. "
            f"Choose from: {', '.join(sorted(URGENCY_MULTIPLIERS))}"
        )
    if req.frequency not in FREQUENCY_DISCOUNTS:
        raise ValueError(
            f"Unsupported frequency '{req.frequency}'. "
            f"Choose from: {', '.join(sorted(FREQUENCY_DISCOUNTS))}"
        )
    if req.hourly_crew_capacity <= 0:
        raise ValueError("hourly_crew_capacity must be greater than 0")


def calculate_quote(req: QuoteRequest) -> QuoteResult:
    validate_request(req)

    cfg = CLEANING_TYPES[req.cleaning_type]
    raw_area_price = req.area_sqm * cfg["rate_per_sqm"]
    base_price = max(raw_area_price, cfg["min_price"])

    bathroom_cost = req.bathrooms * BATHROOM_PRICE
    window_cost = req.windows * WINDOW_PRICE
    oven_cost = OVEN_PRICE if req.include_oven else 0.0
    fridge_cost = FRIDGE_PRICE if req.include_fridge else 0.0
    extras_price = bathroom_cost + window_cost + oven_cost + fridge_cost

    urgency_mult = URGENCY_MULTIPLIERS[req.urgency]
    discount_rate = FREQUENCY_DISCOUNTS[req.frequency]

    subtotal = (base_price + extras_price) * urgency_mult
    total_price = round(subtotal * (1.0 - discount_rate), 2)

    area_hours = (req.area_sqm / 100.0) * cfg["hours_per_100sqm"]
    extras_hours = (
        req.bathrooms * BATHROOM_HOURS
        + req.windows * WINDOW_HOURS
        + (OVEN_HOURS if req.include_oven else 0.0)
        + (FRIDGE_HOURS if req.include_fridge else 0.0)
    )
    estimated_man_hours = round(max(1.0, area_hours + extras_hours), 2)

    # Recommend 1 cleaner per 4 man-hours, capped at 6 for residential/light commercial
    recommended_crew_size = max(1, min(6, math.ceil(estimated_man_hours / 4.0)))
    estimated_duration_hours = round(estimated_man_hours / recommended_crew_size, 2)

    breakdown = {
        "area_base": round(base_price, 2),
        "bathrooms": round(bathroom_cost, 2),
        "windows": round(window_cost, 2),
        "oven": round(oven_cost, 2),
        "fridge": round(fridge_cost, 2),
        "urgency_surcharge": round((base_price + extras_price) * (urgency_mult - 1.0), 2),
        "frequency_discount": round(subtotal * discount_rate, 2),
    }

    return QuoteResult(
        job_id=req.job_id,
        client_name=req.client_name,
        zone=req.zone,
        cleaning_type=req.cleaning_type,
        area_sqm=round(req.area_sqm, 2),
        bathrooms=req.bathrooms,
        windows=req.windows,
        base_price=round(base_price, 2),
        extras_price=round(extras_price, 2),
        urgency_multiplier=urgency_mult,
        discount_rate=discount_rate,
        total_price=total_price,
        estimated_man_hours=estimated_man_hours,
        recommended_crew_size=recommended_crew_size,
        estimated_duration_hours=estimated_duration_hours,
        breakdown=breakdown,
    )


def dispatch_crews(
    quotes: Sequence[QuoteResult],
    num_crews: int = 2,
    max_hours_per_crew: float = 10.0,
) -> List[DispatchAssignment]:
    if num_crews <= 0:
        raise ValueError("num_crews must be greater than 0")
    if max_hours_per_crew <= 0:
        raise ValueError("max_hours_per_crew must be greater than 0")

    crews: List[Dict[str, Any]] = [
        {
            "crew_id": f"CREW-{i + 1:02d}",
            "zones": [],
            "jobs": [],
            "hours": 0.0,
            "revenue": 0.0,
        }
        for i in range(num_crews)
    ]

    # Longest-processing-time-first (LPT) greedy balancing
    sorted_quotes = sorted(
        quotes, key=lambda q: (q.estimated_man_hours, q.total_price), reverse=True
    )

    for quote in sorted_quotes:
        # Prefer crews already in the same zone if capacity allows, else least loaded
        same_zone = [c for c in crews if quote.zone in c["zones"]]
        candidates = same_zone if same_zone else crews
        target = min(candidates, key=lambda c: c["hours"])
        if target["hours"] + quote.estimated_man_hours > max_hours_per_crew:
            target = min(crews, key=lambda c: c["hours"])

        target["jobs"].append(quote.job_id)
        if quote.zone not in target["zones"]:
            target["zones"].append(quote.zone)
        target["hours"] += quote.estimated_man_hours
        target["revenue"] += quote.total_price

    assignments: List[DispatchAssignment] = []
    for crew in crews:
        zone_label = ", ".join(crew["zones"]) if crew["zones"] else "Unassigned"
        util = round((crew["hours"] / max_hours_per_crew) * 100.0, 1)
        assignments.append(
            DispatchAssignment(
                crew_id=crew["crew_id"],
                zone=zone_label,
                jobs=crew["jobs"],
                total_man_hours=round(crew["hours"], 2),
                total_revenue=round(crew["revenue"], 2),
                utilization_pct=util,
            )
        )
    return assignments


def format_quotes_text(quotes: Sequence[QuoteResult]) -> str:
    lines: List[str] = []
    for q in quotes:
        lines.append(
            f"[{q.job_id}] {q.client_name} ({q.zone}) | {q.cleaning_type} | "
            f"{q.area_sqm} sqm | {q.bathrooms} bath | {q.windows} win"
        )
        lines.append(
            f"  Total: ${q.total_price:.2f} | Man-Hours: {q.estimated_man_hours:.2f}h | "
            f"Crew: {q.recommended_crew_size} | Est. Duration: {q.estimated_duration_hours:.2f}h"
        )
    return "\n".join(lines)


def format_dispatch_text(assignments: Sequence[DispatchAssignment]) -> str:
    lines = ["=== CREW DISPATCH SCHEDULE ==="]
    for a in assignments:
        jobs_str = ", ".join(a.jobs) if a.jobs else "None"
        lines.append(
            f"{a.crew_id} | Zone(s): {a.zone} | Jobs: [{jobs_str}] | "
            f"Hours: {a.total_man_hours:.2f}h ({a.utilization_pct:.1f}%) | "
            f"Revenue: ${a.total_revenue:.2f}"
        )
    return "\n".join(lines)


def export_quotes_csv(quotes: Sequence[QuoteResult]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "job_id",
        "client_name",
        "zone",
        "cleaning_type",
        "area_sqm",
        "bathrooms",
        "windows",
        "base_price",
        "extras_price",
        "urgency_multiplier",
        "discount_rate",
        "total_price",
        "estimated_man_hours",
        "recommended_crew_size",
        "estimated_duration_hours",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for q in quotes:
        row = asdict(q)
        row.pop("breakdown", None)
        writer.writerow(row)
    return buf.getvalue().strip()


def export_dispatch_csv(assignments: Sequence[DispatchAssignment]) -> str:
    buf = io.StringIO()
    fieldnames = [
        "crew_id",
        "zone",
        "jobs",
        "total_man_hours",
        "total_revenue",
        "utilization_pct",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for a in assignments:
        row = asdict(a)
        row["jobs"] = ";".join(a.jobs)
        writer.writerow(row)
    return buf.getvalue().strip()


def get_demo_requests() -> List[QuoteRequest]:
    return [
        QuoteRequest(
            job_id="JOB-101",
            client_name="Apex Loft",
            zone="Downtown",
            area_sqm=95.0,
            cleaning_type="deep",
            bathrooms=2,
            windows=6,
            include_oven=True,
            urgency="same_day",
        ),
        QuoteRequest(
            job_id="JOB-102",
            client_name="Northside Dental",
            zone="North",
            area_sqm=180.0,
            cleaning_type="office",
            bathrooms=3,
            windows=10,
            frequency="weekly",
        ),
        QuoteRequest(
            job_id="JOB-103",
            client_name="Maple Residence",
            zone="Downtown",
            area_sqm=68.0,
            cleaning_type="standard",
            bathrooms=1,
            windows=4,
            frequency="biweekly",
        ),
        QuoteRequest(
            job_id="JOB-104",
            client_name="Studio 44 Reno",
            zone="West",
            area_sqm=120.0,
            cleaning_type="post_renovation",
            bathrooms=2,
            windows=8,
            include_fridge=True,
        ),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleaning_dispatch",
        description="Zero-dependency cleaning service quote & crew dispatch calculator.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # quote
    q_parser = sub.add_parser("quote", help="Calculate a single cleaning quote.")
    q_parser.add_argument("--area", type=float, required=True, help="Area in square meters.")
    q_parser.add_argument(
        "--type",
        dest="cleaning_type",
        default="standard",
        choices=sorted(CLEANING_TYPES),
        help="Cleaning type.",
    )
    q_parser.add_argument("--bathrooms", type=int, default=1, help="Number of bathrooms.")
    q_parser.add_argument("--windows", type=int, default=0, help="Number of windows.")
    q_parser.add_argument("--oven", action="store_true", help="Include oven cleaning.")
    q_parser.add_argument("--fridge", action="store_true", help="Include fridge cleaning.")
    q_parser.add_argument(
        "--urgency",
        default="normal",
        choices=sorted(URGENCY_MULTIPLIERS),
        help="Urgency tier.",
    )
    q_parser.add_argument(
        "--frequency",
        default="one_time",
        choices=sorted(FREQUENCY_DISCOUNTS),
        help="Recurring frequency discount.",
    )
    q_parser.add_argument("--job-id", default="JOB-001", help="Job identifier.")
    q_parser.add_argument("--client", default="Walk-in Client", help="Client name.")
    q_parser.add_argument("--zone", default="Central", help="Service zone.")
    q_parser.add_argument(
        "--format",
        dest="output_format",
        default="text",
        choices=["text", "json", "csv"],
        help="Output format.",
    )

    # schedule
    s_parser = sub.add_parser(
        "schedule", help="Dispatch a batch of jobs from a JSON file to crews."
    )
    s_parser.add_argument(
        "--input", required=True, help="Path to JSON file containing list of job objects."
    )
    s_parser.add_argument("--crews", type=int, default=2, help="Number of available crews.")
    s_parser.add_argument(
        "--max-hours", type=float, default=10.0, help="Max man-hours per crew."
    )
    s_parser.add_argument(
        "--format",
        dest="output_format",
        default="text",
        choices=["text", "json", "csv"],
        help="Output format.",
    )

    # demo
    d_parser = sub.add_parser("demo", help="Run a built-in sample quote & dispatch demo.")
    d_parser.add_argument("--crews", type=int, default=2, help="Number of crews.")
    d_parser.add_argument(
        "--format",
        dest="output_format",
        default="text",
        choices=["text", "json", "csv"],
        help="Output format.",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "quote":
        req = QuoteRequest(
            area_sqm=args.area,
            cleaning_type=args.cleaning_type,
            bathrooms=args.bathrooms,
            windows=args.windows,
            include_oven=args.oven,
            include_fridge=args.fridge,
            urgency=args.urgency,
            frequency=args.frequency,
            job_id=args.job_id,
            client_name=args.client,
            zone=args.zone,
        )
        quote = calculate_quote(req)
        if args.output_format == "json":
            print(json.dumps(asdict(quote), indent=2))
        elif args.output_format == "csv":
            print(export_quotes_csv([quote]))
        else:
            print(format_quotes_text([quote]))
        return 0

    if args.command == "schedule":
        with open(args.input, "r", encoding="utf-8") as fh:
            raw_jobs = json.load(fh)
        quotes = [calculate_quote(QuoteRequest(**item)) for item in raw_jobs]
        assignments = dispatch_crews(
            quotes, num_crews=args.crews, max_hours_per_crew=args.max_hours
        )
        if args.output_format == "json":
            payload = {
                "quotes": [asdict(q) for q in quotes],
                "dispatch": [asdict(a) for a in assignments],
            }
            print(json.dumps(payload, indent=2))
        elif args.output_format == "csv":
            print(export_dispatch_csv(assignments))
        else:
            print(format_quotes_text(quotes))
            print()
            print(format_dispatch_text(assignments))
        return 0

    if args.command == "demo":
        quotes = [calculate_quote(r) for r in get_demo_requests()]
        assignments = dispatch_crews(quotes, num_crews=args.crews)
        if args.output_format == "json":
            payload = {
                "quotes": [asdict(q) for q in quotes],
                "dispatch": [asdict(a) for a in assignments],
            }
            print(json.dumps(payload, indent=2))
        elif args.output_format == "csv":
            print(export_dispatch_csv(assignments))
        else:
            print(format_quotes_text(quotes))
            print()
            print(format_dispatch_text(assignments))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
