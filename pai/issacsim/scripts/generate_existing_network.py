#!/usr/bin/env python3
"""Derive the optional existing-network template; authoring requires cfn-lint."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETWORK_RESOURCES = (
    "WorkshopVpc", "InternetGateway", "GatewayAttachment", "PublicSubnet",
    "PublicRouteTable", "InternetRoute", "SubnetRouteAssociation",
)


def render():
    try:
        from cfnlint.decode import decode
    except ImportError:
        raise SystemExit("Template authoring requires cfn-lint in this Python environment.")
    source = ROOT / "static/workshop.yaml"
    template, errors = decode(str(source))
    if errors:
        raise SystemExit(f"Invalid source template: {errors}")
    template["Description"] = (
        "Physical AI workshop GPU host in an existing public VPC/subnet. "
        "Creates only its own security group, EC2, IAM and private results bucket. "
        "Existing network resources are never managed or deleted by this stack."
    )
    template["Metadata"]["SourceTemplateSha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    template["Metadata"]["AWS::CloudFormation::Interface"]["ParameterGroups"].append({
        "Label": {"default": "Existing public network (not owned by this stack)"},
        "Parameters": ["ExistingVpcId", "ExistingSubnetId"],
    })
    template["Parameters"]["ExistingVpcId"] = {"Type": "AWS::EC2::VPC::Id"}
    template["Parameters"]["ExistingSubnetId"] = {"Type": "AWS::EC2::Subnet::Id"}
    resources = template["Resources"]
    for name in NETWORK_RESOURCES:
        del resources[name]
    resources["WorkshopSecurityGroup"]["Properties"]["VpcId"] = {"Ref": "ExistingVpcId"}
    instance = resources["WorkshopInstance"]
    del instance["DependsOn"]
    instance["Properties"]["NetworkInterfaces"][0]["SubnetId"] = {"Ref": "ExistingSubnetId"}
    instance["Properties"]["AvailabilityZone"] = {
        "Fn::If": ["HasAvailabilityZone", {"Ref": "AvailabilityZone"}, {"Ref": "AWS::NoValue"}]
    }
    return json.dumps(template, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "static/workshop-existing-network.json"
    expected = render()
    if args.check:
        if not output.exists() or output.read_text() != expected:
            raise SystemExit("Existing-network template is stale; regenerate it.")
        print("PASS: existing-network template matches its source and scoped network transformation")
    else:
        output.write_text(expected)
        print(f"Generated {output.relative_to(ROOT)}")
