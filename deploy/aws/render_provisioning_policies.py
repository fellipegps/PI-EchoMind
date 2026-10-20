"""Render public review policies using synthetic physical resource names.

No AWS calls, credentials or resource creation. CloudFormation supplies the real
role/profile ARNs during deployment. This output is for validation/simulation.
"""
import argparse
import json
from pathlib import Path
import re

import yaml

from check_infra import CfnLoader


DIRECTORY = Path(__file__).resolve().parent


def render(account, region="us-east-1", stack="echomind-provisioning"):
    template = yaml.load((DIRECTORY / "provisioning.yaml").read_text(encoding="utf-8"), Loader=CfnLoader)
    values = {
        "AWS::Partition": "aws", "AWS::Region": region, "AWS::AccountId": account,
        "AWS::URLSuffix": "amazonaws.com", "AWS::StackName": stack,
        "AWS::StackId": f"arn:aws:cloudformation:{region}:{account}:stack/{stack}/review-only",
        **{name: body["Default"] for name, body in template["Parameters"].items()},
    }
    for name, body in template["Resources"].items():
        physical = f"{stack}-{name}-review"
        values[name] = physical
        if body["Type"] == "AWS::IAM::Role":
            values[name + ".Arn"] = f"arn:aws:iam::{account}:role/{physical}"
        elif body["Type"] == "AWS::IAM::InstanceProfile":
            values[name + ".Arn"] = f"arn:aws:iam::{account}:instance-profile/{physical}"

    def resolve(node):
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        if set(node) == {"Ref"}:
            return values[node["Ref"]]
        if set(node) == {"Fn::GetAtt"}:
            return values[".".join(node["Fn::GetAtt"])]
        if set(node) == {"Fn::Sub"}:
            def substitute(match):
                key = match[1]
                return "${" + key[1:] + "}" if key.startswith("!") else values[key]
            return re.sub(r"\$\{([^}]+)\}", substitute, node["Fn::Sub"])
        return {key: resolve(value) for key, value in node.items()}

    policies = {}
    for name, body in template["Resources"].items():
        props = body["Properties"]
        if body["Type"] == "AWS::IAM::ManagedPolicy":
            policies[name] = resolve(props["PolicyDocument"])
        elif body["Type"] == "AWS::IAM::Role":
            for policy in props.get("Policies", []):
                policies[name + "/" + policy["PolicyName"]] = resolve(policy["PolicyDocument"])
    return policies


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", default="111122223333", help="AWS account ID; default is synthetic for offline checks.")
    parser.add_argument("--check", action="store_true", help="Check IAM size and privilege ceilings; no policy contents printed.")
    args = parser.parse_args()
    if not re.fullmatch(r"\d{12}", args.account):
        parser.error("account must be a 12-digit AWS account ID")
    policies = render(args.account)
    if args.check:
        for name, policy in policies.items():
            limit = 10240 if "/" in name else 6144
            longest = json.dumps(policy, separators=(",", ":")).replace("echomind-prod", "echomind-" + "p" * 20)
            assert len(longest) <= limit, (name, len(longest), limit)
        for name in ("NetworkPolicy", "StorageAndServicesPolicy"):
            for statement in policies[name]["Statement"]:
                actions = statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
                for action in actions:
                    assert action not in {"*", "iam:*", "cloudformation:*"}
                    if action.startswith("iam:"):
                        assert action in {"iam:GetRole", "iam:GetInstanceProfile", "iam:PassRole"}, action
                    assert not action.startswith("cloudformation:"), action
        print("Provisioning policies fit IAM limits and do not allow access-stack or IAM mutation by the execution role.")
    else:
        print(json.dumps(policies, indent=2))
