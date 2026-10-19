"""Run the existing read-only preflight using the explicitly selected local CLI profile.

AWS Core may use a different identity from the local CLI. This adapter preserves
the same checks while verifying the actual local deployment identity. No SDK,
credential exports or mutations. New operations require explicit allowlisting.
"""
import argparse
import ast
import asyncio
import json
from pathlib import Path


READS = {
    ("sts", "GetCallerIdentity"): ("sts", "get-caller-identity"),
    ("freetier", "GetAccountPlanState"): ("freetier", "get-account-plan-state"),
    ("freetier", "GetFreeTierUsage"): ("freetier", "get-free-tier-usage"),
    ("ec2", "DescribeInstanceTypes"): ("ec2", "describe-instance-types"),
    ("service-quotas", "GetServiceQuota"): ("service-quotas", "get-service-quota"),
    ("ssm", "GetParameter"): ("ssm", "get-parameter"),
    ("ec2", "DescribeAvailabilityZones"): ("ec2", "describe-availability-zones"),
    ("ec2", "DescribeInstances"): ("ec2", "describe-instances"),
    ("cloudtrail", "DescribeTrails"): ("cloudtrail", "describe-trails"),
}
PUBLIC_IMAGE = "/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id"


async def preflight(profile):
    async def read(*, service_name, operation_name, region_name, params):
        service, operation = READS[(service_name, operation_name)]
        if operation == "get-parameter" and params != {"Name": PUBLIC_IMAGE}:
            raise ValueError("Only the public Canonical image parameter is allowed.")
        process = await asyncio.create_subprocess_exec(
            "aws", service, operation, "--profile", profile, "--region", region_name,
            "--output", "json", "--no-cli-pager", "--cli-input-json", json.dumps(params),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode:
            raise RuntimeError(stderr.decode(errors="replace").strip())
        return json.loads(stdout)

    source = Path(__file__).with_name("preflight.mcp.py")
    namespace = {"asyncio": asyncio, "call_boto3": read}
    program = compile(source.read_text(encoding="utf-8"), str(source), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    await eval(program, namespace)
    return {"profile": profile, **namespace["result"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="default")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(preflight(args.profile)), indent=2, default=str))
