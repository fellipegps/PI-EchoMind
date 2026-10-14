"""Point-in-time gross estimate, before credits/free allowances, in USD.

Rates verified 2026-10-14 in us-east-1 using AWS Price List and official pricing.
This calculator does not call AWS or claim the credits cover every service.
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP
import json


RATES = {
    "t3_small_hour": Decimal("0.0208"),
    "gp3_gib_month": Decimal("0.08"),
    "ipv4_hour": Decimal("0.005"),
    "snapshot_gib_month": Decimal("0.05"),
    "kms_key_month": Decimal("1"),
    "standard_alarm_month": Decimal("0.10"),
}


def estimate(*, hours=730, root_gib=16, data_gib=20, snapshot_gib_month=20, credits=100):
    if any(Decimal(str(value)) < 0 for value in (hours, root_gib, data_gib, snapshot_gib_month, credits)):
        raise ValueError("Inputs must be nonnegative.")
    entries = {
        "ec2": Decimal(str(hours)) * RATES["t3_small_hour"],
        "ebs_root_and_data": Decimal(str(root_gib + data_gib)) * RATES["gp3_gib_month"],
        "public_ipv4": Decimal(str(hours)) * RATES["ipv4_hour"],
        "kms_notifications": RATES["kms_key_month"],
        "alarms_before_free_allowances": Decimal(4) * RATES["standard_alarm_month"],
        "illustrative_snapshot_storage": Decimal(str(snapshot_gib_month)) * RATES["snapshot_gib_month"],
    }
    total = sum(entries.values(), Decimal(0))
    money = lambda value: str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "verified_at": "2026-10-14", "region": "us-east-1", "currency": "USD", "hours": hours,
        "gross_monthly": {key: money(value) for key, value in entries.items()},
        "gross_monthly_total": money(total),
        "illustrative_credit_months": money(Decimal(str(credits)) / total) if total else None,
        "snapshot_assumption_gib_month": snapshot_gib_month,
        "excluded": ["traffic beyond applicable allowances", "S3 audit storage and requests", "SNS deliveries and KMS API requests",
                     "domain and DNS provider", "taxes/foreign exchange", "Supabase, Groq and Vercel", "future key rotations"],
        "notes": ["Snapshots are incremental; seven copies do not mean seven full disks.",
                  "Free Plan ends at credit exhaustion or account-plan expiration, whichever occurs first.",
                  "Budget alerts do not stop resources. Recheck pricing and credits before provisioning."],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=730)
    parser.add_argument("--snapshot-gib-month", type=int, default=20)
    arguments = parser.parse_args()
    print(json.dumps(estimate(hours=arguments.hours, snapshot_gib_month=arguments.snapshot_gib_month), indent=2))
