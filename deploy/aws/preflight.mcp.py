"""Read-only script for the AWS MCP run_script tool, not a local boto3 program.

Uses the tool's call_boto3 helper. Never prints credentials or fetches secrets.
Re-run before approving a change set; it does not create or authorize resources.
"""

from datetime import datetime, timezone

REGION = "us-east-1"
requests = [
    ("identity", "sts", "GetCallerIdentity", {}),
    ("account_plan", "freetier", "GetAccountPlanState", {}),
    ("usage", "freetier", "GetFreeTierUsage", {}),
    ("instance_type", "ec2", "DescribeInstanceTypes", {"InstanceTypes": ["t3.small"]}),
    ("standard_vcpu_quota", "service-quotas", "GetServiceQuota", {"ServiceCode": "ec2", "QuotaCode": "L-1216C47A"}),
    ("ami", "ssm", "GetParameter", {"Name": "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"}),
    ("availability_zones", "ec2", "DescribeAvailabilityZones", {"Filters": [{"Name": "state", "Values": ["available"]}]}),
    ("target_region_instances", "ec2", "DescribeInstances", {"Filters": [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]}),
    ("target_region_trails", "cloudtrail", "DescribeTrails", {"includeShadowTrails": True}),
]
responses = await asyncio.gather(*[
    call_boto3(service_name=service, operation_name=operation, region_name=REGION, params=params)
    for _, service, operation, params in requests
], return_exceptions=True)
checks = {request[0]: ({"error": str(response)} if isinstance(response, Exception) else response)
          for request, response in zip(requests, responses)}
identity = checks["identity"]
is_root = identity.get("Arn", "").endswith(":root")
plan = checks["account_plan"]
blockers = []
if is_root:
    blockers.append("Use a dedicated non-root provisioning identity; current integration is root.")
if any("error" in value for value in checks.values()):
    blockers.append("Some read checks failed; review errors before provisioning.")
if plan.get("accountPlanStatus") != "ACTIVE":
    blockers.append("Account plan is not confirmed ACTIVE.")
if plan.get("accountPlanType") == "FREE" and plan.get("accountPlanRemainingCredits", {}).get("amount", 0) <= 0:
    blockers.append("No remaining Free Plan credits confirmed.")
result = {
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "region": REGION,
    "uses_root": is_root,
    "read_checks": checks,
    "blockers": blockers,
    "creates_resources": False,
    "requires_before_execution": ["current cost estimate", "confirmed alert email", "free-tier service eligibility",
                                  "quota/capacity and AMI review", "data-disk/AZ review", "approved CloudFormation change set"],
}
result
