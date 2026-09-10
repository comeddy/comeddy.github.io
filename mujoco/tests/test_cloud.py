"""Offline cloud contract tests; every AWS subprocess is a fixture or a local stub."""

from collections import deque
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("microduck_cloud", ROOT / "scripts/cloud/manage.py")
cloud = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cloud)
AMI = "ami-0123456789abcdef0"
INSTANCE = "i-0123456789abcdef0"
STACK = "arn:aws:cloudformation:us-west-2:123456789012:stack/physical-ai-microduck/fixture"
BUCKET = "physical-ai-microduck-artifacts-fixture"
NOT_FOUND = (255, "", "An error occurred (ValidationError) when calling DescribeStacks: Stack with id physical-ai-microduck does not exist")


def selected_type(name="g6.2xlarge", cpus=8):
    return {"InstanceType": name, "VCpuInfo": {"DefaultVCpus": cpus},
            "ProcessorInfo": {"SupportedArchitectures": ["x86_64"]},
            "SupportedUsageClasses": ["on-demand", "spot"], "SupportedBootModes": ["legacy-bios", "uefi"],
            "GpuInfo": {"Gpus": [{"Manufacturer": "NVIDIA", "Name": "L4", "Count": 1}]}}


def image():
    return {"ImageId": AMI, "OwnerId": "123456789012", "ImageOwnerAlias": "amazon", "Public": True,
            "Name": "Deep Learning OSS Nvidia Driver AMI GPU PyTorch (Ubuntu 24.04) 20260901",
            "State": "available", "ImageType": "machine", "Architecture": "x86_64",
            "VirtualizationType": "hvm", "RootDeviceType": "ebs", "EnaSupport": True,
            "PlatformDetails": "Linux/UNIX", "RootDeviceName": "/dev/sda1", "BootMode": "uefi-preferred",
            "BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 100, "SnapshotId": "snap-fixture"}}]}


def stack(state="CREATE_COMPLETE", marked=True):
    return {"Stacks": [{"StackId": STACK, "StackName": "physical-ai-microduck", "StackStatus": state,
                        "Tags": [{"Key": "Workshop", "Value": cloud.WORKSHOP}] if marked else [],
                        "Outputs": [{"OutputKey": "TrainingInstanceId", "OutputValue": INSTANCE},
                                    {"OutputKey": "ArtifactBucketName", "OutputValue": BUCKET}]}]}


def host(state="running", marked=True):
    return {"Reservations": [{"Instances": [{"InstanceId": INSTANCE, "InstanceType": "g6.2xlarge",
            "State": {"Name": state}, "Tags": [{"Key": "Workshop", "Value": cloud.WORKSHOP},
            {"Key": "aws:cloudformation:stack-id", "Value": STACK}] if marked else []}]}]}


def ssm(ping="Online"):
    return {"InstanceInformationList": [{"InstanceId": INSTANCE, "PingStatus": ping, "PlatformType": "Linux"}]}


class FixtureAws:
    """Intercept subprocess.run, keeping the real CLI argument construction and JSON decoding."""
    def __init__(self):
        self.calls = []
        self.quotas = {"L-F678F1CE": 5, "L-A4707A72": 5, "L-DB2E81BA": 32}
        self.responses = {
            ("sts", "get-caller-identity"): {"Account": "123456789012"},
            ("cloudformation", "describe-stacks"): NOT_FOUND,
            ("cloudformation", "validate-template"): {"Parameters": []},
            ("cloudformation", "get-template"): {"TemplateBody": cloud.read_template()},
            ("ec2", "describe-instance-types"): {"InstanceTypes": [selected_type()]},
            ("ec2", "describe-images"): {"Images": [image()]},
            ("ec2", "describe-availability-zones"): {"AvailabilityZones": [
                {"ZoneName": "us-west-2a", "ZoneType": "availability-zone", "State": "available", "OptInStatus": "opt-in-not-required"}]},
            ("ec2", "describe-instance-type-offerings"): {"InstanceTypeOfferings": [{"Location": "us-west-2a"}]},
            ("ec2", "describe-vpcs"): {"Vpcs": []},
            ("ec2", "describe-internet-gateways"): {"InternetGateways": []},
            ("ec2", "describe-instances"): {"Reservations": []},
            ("ec2", "describe-capacity-reservations"): {"CapacityReservations": []},
            ("service-quotas", "get-service-quota"): None,
            ("cloudformation", "list-stack-resources"): {"StackResourceSummaries": [
                {"LogicalResourceId": "TrainingInstance", "PhysicalResourceId": INSTANCE, "ResourceType": "AWS::EC2::Instance", "ResourceStatus": "CREATE_COMPLETE"},
                {"LogicalResourceId": "ArtifactBucket", "PhysicalResourceId": BUCKET, "ResourceType": "AWS::S3::Bucket", "ResourceStatus": "CREATE_COMPLETE"}]},
            ("cloudformation", "create-stack"): {"StackId": STACK},
            ("cloudformation", "delete-stack"): {},
            ("ec2", "stop-instances"): {},
            ("ssm", "describe-instance-information"): ssm(),
        }

    def run(self, command, **kwargs):
        services = {"sts", "ec2", "cloudformation", "ssm", "service-quotas"}
        index = next(i for i, arg in enumerate(command) if arg in services)
        key = tuple(command[index:index + 2])
        self.calls.append((key, command, kwargs))
        if key not in self.responses:
            raise AssertionError(f"Unexpected AWS operation: {key}")
        response = self.responses[key]
        if isinstance(response, deque):
            if not response:
                raise AssertionError(f"Exhausted fixture: {key}")
            response = response.popleft()
        if key == ("service-quotas", "get-service-quota") and response is None:
            response = {"Quota": {"Value": self.quotas[command[command.index("--quota-code") + 1]]}}
        if isinstance(response, Exception):
            raise response
        if isinstance(response, tuple):
            code, stdout, stderr = response
            return subprocess.CompletedProcess(command, code, stdout, stderr)
        return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

    def operations(self):
        return [key for key, _, _ in self.calls]


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.fixture = FixtureAws()
        self.mock = patch.object(cloud.subprocess, "run", side_effect=self.fixture.run)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.aws = cloud.Aws("us-west-2")
        self.args = cloud.parser().parse_args(["--region", "us-west-2", "--ami-id", AMI, "--wait-seconds", "1"])

    def assert_no_mutation(self):
        mutations = {("ec2", "stop-instances"), ("cloudformation", "create-stack"), ("cloudformation", "delete-stack")}
        self.assertFalse(mutations.intersection(self.fixture.operations()))

    def test_default_check_is_read_only_and_uses_trusted_owner(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cloud.main(["--region", "us-west-2", "--ami-id", AMI]), 0)
        self.assert_no_mutation()
        command = next(cmd for key, cmd, _ in self.fixture.calls if key == ("ec2", "describe-images"))
        self.assertEqual(command[command.index("--owners") + 1], "amazon")
        for _, _, kwargs in self.fixture.calls:
            self.assertFalse(kwargs.get("shell", False))
            self.assertEqual(kwargs["timeout"], 45)
            self.assertEqual(kwargs["env"]["AWS_MAX_ATTEMPTS"], "2")

    def test_check_returns_dynamic_ami_root_zone_and_quota(self):
        result = cloud.check(self.aws, self.args)
        self.assertEqual(result["RootDeviceName"], "/dev/sda1")
        self.assertEqual(result["AvailabilityZone"], "us-west-2a")
        self.assertEqual(result["GVtVcpu"]["Required"], 8)

    def test_g6_4xlarge_uses_16_vcpu_and_not_hardcoded_8(self):
        self.args.instance_type = "g6.4xlarge"
        self.fixture.responses[("ec2", "describe-instance-types")] = {"InstanceTypes": [selected_type("g6.4xlarge", 16)]}
        self.fixture.quotas["L-DB2E81BA"] = 15
        with self.assertRaisesRegex(cloud.CloudError, "vCPU quota 부족"):
            cloud.check(self.aws, self.args)
        self.assert_no_mutation()

    def test_ubuntu_2204_and_2404_supported(self):
        for version in ("22.04", "24.04"):
            candidate = image()
            candidate["Name"] = f"Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu {version})"
            self.assertEqual(cloud.validate_ami(candidate, selected_type()), "/dev/sda1")

    def test_rejects_unsafe_or_incompatible_amis(self):
        cases = [
            {"State": "pending"}, {"ImageType": "kernel"}, {"ImageOwnerAlias": "aws-marketplace"},
            {"Public": False}, {"Architecture": "arm64"}, {"VirtualizationType": "paravirtual"},
            {"RootDeviceType": "instance-store"}, {"EnaSupport": False}, {"Platform": "windows"},
            {"PlatformDetails": "Windows"}, {"Name": "Deep Learning GPU AMI Ubuntu 20.04"},
            {"Name": "Ubuntu 24.04"}, {"Name": "Deep Learning Neuron AMI Ubuntu 24.04"},
            {"ProductCodes": [{"ProductCodeType": "marketplace"}]}, {"ImageAllowed": False},
            {"DeprecationTime": "2000-01-01T00:00:00Z"}, {"RootDeviceName": "/dev/wrong"},
            {"BootMode": "unknown"}, {"BlockDeviceMappings": []},
            {"BlockDeviceMappings": [{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 151, "SnapshotId": "snap-fixture"}}]},
            {"BlockDeviceMappings": image()["BlockDeviceMappings"] + [{"DeviceName": "/dev/sdf", "Ebs": {"VolumeSize": 1}}]},
        ]
        for changed in cases:
            with self.subTest(changed=changed):
                candidate = image()
                candidate.update(changed)
                with self.assertRaises(cloud.CloudError):
                    cloud.validate_ami(candidate, selected_type())

    def test_amazon_filter_empty_response_fails_closed(self):
        self.fixture.responses[("ec2", "describe-images")] = {"Images": []}
        with self.assertRaisesRegex(cloud.CloudError, "Amazon 소유 AMI"):
            cloud.check(self.aws, self.args)
        self.assert_no_mutation()

    def test_wrong_gpu_or_unavailable_az_rejected(self):
        self.args.availability_zone = "us-west-2z"
        with self.assertRaisesRegex(cloud.CloudError, "리전/AZ"):
            cloud.check(self.aws, self.args)
        self.args.availability_zone = None
        self.fixture.responses[("ec2", "describe-instance-types")]["InstanceTypes"][0]["GpuInfo"]["Gpus"][0]["Name"] = "L40S"
        with self.assertRaisesRegex(cloud.CloudError, "NVIDIA L4"):
            cloud.check(self.aws, self.args)

    def test_network_quotas_and_permission_fail_closed(self):
        for operation, result_key, code in (("describe-vpcs", "Vpcs", "L-F678F1CE"),
                                             ("describe-internet-gateways", "InternetGateways", "L-A4707A72")):
            with self.subTest(operation=operation):
                self.fixture.quotas[code] = 1
                self.fixture.responses[("ec2", operation)] = {result_key: [{}]}
                with self.assertRaisesRegex(cloud.CloudError, "quota 부족"):
                    cloud.check(self.aws, self.args)
                self.fixture.responses[("ec2", operation)] = {result_key: []}
        self.fixture.responses[("service-quotas", "get-service-quota")] = (255, "", "AccessDeniedException")
        with self.assertRaises(cloud.AwsError):
            cloud.check(self.aws, self.args)
        self.assert_no_mutation()

    def test_quota_counts_default_vcpus_and_unused_reservations_excluding_spot(self):
        self.fixture.responses[("ec2", "describe-instances")] = {"Reservations": [{"Instances": [
            {"InstanceType": "g6.2xlarge", "CpuOptions": {"CoreCount": 1, "ThreadsPerCore": 1}},
            {"InstanceType": "g6.2xlarge", "InstanceLifecycle": "spot"}]}]}
        self.fixture.responses[("ec2", "describe-capacity-reservations")] = {"CapacityReservations": [
            {"InstanceType": "g6.2xlarge", "AvailableInstanceCount": 2}]}
        self.assertEqual(cloud.gpu_usage(self.aws, selected_type()), (8, 16))
        self.fixture.quotas["L-DB2E81BA"] = 31
        with self.assertRaisesRegex(cloud.CloudError, "미사용 예약 16"):
            cloud.check(self.aws, self.args)

    def test_existing_stack_or_access_denied_never_creates(self):
        for response in (stack(), (255, "", "An error occurred (AccessDenied) when calling DescribeStacks")):
            self.fixture.responses[("cloudformation", "describe-stacks")] = response
            with self.assertRaises(cloud.CloudError):
                cloud.deploy(self.aws, self.args)
        self.assert_no_mutation()

    def test_pagination_follows_tokens_and_has_a_bound(self):
        self.fixture.responses[("ec2", "describe-vpcs")] = deque([
            {"Vpcs": [1], "NextToken": "opaque-token"}, {"Vpcs": [2]}])
        self.assertEqual(self.aws.items("ec2", "describe-vpcs", "Vpcs"), [1, 2])
        self.assertIn("opaque-token", self.fixture.calls[-1][1])
        self.fixture.responses[("ec2", "describe-vpcs")] = {"Vpcs": [1], "NextToken": "repeated"}
        with self.assertRaisesRegex(cloud.CloudError, "반복 페이지 토큰"):
            self.aws.items("ec2", "describe-vpcs", "Vpcs")
        self.fixture.responses[("ec2", "describe-vpcs")] = deque([
            {"Vpcs": [1], "NextToken": "one"}, {"Vpcs": [2], "NextToken": "two"}])
        with patch.object(cloud, "PAGE_LIMIT", 2), self.assertRaisesRegex(cloud.CloudError, "페이지 제한"):
            self.aws.items("ec2", "describe-vpcs", "Vpcs")

    def test_cfn_pagination_does_not_send_unsupported_page_size(self):
        cloud.inventory(self.aws, stack()["Stacks"][0])
        self.assertNotIn("--page-size", self.fixture.calls[-1][1])

    def test_deploy_creates_only_after_check_and_waits_for_ssm(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = deque([
            NOT_FOUND, stack("CREATE_IN_PROGRESS"), stack(), stack()])
        self.fixture.responses[("ec2", "describe-instances")] = deque([{"Reservations": []}, host()])
        self.fixture.responses[("ssm", "describe-instance-information")] = deque([ssm("ConnectionLost"), ssm(), ssm()])
        with patch.object(cloud.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            result = cloud.deploy(self.aws, self.args)
        self.assertEqual(result["SsmPingStatus"], "Online")
        ops = self.fixture.operations()
        self.assertLess(ops.index(("service-quotas", "get-service-quota")), ops.index(("cloudformation", "create-stack")))
        create = next(cmd for key, cmd, _ in self.fixture.calls if key == ("cloudformation", "create-stack"))
        parameters = json.loads(create[create.index("--parameters") + 1])
        self.assertEqual({p["ParameterKey"] for p in parameters}, {"AmiId", "InstanceType", "AvailabilityZone", "RootDeviceName"})
        self.assertNotIn("KeyName", str(parameters))
        self.assertNotIn("deploy", create)

    def test_stack_alias_and_profile_are_preserved(self):
        args = cloud.parser().parse_args(["status", "--stack", "chosen-stack", "--profile", "my profile"])
        self.assertEqual(args.stack_name, "chosen-stack")
        self.assertEqual(cloud.parser().parse_args(["--stack-name", "same"]).stack_name, "same")
        cloud.Aws("us-west-2", args.profile).call("sts", "get-caller-identity")
        command = self.fixture.calls[-1][1]
        self.assertEqual(command[command.index("--profile") + 1], "my profile")

    def test_deploy_failure_does_not_claim_ready(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = deque([NOT_FOUND, stack("ROLLBACK_IN_PROGRESS")])
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(cloud.CloudError, "생성 실패/롤백"):
            cloud.deploy(self.aws, self.args)
        self.assertNotIn(("ssm", "describe-instance-information"), self.fixture.operations())
        self.assertNotIn(("cloudformation", "delete-stack"), self.fixture.operations())

    def test_deploy_ssm_timeout_leaves_stack_for_explicit_cleanup(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = deque([NOT_FOUND, stack()])
        self.fixture.responses[("ssm", "describe-instance-information")] = ssm("ConnectionLost")
        with patch.object(cloud.time, "monotonic", side_effect=[0, 0, 2]), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(cloud.CloudError, "SSM Online.*대기 제한 초과"):
                cloud.deploy(self.aws, self.args)
        self.assertNotIn(("cloudformation", "delete-stack"), self.fixture.operations())

    def test_status_reports_unregistered_ssm_without_mutating(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack()
        self.fixture.responses[("ec2", "describe-instances")] = host()
        self.fixture.responses[("ssm", "describe-instance-information")] = {"InstanceInformationList": []}
        result = cloud.status(self.aws, self.args)
        self.assertEqual(result["SsmPingStatus"], "NotRegistered")
        self.assertEqual(result["Outputs"]["ArtifactBucketName"], BUCKET)
        self.assert_no_mutation()

    def test_stop_verifies_final_state_and_scopes_to_cfn_instance(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack()
        self.fixture.responses[("ec2", "describe-instances")] = deque([host(), host("stopping"), host("stopped")])
        with patch.object(cloud.time, "sleep"):
            result = cloud.stop(self.aws, self.args)
        self.assertEqual(result["InstanceState"], "stopped")
        self.assertTrue(result["Verified"])
        stop_command = next(cmd for key, cmd, _ in self.fixture.calls if key == ("ec2", "stop-instances"))
        self.assertEqual(stop_command[-2:], ["--instance-ids", INSTANCE])

    def test_stop_already_stopped_is_idempotent(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack()
        self.fixture.responses[("ec2", "describe-instances")] = host("stopped")
        self.assertTrue(cloud.stop(self.aws, self.args)["Verified"])
        self.assert_no_mutation()

    def test_stop_timeout_does_not_claim_stopped(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack()
        self.fixture.responses[("ec2", "describe-instances")] = deque([host(), host("stopping")])
        with patch.object(cloud.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaisesRegex(cloud.CloudError, "대기 제한 초과"):
                cloud.stop(self.aws, self.args)

    def test_stop_rejects_foreign_instance(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack()
        self.fixture.responses[("ec2", "describe-instances")] = host(marked=False)
        with self.assertRaisesRegex(cloud.CloudError, "소속/워크숍"):
            cloud.stop(self.aws, self.args)
        self.assert_no_mutation()

    def test_destroy_requires_exact_confirmation_before_aws(self):
        self.args.confirm_stack_name = "different-stack"
        with self.assertRaisesRegex(cloud.CloudError, "동일한 스택 이름"):
            cloud.destroy(self.aws, self.args)
        self.assertEqual(self.fixture.calls, [])

    def test_mutations_reject_unmarked_stacks(self):
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack(marked=False)
        self.args.confirm_stack_name = self.args.stack_name
        for operation in (cloud.destroy, cloud.stop):
            with self.assertRaisesRegex(cloud.CloudError, "태그가 없는"):
                operation(self.aws, self.args)
        self.assert_no_mutation()

    def test_destroy_rejects_unrelated_resources_and_nonretaining_deployed_template(self):
        self.args.confirm_stack_name = self.args.stack_name
        self.fixture.responses[("cloudformation", "describe-stacks")] = stack()
        deployed = self.fixture.responses[("cloudformation", "get-template")]["TemplateBody"]
        deployed["Resources"]["ArtifactBucket"]["DeletionPolicy"] = "Delete"
        with self.assertRaisesRegex(cloud.CloudError, "Retain 정책"):
            cloud.destroy(self.aws, self.args)
        deployed["Resources"]["ArtifactBucket"]["DeletionPolicy"] = "Retain"
        self.fixture.responses[("cloudformation", "list-stack-resources")]["StackResourceSummaries"].append(
            {"LogicalResourceId": "OtherDatabase", "ResourceType": "AWS::RDS::DBInstance"})
        with self.assertRaisesRegex(cloud.CloudError, "계약 외 리소스"):
            cloud.destroy(self.aws, self.args)
        self.assert_no_mutation()

    def test_destroy_retains_bucket_and_uses_stack_arn(self):
        self.args.confirm_stack_name = self.args.stack_name
        self.fixture.responses[("cloudformation", "describe-stacks")] = deque([stack(), stack("DELETE_IN_PROGRESS"), stack("DELETE_COMPLETE")])
        with patch.object(cloud.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            result = cloud.destroy(self.aws, self.args)
        self.assertEqual(result["RetainedArtifactBucket"], BUCKET)
        self.assertEqual(result["StackStatus"], "DELETE_COMPLETE")
        mutation = [cmd for key, cmd, _ in self.fixture.calls if key == ("cloudformation", "delete-stack")]
        self.assertEqual(len(mutation), 1)
        self.assertEqual(mutation[0][-2:], ["--stack-name", STACK])
        self.assertTrue(all(key[0] != "s3" for key in self.fixture.operations()))

    def test_destroy_failure_does_not_retry_or_force_delete(self):
        self.args.confirm_stack_name = self.args.stack_name
        self.fixture.responses[("cloudformation", "describe-stacks")] = deque([stack(), stack("DELETE_FAILED")])
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(cloud.CloudError, "DELETE_FAILED"):
            cloud.destroy(self.aws, self.args)
        self.assertEqual(self.fixture.operations().count(("cloudformation", "delete-stack")), 1)

    def test_cli_errors_invalid_json_missing_binary_and_timeout_are_actionable(self):
        for response, message in [((0, "not JSON", ""), "JSON"),
                                  (FileNotFoundError(), "AWS CLI v2"),
                                  (subprocess.TimeoutExpired(["aws"], 45), "45초 제한")]:
            self.fixture.responses[("sts", "get-caller-identity")] = response
            with self.assertRaisesRegex(cloud.CloudError, message):
                self.aws.call("sts", "get-caller-identity")

    def test_invalid_local_arguments_do_not_call_aws(self):
        cases = [["--region", "us-west-2"],
                 ["--region", "us-west-2", "--ami-id", AMI, "--stack-name", "../other"],
                 ["destroy", "--region", "us-west-2"],
                 ["status", "--region", "us-west-2", "--wait-seconds", "0"]]
        for arguments in cases:
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(cloud.main(arguments), 1)
        self.assertEqual(self.fixture.calls, [])


class TemplateTests(unittest.TestCase):
    def test_single_host_network_and_no_key_or_bootstrap(self):
        template = cloud.read_template()
        resources = template["Resources"]
        for kind in ("AWS::EC2::Instance", "AWS::EC2::VPC", "AWS::EC2::Subnet", "AWS::EC2::InternetGateway", "AWS::S3::Bucket"):
            self.assertEqual(sum(r["Type"] == kind for r in resources.values()), 1)
        props = resources["TrainingInstance"]["Properties"]
        self.assertNotIn("KeyName", props)
        self.assertNotIn("UserData", props)
        self.assertNotIn("Default", template["Parameters"]["AmiId"])
        self.assertEqual(template["Parameters"]["InstanceType"]["AllowedValues"], ["g6.2xlarge", "g6.4xlarge"])
        self.assertEqual(template["Parameters"]["InstanceType"]["Default"], "g6.2xlarge")
        metadata = resources["HostLaunchTemplate"]["Properties"]["LaunchTemplateData"]["MetadataOptions"]
        self.assertEqual(metadata["HttpTokens"], "required")
        self.assertEqual(metadata["HttpPutResponseHopLimit"], 1)
        disk = props["BlockDeviceMappings"][0]["Ebs"]
        self.assertEqual(disk, {"VolumeSize": 150, "VolumeType": "gp3", "Encrypted": True, "DeleteOnTermination": True})
        security = resources["HostSecurityGroup"]["Properties"]
        self.assertEqual(security["SecurityGroupIngress"], [])
        self.assertCountEqual(
            [(rule["IpProtocol"], rule["FromPort"], rule["ToPort"], rule["CidrIp"])
             for rule in security["SecurityGroupEgress"]],
            [("tcp", 443, 443, "0.0.0.0/0"), ("tcp", 80, 80, "0.0.0.0/0")],
        )
        self.assertEqual(resources["InternetRoute"]["Properties"]["GatewayId"], {"Ref": "InternetGateway"})
        self.assertTrue(props["NetworkInterfaces"][0]["AssociatePublicIpAddress"])

    def test_artifact_bucket_is_private_encrypted_versioned_and_retained(self):
        resources = cloud.read_template()["Resources"]
        bucket = resources["ArtifactBucket"]
        self.assertEqual(bucket["DeletionPolicy"], "Retain")
        self.assertEqual(bucket["UpdateReplacePolicy"], "Retain")
        props = bucket["Properties"]
        self.assertTrue(all(props["PublicAccessBlockConfiguration"].values()))
        self.assertEqual(props["VersioningConfiguration"]["Status"], "Enabled")
        self.assertEqual(props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"], "AES256")
        policy = resources["ArtifactBucketPolicy"]
        self.assertEqual(policy["DeletionPolicy"], "Retain")
        self.assertEqual(policy["Properties"]["PolicyDocument"]["Statement"][0]["Effect"], "Deny")
        role = resources["HostRole"]["Properties"]
        self.assertIn("AmazonSSMManagedInstanceCore", str(role["ManagedPolicyArns"]))
        self.assertNotIn("DeleteObject", str(role["Policies"]))
        self.assertNotIn('"Action": "*"', json.dumps(role))
        statements = role["Policies"][0]["PolicyDocument"]["Statement"]
        readable = next(s for s in statements if "s3:GetObject" in s["Action"])
        writable = next(s for s in statements if "s3:PutObject" in s["Action"])
        self.assertEqual(readable["Resource"], [
            {"Fn::Sub": "${ArtifactBucket.Arn}/workshop/*"}, {"Fn::Sub": "${ArtifactBucket.Arn}/runs/*"}])
        self.assertEqual(writable["Resource"], {"Fn::Sub": "${ArtifactBucket.Arn}/runs/*"})



class RealProcessTests(unittest.TestCase):
    def test_default_command_in_real_process_only_attempts_read(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            log = temporary / "calls.jsonl"
            stub = temporary / "aws"
            stub.write_text("#!" + sys.executable + "\n" +
                            "import json, os, sys\n" +
                            "with open(os.environ['CLOUD_TEST_LOG'], 'a') as out: out.write(json.dumps(sys.argv[1:])+'\\n')\n" +
                            "sys.stderr.write('fixture AccessDenied: read-only STS test\\n')\n" +
                            "sys.exit(255)\n", encoding="utf-8")
            stub.chmod(0o755)
            environment = dict(os.environ, PATH=str(temporary) + os.pathsep + os.environ.get("PATH", ""),
                               CLOUD_TEST_LOG=str(log), PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/cloud/manage.py"),
                                     "--region", "us-west-2", "--ami-id", AMI],
                                    capture_output=True, text=True, timeout=10, env=environment)
            self.assertEqual(result.returncode, 1)
            self.assertIn("fixture AccessDenied", result.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][-2:], ["sts", "get-caller-identity"])


if __name__ == "__main__":
    unittest.main()
