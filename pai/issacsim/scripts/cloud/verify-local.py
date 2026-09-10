#!/usr/bin/env python3
"""Offline regression checks. No AWS SDK/API, Docker, or host bootstrap execution."""

import ast
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preflight = load("preflight", "preflight.py")
cleanup = load("cleanup", "cleanup-resources.py")
ENV = {
    "AWS_REGION": "us-east-1", "AMI_ID": "ami-0123456789abcdef0",
    "KEY_NAME": "example-key", "SSH_CIDR": "203.0.113.10/32",
    "STACK_NAME": "offline-test",
}

NETWORK_ENV = {"EXISTING_VPC_ID": "vpc-0123456789abcdef0",
               "EXISTING_SUBNET_ID": "subnet-0123456789abcdef0"}
VPC_QUOTAS = ("service-quotas", "list-service-quotas", "--service-code", "vpc")
G6E_OFFERINGS = ("ec2", "describe-instance-type-offerings", "--location-type", "availability-zone",
                 "--filters", "Name=instance-type,Values=g6e.2xlarge")
EXPLICIT_ROUTES = ("ec2", "describe-route-tables", "--filters",
                   f"Name=vpc-id,Values={NETWORK_ENV['EXISTING_VPC_ID']}",
                   f"Name=association.subnet-id,Values={NETWORK_ENV['EXISTING_SUBNET_ID']}")
MAIN_ROUTES = (*EXPLICIT_ROUTES[:-1], "Name=association.main,Values=true")


class OfflineChecks(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, ENV)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        for key in ("AMI_OWNER_ID", "AVAILABILITY_ZONE", "CONFIRM_DELETE_STACK", "ACCEPT_EULA", "INSTANCE_TYPE",
                    *NETWORK_ENV):
            os.environ.pop(key, None)
        self.calls = []
        self.fixtures = {
            ("sts", "get-caller-identity"): {"Account": "111122223333", "Arn": "test-principal"},
            ("cloudformation", "list-stacks"): {"StackSummaries": []},
            ("ec2", "describe-images"): {"Images": [{
                "OwnerId": "099720109477", "State": "available", "Architecture": "x86_64",
                "VirtualizationType": "hvm", "RootDeviceType": "ebs",
                "RootDeviceName": "/dev/sda1",
                "Name": "ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-20260909",
                "BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 8}}],
            }]},
            ("ec2", "describe-key-pairs"): {"KeyPairs": [{"KeyName": "example-key"}]},
            ("ec2", "describe-instance-type-offerings"): {
                "InstanceTypeOfferings": [{"Location": "us-east-1a"}]},
            ("service-quotas", "list-service-quotas"): {"Quotas": [{
                "QuotaName": "Running On-Demand G and VT instances", "Value": 32}]},
            VPC_QUOTAS: {"Quotas": [
                {"QuotaCode": "L-F678F1CE", "QuotaName": "VPCs per Region", "Value": 5},
                {"QuotaCode": "L-A4707A72", "QuotaName": "Internet gateways per Region", "Value": 5}]},
            ("ec2", "describe-vpcs"): {"Vpcs": [
                {"VpcId": NETWORK_ENV["EXISTING_VPC_ID"], "State": "available"}]},
            ("ec2", "describe-subnets"): {"Subnets": [{
                "SubnetId": NETWORK_ENV["EXISTING_SUBNET_ID"],
                "VpcId": NETWORK_ENV["EXISTING_VPC_ID"], "State": "available",
                "AvailabilityZone": "us-east-1a", "AvailableIpAddressCount": 1,
                "MapPublicIpOnLaunch": False}]},
            ("ec2", "describe-route-tables"): {"RouteTables": [{
                "RouteTableId": "rtb-0123456789abcdef0", "VpcId": NETWORK_ENV["EXISTING_VPC_ID"],
                "Associations": [{"SubnetId": NETWORK_ENV["EXISTING_SUBNET_ID"],
                                  "AssociationState": {"State": "associated"}}],
                "Routes": [{"DestinationCidrBlock": "0.0.0.0/0", "State": "active",
                            "GatewayId": "igw-0123456789abcdef0"}]}]},
            ("ec2", "describe-internet-gateways"): {"InternetGateways": [{
                "InternetGatewayId": "igw-0123456789abcdef0",
                "Attachments": [{"VpcId": NETWORK_ENV["EXISTING_VPC_ID"], "State": "available"}]}]},
            ("ec2", "describe-instances"): {"Reservations": [{"Instances": [
                {"InstanceType": "g6.4xlarge"},
                {"InstanceType": "g6.4xlarge", "InstanceLifecycle": "spot"},
            ]}]},
            ("ec2", "describe-instance-types"): {"InstanceTypes": [
                {"InstanceType": "g6.4xlarge", "VCpuInfo": {"DefaultVCpus": 16}},
                {"InstanceType": "g6e.2xlarge", "VCpuInfo": {"DefaultVCpus": 8}}]},
        }

    def fake_read(self, values, *args):
        self.calls.append(args)
        return copy.deepcopy(self.fixtures[args if args in self.fixtures else args[:2]])

    def run_preflight(self):
        with patch.object(preflight, "aws", self.fake_read), redirect_stderr(io.StringIO()):
            return preflight.check_aws(preflight.local_parameters())

    def test_source_syntax(self):
        for path in ROOT.glob("*.sh"):
            subprocess.run(["bash", "-n", str(path)], check=True)
        for path in ROOT.glob("*.py"):
            ast.parse(path.read_text())

    def test_cidr_rejects_broad_ipv6_and_invalid_inputs(self):
        for cidr in ("0.0.0.0/0", "203.0.113.0/24", "::1/128", "1.2.3.999/32", "1.2.3.4/33"):
            with self.subTest(cidr=cidr), patch.dict(os.environ, {"SSH_CIDR": cidr}):
                with self.assertRaises(SystemExit):
                    preflight.local_parameters()

    def test_ami_and_stack_reject_placeholders(self):
        for key, value in (("AMI_ID", "<AMI_ID>"), ("STACK_NAME", "-unsafe")):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(SystemExit):
                    preflight.local_parameters()

    def test_read_checks_compute_quota_and_ignore_spot(self):
        result = self.run_preflight()
        self.assertEqual(result["ObservedUsedVcpus"], 16)
        self.assertEqual(result["RequiredVcpus"], 16)
        self.assertEqual(result["InstanceType"], "g6.4xlarge")
        self.assertEqual(result["RootDeviceName"], "/dev/sda1")
        self.assertEqual(result["AvailabilityZone"], "us-east-1a")
        self.assertTrue(all(
            args[1].startswith(("get-", "list-", "describe-")) for args in self.calls))

    def test_instance_type_requires_exact_explicit_allowlist(self):
        self.assertEqual(preflight.local_parameters()["INSTANCE_TYPE"], "g6.4xlarge")
        for instance_type in ("g6.4xlarge", "g6e.2xlarge"):
            with patch.dict(os.environ, {"INSTANCE_TYPE": instance_type}):
                self.assertEqual(preflight.local_parameters()["INSTANCE_TYPE"], instance_type)
        for instance_type in ("", "g6.8xlarge", "g6e.4xlarge", "g7e.8xlarge", "G6E.2XLARGE", "g6e.2xlarge "):
            with self.subTest(instance_type=instance_type), patch.dict(os.environ, {"INSTANCE_TYPE": instance_type}):
                with self.assertRaisesRegex(SystemExit, "INSTANCE_TYPE"):
                    preflight.local_parameters()

    def test_g6e_uses_eight_vcpus_and_accounts_for_existing_usage(self):
        original = copy.deepcopy(self.fixtures[("ec2", "describe-instances")]["Reservations"])
        for network in ({}, NETWORK_ENV):
            for reservations, used in (([], 0), (original, 16)):
                with self.subTest(network=network, used=used), patch.dict(os.environ, {**network, "INSTANCE_TYPE": "g6e.2xlarge"}):
                    self.fixtures[("ec2", "describe-instances")]["Reservations"] = reservations
                    quota = self.fixtures[("service-quotas", "list-service-quotas")]["Quotas"][0]
                    quota["Value"] = used + 8
                    result = self.run_preflight()
                    self.assertEqual(result["InstanceType"], "g6e.2xlarge")
                    self.assertEqual(result["RequiredVcpus"], 8)
                    self.assertEqual(result["ObservedUsedVcpus"], used)
                    self.assertIn(G6E_OFFERINGS, self.calls)
                    types = ("g6.4xlarge", "g6e.2xlarge") if used else ("g6e.2xlarge",)
                    self.assertIn(("ec2", "describe-instance-types", "--instance-types", *types), self.calls)
                    quota["Value"] -= 1
                    with self.assertRaisesRegex(SystemExit, "G/VT vCPU quota 부족:.*추가 필요 8"):
                        self.run_preflight()

    def test_selected_type_quota_uses_reported_default_vcpus(self):
        self.fixtures[("ec2", "describe-instances")]["Reservations"] = []
        self.fixtures[("service-quotas", "list-service-quotas")]["Quotas"][0]["Value"] = 8
        # A changed API response must not be replaced by a hardcoded eight-vCPU assumption.
        self.fixtures[("ec2", "describe-instance-types")]["InstanceTypes"][1]["VCpuInfo"]["DefaultVCpus"] = 10
        with patch.dict(os.environ, {"INSTANCE_TYPE": "g6e.2xlarge"}):
            with self.assertRaisesRegex(SystemExit, "추가 필요 10"):
                self.run_preflight()

    def test_g6e_offerings_control_explicit_az_and_existing_subnet(self):
        self.fixtures[G6E_OFFERINGS] = {"InstanceTypeOfferings": [
            {"Location": "us-east-1b"}, {"Location": "us-east-1d"}]}
        with patch.dict(os.environ, {"INSTANCE_TYPE": "g6e.2xlarge", "AVAILABILITY_ZONE": "us-east-1d"}):
            self.assertEqual(self.run_preflight()["AvailabilityZone"], "us-east-1d")
        with patch.dict(os.environ, {**NETWORK_ENV, "INSTANCE_TYPE": "g6e.2xlarge"}):
            with self.assertRaisesRegex(SystemExit, "g6e.2xlarge 제공 목록"):
                self.run_preflight()  # The subnet AZ offers G6 in the default fixture, but not G6e.
            self.fixtures[("ec2", "describe-subnets")]["Subnets"][0]["AvailabilityZone"] = "us-east-1b"
            self.assertEqual(self.run_preflight()["AvailabilityZone"], "us-east-1b")
        self.assertTrue(all(args == G6E_OFFERINGS for args in self.calls
                            if args[:2] == ("ec2", "describe-instance-type-offerings")))

    def test_missing_g6e_offering_never_falls_back_to_g6(self):
        self.fixtures[G6E_OFFERINGS] = {"InstanceTypeOfferings": []}
        with patch.dict(os.environ, {"INSTANCE_TYPE": "g6e.2xlarge"}):
            with self.assertRaisesRegex(SystemExit, "g6e.2xlarge 제공 AZ가 없습니다"):
                self.run_preflight()
        self.assertEqual([args for args in self.calls if args[:2] ==
                          ("ec2", "describe-instance-type-offerings")], [G6E_OFFERINGS])

    def test_insufficient_remaining_quota_is_rejected(self):
        self.fixtures[("service-quotas", "list-service-quotas")]["Quotas"][0]["Value"] = 16
        with self.assertRaisesRegex(SystemExit, "quota 부족"):
            self.run_preflight()

    def test_untrusted_ami_is_rejected(self):
        self.fixtures[("ec2", "describe-images")]["Images"][0]["OwnerId"] = "999900001111"
        with self.assertRaisesRegex(SystemExit, "소유자"):
            self.run_preflight()

    def test_extra_ami_disks_are_rejected(self):
        self.fixtures[("ec2", "describe-images")]["Images"][0]["BlockDeviceMappings"].append(
            {"DeviceName": "/dev/sdf", "Ebs": {"VolumeSize": 10}})
        with self.assertRaisesRegex(SystemExit, "하나만"):
            self.run_preflight()

    def test_wrong_os_image_is_rejected(self):
        self.fixtures[("ec2", "describe-images")]["Images"][0]["Name"] = "ubuntu-noble-24.04"
        with self.assertRaisesRegex(SystemExit, "22.04"):
            self.run_preflight()

    def test_existing_stack_is_not_updated(self):
        self.fixtures[("cloudformation", "list-stacks")]["StackSummaries"] = [
            {"StackName": "offline-test", "StackStatus": "CREATE_COMPLETE"}]
        with self.assertRaisesRegex(SystemExit, "존재"):
            self.run_preflight()

    def test_invalid_az_is_rejected(self):
        with patch.dict(os.environ, {"AVAILABILITY_ZONE": "us-east-1z"}):
            with self.assertRaisesRegex(SystemExit, "제공 목록"):
                self.run_preflight()

    def test_existing_network_requires_both_valid_ids(self):
        for values in ({"EXISTING_VPC_ID": NETWORK_ENV["EXISTING_VPC_ID"]},
                       {"EXISTING_SUBNET_ID": NETWORK_ENV["EXISTING_SUBNET_ID"]},
                       {**NETWORK_ENV, "EXISTING_VPC_ID": "vpc-example"},
                       {**NETWORK_ENV, "EXISTING_SUBNET_ID": "subnet-0123456789abcdef00"}):
            with self.subTest(values=values), patch.dict(os.environ, values):
                with self.assertRaises(SystemExit):
                    preflight.local_parameters()
        with patch.dict(os.environ, {"EXISTING_VPC_ID": "vpc-1234abcd",
                                     "EXISTING_SUBNET_ID": "subnet-1234abcd"}):
            self.assertEqual(preflight.local_parameters()["EXISTING_VPC_ID"], "vpc-1234abcd")

    def test_default_network_checks_both_quotas_and_counts(self):
        result = self.run_preflight()
        self.assertEqual(result["NetworkMode"], "new")
        self.assertEqual(result["VPCQuota"], 5)
        self.assertEqual(result["ObservedVPCCount"], 1)
        self.assertEqual(result["InternetGatewayQuota"], 5)
        self.assertEqual(result["ObservedInternetGatewayCount"], 1)
        for operation, key, name in (("describe-vpcs", "Vpcs", "VPC"),
                                     ("describe-internet-gateways", "InternetGateways", "InternetGateway")):
            original = copy.deepcopy(self.fixtures[("ec2", operation)][key])
            with self.subTest(quota=name):
                self.fixtures[("ec2", operation)][key] = original * 4
                self.run_preflight()  # One free slot is sufficient.
                self.fixtures[("ec2", operation)][key] = original * 5
                with self.assertRaisesRegex(SystemExit, f"quota 부족:.*{name}.*EXISTING_VPC_ID"):
                    self.run_preflight()
            self.fixtures[("ec2", operation)][key] = original

    def test_missing_network_quota_fails_closed(self):
        for index in (0, 1):
            with self.subTest(index=index):
                quotas = self.fixtures[VPC_QUOTAS]["Quotas"]
                saved = quotas.pop(index)
                with self.assertRaisesRegex(SystemExit, "quota를 확인하지"):
                    self.run_preflight()
                quotas.insert(index, saved)

    def test_existing_network_uses_subnet_az_and_skips_creation_quotas(self):
        self.fixtures[VPC_QUOTAS]["Quotas"] = []
        self.fixtures[("ec2", "describe-instance-type-offerings")]["InstanceTypeOfferings"].insert(
            0, {"Location": "us-east-1b"})
        self.fixtures[("ec2", "describe-subnets")]["Subnets"][0]["AvailabilityZone"] = "us-east-1b"
        with patch.dict(os.environ, NETWORK_ENV):
            result = self.run_preflight()
        self.assertEqual(result["NetworkMode"], "existing")
        self.assertEqual(result["AvailabilityZone"], "us-east-1b")
        self.assertEqual(result["AvailableIpAddressCount"], 1)
        self.assertEqual(result["ObservedUsedVcpus"], 16)
        self.assertNotIn(VPC_QUOTAS, self.calls)
        self.assertIn(("ec2", "describe-vpcs", "--vpc-ids", NETWORK_ENV["EXISTING_VPC_ID"]), self.calls)
        self.assertIn(EXPLICIT_ROUTES, self.calls)
        self.assertNotIn(MAIN_ROUTES, self.calls)
        self.assertTrue(all(args[1].startswith(("get-", "list-", "describe-")) for args in self.calls))

    def test_existing_subnet_uses_main_table_only_without_explicit_association(self):
        self.fixtures[EXPLICIT_ROUTES] = {"RouteTables": []}
        table = self.fixtures[("ec2", "describe-route-tables")]["RouteTables"][0]
        table["Associations"] = [{"Main": True, "AssociationState": {"State": "associated"}}]
        with patch.dict(os.environ, NETWORK_ENV):
            self.assertEqual(self.run_preflight()["RouteTableId"], table["RouteTableId"])
        self.assertIn(MAIN_ROUTES, self.calls)

    def test_existing_network_rejects_unavailable_mismatched_or_full_subnet(self):
        cases = (("describe-vpcs", "Vpcs", "State", "pending", "available"),
                 ("describe-subnets", "Subnets", "State", "pending", "available"),
                 ("describe-subnets", "Subnets", "VpcId", "vpc-99999999", "속하지"),
                 ("describe-subnets", "Subnets", "AvailableIpAddressCount", 0, "IPv4"),
                 ("describe-subnets", "Subnets", "Ipv6Native", True, "IPv4"),
                 ("describe-subnets", "Subnets", "AvailabilityZone", "us-east-1z", "제공 목록"))
        for operation, key, field, value, message in cases:
            with self.subTest(field=field), patch.dict(os.environ, NETWORK_ENV):
                resource = self.fixtures[("ec2", operation)][key][0]
                with patch.dict(resource, {field: value}):
                    with self.assertRaisesRegex(SystemExit, message):
                        self.run_preflight()
        with patch.dict(os.environ, {**NETWORK_ENV, "AVAILABILITY_ZONE": "us-east-1b"}):
            with self.assertRaisesRegex(SystemExit, "일치하지"):
                self.run_preflight()

    def test_existing_network_rejects_private_or_blackhole_default_route(self):
        table = self.fixtures[("ec2", "describe-route-tables")]["RouteTables"][0]
        cases = ([], [{"DestinationCidrBlock": "0.0.0.0/0", "State": "active", "NatGatewayId": "nat-test"}],
                 [{"DestinationCidrBlock": "0.0.0.0/0", "State": "blackhole", "GatewayId": "igw-test"}],
                 [{"DestinationCidrBlock": "10.0.0.0/8", "State": "active", "GatewayId": "igw-test"}])
        for routes in cases:
            with self.subTest(routes=routes), patch.dict(os.environ, NETWORK_ENV):
                with patch.dict(table, {"Routes": routes}):
                    with self.assertRaisesRegex(SystemExit, "active 0.0.0.0/0 IGW"):
                        self.run_preflight()
        self.assertNotIn(MAIN_ROUTES, self.calls)

    def test_existing_network_rejects_unstable_route_association_or_detached_igw(self):
        table = self.fixtures[("ec2", "describe-route-tables")]["RouteTables"][0]
        with patch.dict(os.environ, NETWORK_ENV):
            with patch.dict(table["Associations"][0]["AssociationState"], {"State": "associating"}):
                with self.assertRaisesRegex(SystemExit, "associated"):
                    self.run_preflight()
            gateway = self.fixtures[("ec2", "describe-internet-gateways")]["InternetGateways"][0]
            for attachments in ([], [{"VpcId": "vpc-99999999", "State": "available"}],
                                [{"VpcId": NETWORK_ENV["EXISTING_VPC_ID"], "State": "detached"}]):
                with self.subTest(attachments=attachments), patch.dict(gateway, {"Attachments": attachments}):
                    with self.assertRaisesRegex(SystemExit, "IGW가 같은 VPC"):
                        self.run_preflight()

    def test_existing_network_still_checks_gpu_quota(self):
        self.fixtures[("service-quotas", "list-service-quotas")]["Quotas"][0]["Value"] = 16
        with patch.dict(os.environ, NETWORK_ENV):
            with self.assertRaisesRegex(SystemExit, "G/VT vCPU quota 부족"):
                self.run_preflight()

    def test_existing_template_allocates_public_ip_without_owning_network(self):
        template = json.loads((ROOT / "../../static/workshop-existing-network.json").read_text())
        self.assertEqual({name: resource["Type"] for name, resource in template["Resources"].items()},
                         cleanup.EXISTING_NETWORK_RESOURCE_TYPES)
        self.assertEqual(template["Parameters"]["InstanceType"]["Default"], "g6.4xlarge")
        self.assertEqual(template["Parameters"]["InstanceType"]["AllowedValues"], ["g6.4xlarge", "g6e.2xlarge"])
        self.assertEqual(set(template["Parameters"]), {"AmiId", "KeyName", "SshCidr", "InstanceType",
                         "AvailabilityZone", "RootDeviceName", "ExistingVpcId", "ExistingSubnetId"})
        forbidden = {"AWS::EC2::" + name for name in ("VPC", "Subnet", "InternetGateway",
                     "VPCGatewayAttachment", "Route", "RouteTable", "SubnetRouteTableAssociation")}
        self.assertTrue(all(r["Type"] not in forbidden for r in template["Resources"].values()))
        instance = template["Resources"]["WorkshopInstance"]["Properties"]
        interface = instance["NetworkInterfaces"][0]
        self.assertIs(interface["AssociatePublicIpAddress"], True)
        self.assertEqual(interface["SubnetId"], {"Ref": "ExistingSubnetId"})
        sg = template["Resources"]["WorkshopSecurityGroup"]["Properties"]
        self.assertEqual(sg["VpcId"], {"Ref": "ExistingVpcId"})

    def test_default_modes_and_eula_gate_never_call_aws_or_docker(self):
        with tempfile.TemporaryDirectory(prefix="isaac-offline-") as directory:
            sentinel = Path(directory) / "unexpected-call"
            for executable in ("aws", "docker", "sudo"):
                stub = Path(directory) / executable
                stub.write_text('#!/bin/sh\nprintf "called" > "$SENTINEL"\nexit 99\n')
                stub.chmod(0o755)
            env = {**os.environ, "PATH": f"{directory}:{os.environ['PATH']}",
                   "SENTINEL": str(sentinel)}
            for name, args, expected, extra in (
                ("deploy.sh", [], 0, {}), ("deploy.sh", ["--plan"], 0, NETWORK_ENV),
                ("deploy.sh", ["--plan"], 0, {"INSTANCE_TYPE": "g6e.2xlarge"}),
                ("deploy.sh", ["--plan"], 0, {**NETWORK_ENV, "INSTANCE_TYPE": "g6e.2xlarge"}),
                ("deploy.sh", ["--plan"], 1, {"INSTANCE_TYPE": "g7e.8xlarge"}),
                ("deploy.sh", ["--check"], 1, {"INSTANCE_TYPE": "g6e.4xlarge"}),
                ("deploy.sh", ["--deploy"], 1, {"INSTANCE_TYPE": ""}),
                ("deploy.sh", ["--check"], 1, {"EXISTING_VPC_ID": NETWORK_ENV["EXISTING_VPC_ID"]}),
                ("deploy.sh", ["--deploy"], 1, {"EXISTING_SUBNET_ID": NETWORK_ENV["EXISTING_SUBNET_ID"]}),
                ("cleanup.sh", [], 0, {}), ("run-headless.sh", ["--check"], 2, {}),
                ("cleanup.sh", ["--delete"], 2, {}),
            ):
                with self.subTest(name=name, args=args):
                    result = subprocess.run(["bash", str(ROOT / name), *args], env={**env, **extra},
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertFalse(sentinel.exists(), "AWS/Docker/sudo was unexpectedly invoked")
                    if name == "deploy.sh" and expected == 0:
                        instance_type = extra.get("INSTANCE_TYPE", "g6.4xlarge")
                        self.assertIn(f"인스턴스={instance_type}", result.stdout)
                        self.assertIn(f"InstanceType={instance_type}", result.stdout)
                        if extra.get("EXISTING_VPC_ID"):
                            self.assertIn("workshop-existing-network.json", result.stdout)
                            self.assertIn(f"ExistingVpcId={NETWORK_ENV['EXISTING_VPC_ID']}", result.stdout)
                            self.assertIn(f"ExistingSubnetId={NETWORK_ENV['EXISTING_SUBNET_ID']}", result.stdout)
                        else:
                            self.assertIn("workshop.yaml", result.stdout)
                            self.assertNotIn("ExistingVpcId=", result.stdout)

    def test_wrapper_check_and_deploy_use_verified_existing_network_with_fake_cli(self):
        with tempfile.TemporaryDirectory(prefix="isaac-fake-cli-") as directory:
            directory = Path(directory)
            fixtures = directory / "fixtures.json"
            fixtures.write_text(json.dumps([[list(k), v] for k, v in self.fixtures.items()]))
            log = directory / "calls.jsonl"
            stub = directory / "aws"
            stub.write_text(r"""#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ['CALL_LOG'], 'a') as stream:
    stream.write(json.dumps(args) + '\n')
if args[:1] == ['--region']:
    args = args[4:]
with open(os.environ['FIXTURES']) as stream:
    fixtures = {tuple(k): v for k, v in json.load(stream)}
if args[:2] in (['cloudformation', 'deploy'], ['cloudformation', 'describe-stacks']):
    print('{}')
else:
    print(json.dumps(fixtures.get(tuple(args), fixtures.get(tuple(args[:2])))))
""")
            stub.chmod(0o755)
            env = {**os.environ, **NETWORK_ENV, "PATH": f"{directory}:{os.environ['PATH']}",
                   "CALL_LOG": str(log), "FIXTURES": str(fixtures)}
            for instance_type, mode in ((t, m) for t in ("g6.4xlarge", "g6e.2xlarge") for m in ("--check", "--deploy")):
                with self.subTest(instance_type=instance_type, mode=mode):
                    log.write_text("")
                    result = subprocess.run(["bash", str(ROOT / "deploy.sh"), mode], env={**env, "INSTANCE_TYPE": instance_type},
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    calls = [json.loads(line) for line in log.read_text().splitlines()]
                    self.assertTrue(any(args[4:] == [*G6E_OFFERINGS[:-1], f"Name=instance-type,Values={instance_type}"]
                                        for args in calls))
                    if mode == "--check":
                        self.assertEqual(json.loads(result.stdout)["InstanceType"], instance_type)
                        self.assertEqual(json.loads(result.stdout)["RequiredVcpus"], 8 if instance_type == "g6e.2xlarge" else 16)
                        self.assertEqual(json.loads(result.stdout)["ExistingSubnetId"],
                                         NETWORK_ENV["EXISTING_SUBNET_ID"])
                        self.assertTrue(all(args[5].startswith(("get-", "list-", "describe-")) for args in calls))
                    else:
                        deploy = next(args for args in calls if args[:2] == ["cloudformation", "deploy"])
                        self.assertTrue(deploy[deploy.index("--template-file") + 1].endswith(
                            "/static/workshop-existing-network.json"))
                        for parameter in (f"InstanceType={instance_type}", "AvailabilityZone=us-east-1a", "RootDeviceName=/dev/sda1",
                                          f"ExistingVpcId={NETWORK_ENV['EXISTING_VPC_ID']}",
                                          f"ExistingSubnetId={NETWORK_ENV['EXISTING_SUBNET_ID']}"):
                            self.assertIn(parameter, deploy)

    def cleanup_fixture(self, region, *args, **kwargs):
        self.calls.append(args)
        responses = {
            ("cloudformation", "describe-stacks"): {"Stacks": [{
                "StackId": "test-stack-id", "StackStatus": "CREATE_COMPLETE",
                "Tags": [{"Key": "Workshop", "Value": "physical-ai-isaac-aws"}],
            }]},
            ("cloudformation", "list-stack-resources"): {"StackResourceSummaries": [
                {"LogicalResourceId": "WorkshopVpc", "PhysicalResourceId": "test-vpc",
                 "ResourceType": "AWS::EC2::VPC"},
                {"LogicalResourceId": "WorkshopInstance", "PhysicalResourceId": "test-instance",
                 "ResourceType": "AWS::EC2::Instance"},
                {"LogicalResourceId": "ResultsBucket", "PhysicalResourceId": "test-results",
                 "ResourceType": "AWS::S3::Bucket"},
            ]},
            ("ec2", "describe-instances"): {"Reservations": [{"Instances": [
                {"State": {"Name": "running"}}]}]},
            ("ec2", "stop-instances"): {},
            ("ec2", "wait"): {},
            ("s3api", "get-bucket-versioning"): {},
            ("s3api", "list-multipart-uploads"): {"Uploads": [{"Key": "frames", "UploadId": "test-upload"}]},
            ("s3api", "abort-multipart-upload"): {},
            ("s3", "rm"): "",
            ("cloudformation", "delete-stack"): {},
            ("cloudformation", "wait"): "",
        }
        return copy.deepcopy(responses[args[:2]])

    def run_cleanup_with_cli_versioning_stdout(self, stdout):
        def captured(command, **kwargs):
            self.assertTrue(kwargs["capture_output"])
            self.assertTrue(kwargs["text"])
            self.assertTrue(kwargs["check"])
            self.assertEqual(kwargs["env"]["AWS_PAGER"], "")
            args = tuple(command[3:])
            if args[-2:] == ("--output", "json"):
                args = args[:-2]
            response = self.fallback_cleanup_fixture(command[2], *args)
            if args[:2] == ("s3api", "get-bucket-versioning"):
                self.assertEqual(command, ["aws", "--region", "us-east-1", "s3api", "get-bucket-versioning",
                                           "--bucket", "test-results", "--output", "json"])
                text = stdout
            else:
                text = json.dumps(response) if isinstance(response, dict) else response
            return subprocess.CompletedProcess(command, 0, stdout=text, stderr="")
        with patch.dict(os.environ, {"CONFIRM_DELETE_STACK": "offline-test"}):
            with patch.object(cleanup.subprocess, "run", side_effect=captured), redirect_stdout(io.StringIO()):
                cleanup.main("us-east-1", "offline-test")

    def test_cleanup_empty_versioning_cli_output_completes_cleanup(self):
        for stdout in ("", " \n\t", "{}"):
            with self.subTest(stdout=stdout):
                self.calls.clear()
                self.run_cleanup_with_cli_versioning_stdout(stdout)
                self.assertIn(("s3", "rm", "s3://test-results", "--recursive"), self.calls)
                self.assertIn(("cloudformation", "delete-stack", "--stack-name", "test-stack-id"), self.calls)
                self.assertEqual(self.calls[-1], ("cloudformation", "wait", "stack-delete-complete",
                                                 "--stack-name", "test-stack-id"))

    def test_cleanup_malformed_versioning_cli_output_blocks_bucket_and_stack_deletion(self):
        for stdout in ('""', '"unexpected"', "null", "[]", "false", "0", "not-json", "{",
                       '{"Status": "Enabled"}', '{"Status": "Suspended"}', '{"Status": "Disabled"}',
                       '{"Status": null}', '{"Unknown": true}', '{"MFADelete": "Enabled"}'):
            with self.subTest(stdout=stdout):
                self.calls.clear()
                with self.assertRaises(SystemExit):
                    self.run_cleanup_with_cli_versioning_stdout(stdout)
                self.assertEqual(self.calls[-1][:2], ("s3api", "get-bucket-versioning"))
                self.assertFalse(any(args[:2] in (("s3", "rm"), ("s3api", "abort-multipart-upload"),
                                                  ("cloudformation", "delete-stack")) for args in self.calls))

    def test_cleanup_cli_error_is_not_treated_as_empty_success(self):
        with patch.object(cleanup.subprocess, "run", side_effect=subprocess.CalledProcessError(
                255, ["aws", "s3api", "get-bucket-versioning"], stderr="AccessDenied")):
            with self.assertRaises(subprocess.CalledProcessError):
                cleanup.aws("us-east-1", "s3api", "get-bucket-versioning", "--bucket", "test-results")

    def test_cleanup_cli_text_output_is_preserved(self):
        result = subprocess.CompletedProcess(["aws"], 0, stdout="delete: s3://test-results/frame\n", stderr="")
        with patch.object(cleanup.subprocess, "run", return_value=result):
            self.assertEqual(cleanup.aws("us-east-1", "s3", "rm", "s3://test-results", "--recursive",
                                         json_output=False), result.stdout)

    def test_cleanup_requires_matching_confirmation_before_any_api(self):
        with patch.object(cleanup, "aws", side_effect=AssertionError("No API calls allowed")):
            with self.assertRaisesRegex(SystemExit, "일치"):
                cleanup.main("us-east-1", "offline-test")

    def test_cleanup_stops_writer_and_limits_deletion_to_stack_resources(self):
        with patch.dict(os.environ, {"CONFIRM_DELETE_STACK": "offline-test"}):
            with patch.object(cleanup, "aws", self.cleanup_fixture), redirect_stdout(io.StringIO()):
                cleanup.main("us-east-1", "offline-test")
        stop = self.calls.index(("ec2", "stop-instances", "--instance-ids", "test-instance"))
        empty = self.calls.index(("s3", "rm", "s3://test-results", "--recursive"))
        delete = self.calls.index(("cloudformation", "delete-stack", "--stack-name", "test-stack-id"))
        self.assertLess(stop, empty)
        self.assertLess(empty, delete)
        self.assertIn(("s3api", "abort-multipart-upload", "--bucket", "test-results",
                       "--key", "frames", "--upload-id", "test-upload"), self.calls)
        self.assertEqual(self.calls[-1], ("cloudformation", "wait", "stack-delete-complete",
                                        "--stack-name", "test-stack-id"))

    def fallback_cleanup_fixture(self, region, *args, **kwargs):
        result = self.cleanup_fixture(region, *args, **kwargs)
        if args[:2] == ("cloudformation", "describe-stacks"):
            result["Stacks"][0]["Parameters"] = [
                {"ParameterKey": "ExistingVpcId", "ParameterValue": NETWORK_ENV["EXISTING_VPC_ID"]},
                {"ParameterKey": "ExistingSubnetId", "ParameterValue": NETWORK_ENV["EXISTING_SUBNET_ID"]}]
        if args[:2] == ("cloudformation", "list-stack-resources"):
            resources = [r for r in result["StackResourceSummaries"] if r["LogicalResourceId"] != "WorkshopVpc"]
            for name, kind in (("WorkshopSecurityGroup", "AWS::EC2::SecurityGroup"),
                               ("ResultsBucketPolicy", "AWS::S3::BucketPolicy"),
                               ("WorkshopRole", "AWS::IAM::Role"),
                               ("WorkshopInstanceProfile", "AWS::IAM::InstanceProfile"),
                               ("WorkshopLaunchTemplate", "AWS::EC2::LaunchTemplate")):
                resources.append({"LogicalResourceId": name, "ResourceType": kind,
                                  "PhysicalResourceId": f"test-{name}"})
            result["StackResourceSummaries"] = resources
        return result

    def run_cleanup(self, fixture):
        with patch.dict(os.environ, {"CONFIRM_DELETE_STACK": "offline-test"}):
            with patch.object(cleanup, "aws", fixture), redirect_stdout(io.StringIO()):
                cleanup.main("us-east-1", "offline-test")

    def assert_cleanup_inventory_only(self):
        self.assertEqual([args[:2] for args in self.calls],
                         [("cloudformation", "describe-stacks"), ("cloudformation", "list-stack-resources")])

    def test_cleanup_existing_network_uses_only_stack_owned_resources(self):
        # Environment values must never replace the saved stack inventory or parameters.
        with patch.dict(os.environ, {"EXISTING_VPC_ID": "vpc-ffffffff",
                                     "EXISTING_SUBNET_ID": "subnet-ffffffff"}):
            self.run_cleanup(self.fallback_cleanup_fixture)
        self.assertEqual(self.calls, [
            ("cloudformation", "describe-stacks", "--stack-name", "offline-test"),
            ("cloudformation", "list-stack-resources", "--stack-name", "test-stack-id"),
            ("ec2", "describe-instances", "--filters", "Name=instance-id,Values=test-instance"),
            ("ec2", "stop-instances", "--instance-ids", "test-instance"),
            ("ec2", "wait", "instance-stopped", "--instance-ids", "test-instance"),
            ("s3api", "get-bucket-versioning", "--bucket", "test-results"),
            ("s3api", "list-multipart-uploads", "--bucket", "test-results"),
            ("s3api", "abort-multipart-upload", "--bucket", "test-results",
             "--key", "frames", "--upload-id", "test-upload"),
            ("s3", "rm", "s3://test-results", "--recursive"),
            ("cloudformation", "delete-stack", "--stack-name", "test-stack-id"),
            ("cloudformation", "wait", "stack-delete-complete", "--stack-name", "test-stack-id"),
        ])
        for network_id in (*NETWORK_ENV.values(), "vpc-ffffffff", "subnet-ffffffff"):
            self.assertNotIn(network_id, json.dumps(self.calls))

    def test_cleanup_rejects_malformed_fallback_parameters_before_mutation(self):
        valid = [{"ParameterKey": "ExistingVpcId", "ParameterValue": NETWORK_ENV["EXISTING_VPC_ID"]},
                 {"ParameterKey": "ExistingSubnetId", "ParameterValue": NETWORK_ENV["EXISTING_SUBNET_ID"]}]
        cases = [[], valid[:1], valid[1:], valid + valid[:1], [valid[0], valid[0]]]
        for index in (0, 1):
            for value in ("", None, "not-an-id", "vpc-123456789"):
                parameters = copy.deepcopy(valid)
                parameters[index]["ParameterValue"] = value
                cases.append(parameters)
        for parameters in cases:
            with self.subTest(parameters=parameters):
                self.calls.clear()
                def malformed(region, *args, **kwargs):
                    result = self.fallback_cleanup_fixture(region, *args, **kwargs)
                    if args[:2] == ("cloudformation", "describe-stacks"):
                        result["Stacks"][0]["Parameters"] = parameters
                    return result
                with self.assertRaisesRegex(SystemExit, "삭제하지"):
                    self.run_cleanup(malformed)
                self.assert_cleanup_inventory_only()

    def test_cleanup_rejects_fallback_impostor_resources_before_mutation(self):
        base = self.fallback_cleanup_fixture("us-east-1", "cloudformation", "list-stack-resources")
        resources = base["StackResourceSummaries"]
        cases = []
        for index in range(len(resources)):
            cases.append(resources[:index] + resources[index + 1:])
            wrong_type = copy.deepcopy(resources)
            wrong_type[index]["ResourceType"] = "AWS::EC2::VPC"
            cases.append(wrong_type)
        for kind in ("VPC", "Subnet", "InternetGateway", "VPCGatewayAttachment", "Route", "RouteTable",
                     "SubnetRouteTableAssociation", "Instance"):
            cases.append(resources + [{"LogicalResourceId": "UnexpectedResource", "ResourceType": f"AWS::EC2::{kind}"}])
        for kind in ("AWS::CloudFormation::Stack", "Custom::NetworkModifier"):
            cases.append(resources + [{"LogicalResourceId": "UnexpectedResource", "ResourceType": kind}])
        cases.append(resources + [resources[0]])
        for network_id in NETWORK_ENV.values():
            impersonated = copy.deepcopy(resources)
            impersonated[0]["PhysicalResourceId"] = network_id
            cases.append(impersonated)
        for index, inventory in enumerate(cases):
            with self.subTest(case=index):
                self.calls.clear()
                def impostor(region, *args, **kwargs):
                    result = self.fallback_cleanup_fixture(region, *args, **kwargs)
                    if args[:2] == ("cloudformation", "list-stack-resources"):
                        result["StackResourceSummaries"] = inventory
                    return result
                with self.assertRaisesRegex(SystemExit, "삭제하지"):
                    self.run_cleanup(impostor)
                self.assert_cleanup_inventory_only()

    def test_cleanup_normal_mode_keeps_owned_vpc_and_type_guards(self):
        for name in ("WorkshopVpc", "WorkshopInstance", "ResultsBucket"):
            for change in ("missing", "wrong-type"):
                with self.subTest(name=name, change=change):
                    self.calls.clear()
                    def invalid_normal(region, *args, **kwargs):
                        result = self.cleanup_fixture(region, *args, **kwargs)
                        if args[:2] == ("cloudformation", "list-stack-resources"):
                            resources = result["StackResourceSummaries"]
                            if change == "missing":
                                result["StackResourceSummaries"] = [r for r in resources if r["LogicalResourceId"] != name]
                            else:
                                next(r for r in resources if r["LogicalResourceId"] == name)["ResourceType"] = "AWS::EC2::Subnet"
                        return result
                    with patch.dict(os.environ, NETWORK_ENV), self.assertRaisesRegex(SystemExit, "삭제하지"):
                        self.run_cleanup(invalid_normal)
                    self.assert_cleanup_inventory_only()

    def test_cleanup_fallback_preserves_confirmation_tag_and_stack_state_guards(self):
        for confirmation in ("", "OFFLINE-TEST", "offline-test "):
            with self.subTest(confirmation=confirmation), patch.dict(os.environ, {"CONFIRM_DELETE_STACK": confirmation}):
                with patch.object(cleanup, "aws", self.fallback_cleanup_fixture):
                    with self.assertRaisesRegex(SystemExit, "일치"):
                        cleanup.main("us-east-1", "offline-test")
                self.assertEqual(self.calls, [])
        for key, value, message in (("Tags", [], "삭제하지"),
                                    ("Tags", [{"Key": "Workshop", "Value": "other"}], "삭제하지"),
                                    *(("StackStatus", state, "진행 중") for state in
                                      ("CREATE_IN_PROGRESS", "UPDATE_IN_PROGRESS", "DELETE_IN_PROGRESS", "ROLLBACK_IN_PROGRESS"))):
            with self.subTest(key=key, value=value):
                self.calls.clear()
                def guarded(region, *args, **kwargs):
                    result = self.fallback_cleanup_fixture(region, *args, **kwargs)
                    if args[:2] == ("cloudformation", "describe-stacks"):
                        result["Stacks"][0][key] = value
                    return result
                with self.assertRaisesRegex(SystemExit, message):
                    self.run_cleanup(guarded)
                self.assert_cleanup_inventory_only()

    def test_cleanup_fallback_handles_already_stopped_host(self):
        def stopped(region, *args, **kwargs):
            result = self.fallback_cleanup_fixture(region, *args, **kwargs)
            if args[:2] == ("ec2", "describe-instances"):
                result["Reservations"][0]["Instances"][0]["State"]["Name"] = "stopped"
            return result
        self.run_cleanup(stopped)
        self.assertFalse(any(args[:2] in (("ec2", "stop-instances"), ("ec2", "wait")) for args in self.calls))
        self.assertIn(("cloudformation", "delete-stack", "--stack-name", "test-stack-id"), self.calls)

    def test_cleanup_fallback_retries_delete_failed_skipping_deleted_resources(self):
        def retry(region, *args, **kwargs):
            result = self.fallback_cleanup_fixture(region, *args, **kwargs)
            if args[:2] == ("cloudformation", "describe-stacks"):
                result["Stacks"][0]["StackStatus"] = "DELETE_FAILED"
            if args[:2] == ("cloudformation", "list-stack-resources"):
                for resource in result["StackResourceSummaries"]:
                    if resource["LogicalResourceId"] in ("WorkshopInstance", "ResultsBucket"):
                        resource["ResourceStatus"] = "DELETE_COMPLETE"
            return result
        self.run_cleanup(retry)
        self.assertTrue(all(args[0] == "cloudformation" for args in self.calls))
        self.assertIn(("cloudformation", "delete-stack", "--stack-name", "test-stack-id"), self.calls)

    def test_cleanup_rejects_other_stacks_before_mutation(self):
        def wrong_tag(region, *args, **kwargs):
            result = self.cleanup_fixture(region, *args, **kwargs)
            if args[:2] == ("cloudformation", "describe-stacks"):
                result["Stacks"][0]["Tags"] = []
            return result
        with patch.dict(os.environ, {"CONFIRM_DELETE_STACK": "offline-test"}):
            with patch.object(cleanup, "aws", wrong_tag):
                with self.assertRaisesRegex(SystemExit, "삭제하지"):
                    cleanup.main("us-east-1", "offline-test")
        self.assertTrue(all(args[1] in ("describe-stacks", "list-stack-resources") for args in self.calls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
