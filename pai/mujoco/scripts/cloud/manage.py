#!/usr/bin/env python3
"""Microduck CloudFormation CLI. Default: read-only check; no training execution."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

WORKSHOP = "physical-ai-from-cloud-to-robot"
TEMPLATE = Path(__file__).resolve().parents[2] / "static" / "workshop.yaml"
INSTANCE_TYPES = ("g6.2xlarge", "g6.4xlarge")
PAGE_LIMIT = 20
AWS_TIMEOUT = 45


class CloudError(Exception):
    """An actionable input, AWS, or validation error."""


class AwsError(CloudError):
    def __init__(self, operation, stderr):
        self.operation = operation
        self.stderr = stderr.strip()
        super().__init__(f"AWS {operation}: {self.stderr}")


def require(condition, message):
    if not condition:
        raise CloudError(message)


class Aws:
    def __init__(self, region, profile=None):
        self.region = region
        self.profile = profile

    def call(self, service, operation, *arguments):
        command = ["aws", "--region", self.region, "--output", "json", "--no-cli-pager",
                   "--cli-connect-timeout", "10", "--cli-read-timeout", "20"]
        if self.profile:
            command += ["--profile", self.profile]
        command += [service, operation, *arguments]
        environment = dict(os.environ, AWS_PAGER="", AWS_CLI_AUTO_PROMPT="off",
                           AWS_RETRY_MODE="standard", AWS_MAX_ATTEMPTS="2")
        try:
            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=AWS_TIMEOUT, env=environment, check=False)
        except FileNotFoundError as error:
            raise CloudError("AWS CLI v2를 설치하세요. 실행 파일 aws를 찾지 못했습니다.") from error
        except subprocess.TimeoutExpired as error:
            raise CloudError(f"AWS {service} {operation}: {AWS_TIMEOUT}초 제한 초과. "
                             "변경 명령이었다면 status로 결과를 확인하세요.") from error
        if result.returncode:
            raise AwsError(f"{service} {operation}", result.stderr or "AWS CLI failed")
        try:
            body = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError as error:
            raise CloudError(f"AWS {service} {operation}: 올바른 JSON 응답이 아닙니다.") from error
        require(isinstance(body, dict), "AWS 응답은 JSON 객체여야 합니다.")
        return body

    def items(self, service, operation, key, *arguments):
        items, token, seen = [], None, set()
        for _ in range(PAGE_LIMIT):
            page_args = [*arguments, "--max-items", "100"]
            if service == "ec2":
                page_args += ["--page-size", "100"]
            if token:
                page_args += ["--starting-token", token]
            page = self.call(service, operation, *page_args)
            require(isinstance(page.get(key), list), f"AWS {operation}: {key} 목록 누락")
            items.extend(page[key])
            token = page.get("NextToken")
            if not token:
                return items
            require(token not in seen, f"AWS {operation}: 반복 페이지 토큰; 불완전 조회 중단")
            seen.add(token)
        raise CloudError(f"AWS {operation}: {PAGE_LIMIT}페이지 제한 초과; 사용량을 추측하지 않습니다.")


def read_template():
    # JSON is a YAML subset: this keeps local contract checks dependency-free.
    try:
        return json.loads(TEMPLATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CloudError(f"템플릿을 읽지 못했습니다: {TEMPLATE}: {error}") from error


def stack_or_none(aws, name):
    try:
        stacks = aws.call("cloudformation", "describe-stacks", "--stack-name", name).get("Stacks", [])
    except AwsError as error:
        # Permission and connectivity errors must never look like an absent stack.
        if "(ValidationError)" in error.stderr and re.search(
                r"Stack with id .+ does not exist", error.stderr):
            return None
        raise
    require(len(stacks) == 1, "스택 조회 결과가 정확히 하나가 아닙니다.")
    return stacks[0]


def tags_of(resource):
    return {tag["Key"]: tag["Value"] for tag in resource.get("Tags", [])}


def owned_stack(aws, name):
    stack = stack_or_none(aws, name)
    require(stack is not None, f"스택이 없습니다: {name}")
    require(tags_of(stack).get("Workshop") == WORKSHOP,
            f"Workshop={WORKSHOP} 태그가 없는 스택은 관리하지 않습니다.")
    return stack


def inventory(aws, stack):
    resources = aws.items("cloudformation", "list-stack-resources", "StackResourceSummaries",
                          "--stack-name", stack["StackId"])
    expected = read_template()["Resources"]
    for resource in resources:
        definition = expected.get(resource["LogicalResourceId"])
        require(definition and definition["Type"] == resource["ResourceType"],
                "워크숍 계약 외 리소스가 있는 스택입니다. 수동으로 검토하세요.")
    return {r["LogicalResourceId"]: r["PhysicalResourceId"] for r in resources
            if r.get("PhysicalResourceId") and r.get("ResourceStatus") != "DELETE_COMPLETE"}


def instance(aws, identifier):
    body = aws.call("ec2", "describe-instances", "--instance-ids", identifier)
    instances = [i for r in body.get("Reservations", []) for i in r.get("Instances", [])]
    require(len(instances) == 1 and instances[0]["InstanceId"] == identifier,
            "워크숍 EC2 인스턴스를 정확히 하나 조회하지 못했습니다.")
    return instances[0]


def validate_ami(image, instance_type):
    require(image.get("State") == "available" and image.get("ImageType") == "machine",
            "AMI는 available 상태의 machine 이미지여야 합니다.")
    require(image.get("ImageOwnerAlias") == "amazon" and image.get("Public") is True,
            "공개 Amazon 소유 AMI만 허용합니다. owner override는 지원하지 않습니다.")
    require(image.get("Architecture") == "x86_64" and image.get("VirtualizationType") == "hvm"
            and image.get("RootDeviceType") == "ebs" and image.get("EnaSupport") is True,
            "AMI는 x86_64 / HVM / EBS / ENA 조합이어야 합니다.")
    require(not image.get("Platform") and image.get("PlatformDetails") == "Linux/UNIX",
            "Linux/UNIX AMI가 필요합니다.")
    name = re.sub(r"[_-]+", " ", image.get("Name", "").lower())
    require("deep learning" in name and "ami" in name and "gpu" in name
            and re.search(r"ubuntu\s*(22\.04|24\.04)(?!\d)", name) and "neuron" not in name,
            "Amazon GPU Deep Learning AMI Ubuntu 22.04 또는 24.04를 직접 선택하세요.")
    require(not image.get("ProductCodes"), "Marketplace/제품 코드 AMI는 이 계약에서 지원하지 않습니다.")
    require(image.get("ImageAllowed") is not False, "계정의 Allowed AMIs 정책이 차단한 AMI입니다.")
    if image.get("DeprecationTime"):
        deprecated_at = datetime.fromisoformat(image["DeprecationTime"].replace("Z", "+00:00"))
        require(deprecated_at > datetime.now(timezone.utc), "사용 중단된 AMI입니다.")
    boot = image.get("BootMode", "legacy-bios")
    supported_boot = instance_type.get("SupportedBootModes", [])
    require((boot == "uefi-preferred" and any(b in supported_boot for b in ("uefi", "legacy-bios")))
            or boot in supported_boot, "AMI와 인스턴스의 부팅 모드가 호환되지 않습니다.")
    root_name = image.get("RootDeviceName")
    require(root_name in ("/dev/sda1", "/dev/xvda"), "지원하지 않는 AMI 루트 디바이스입니다.")
    ebs = [m for m in image.get("BlockDeviceMappings", []) if "Ebs" in m]
    require(len(ebs) == 1 and ebs[0].get("DeviceName") == root_name,
            "추가 EBS 매핑이 없는 단일 루트 볼륨 DLAMI만 지원합니다.")
    require(0 < ebs[0]["Ebs"].get("VolumeSize", 0) <= 150,
            "AMI 루트 볼륨은 150GiB 이하여야 합니다. 자동 확장은 하지 않습니다.")
    require(bool(ebs[0]["Ebs"].get("SnapshotId")), "루트 EBS snapshot 정보가 없습니다.")
    return root_name


def quota(aws, service, code):
    value = aws.call("service-quotas", "get-service-quota", "--service-code", service,
                     "--quota-code", code).get("Quota", {}).get("Value")
    require(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0,
            f"적용 quota를 확인하지 못했습니다: {service}/{code}")
    return value


def gpu_family(name):
    return bool(re.match(r"^(g\d|vt\d)", name))


def gpu_usage(aws, selected_type):
    reservations = aws.items("ec2", "describe-instances", "Reservations", "--filters",
                             "Name=instance-state-name,Values=pending,running",
                             "Name=instance-type,Values=g*,vt*")
    running = [i for r in reservations for i in r.get("Instances", [])
               if gpu_family(i["InstanceType"]) and not i.get("InstanceLifecycle")]
    capacity = [r for r in aws.items("ec2", "describe-capacity-reservations", "CapacityReservations",
                                    "--filters", "Name=state,Values=active")
                if gpu_family(r["InstanceType"]) and r.get("AvailableInstanceCount", 0) > 0]
    types = {selected_type["InstanceType"]: selected_type}
    missing = sorted({r["InstanceType"] for r in running + capacity} - types.keys())
    for start in range(0, len(missing), 100):
        batch = missing[start:start + 100]
        details = aws.items("ec2", "describe-instance-types", "InstanceTypes", "--instance-types", *batch)
        types.update({t["InstanceType"]: t for t in details})
    require(all(t in types for t in missing), "기존 GPU 인스턴스 타입의 vCPU를 조회하지 못했습니다.")
    # Quotas count default vCPUs, including unused On-Demand Capacity Reservations.
    used = sum(types[i["InstanceType"]]["VCpuInfo"]["DefaultVCpus"] for i in running)
    reserved = sum(types[r["InstanceType"]]["VCpuInfo"]["DefaultVCpus"] * r["AvailableInstanceCount"]
                   for r in capacity)
    return used, reserved


def check(aws, args):
    template = read_template()
    require(template.get("Metadata", {}).get("Workshop") == WORKSHOP, "템플릿 워크숍 표식이 다릅니다.")
    identity = aws.call("sts", "get-caller-identity")
    require(stack_or_none(aws, args.stack_name) is None,
            "같은 이름의 스택이 이미 있습니다. status로 확인하거나 새 이름을 사용하세요. 갱신은 지원하지 않습니다.")
    aws.call("cloudformation", "validate-template", "--template-body", f"file://{TEMPLATE}")
    types = aws.call("ec2", "describe-instance-types", "--instance-types", args.instance_type).get("InstanceTypes", [])
    require(len(types) == 1, "선택한 인스턴스 타입을 조회하지 못했습니다.")
    selected = types[0]
    require("x86_64" in selected.get("ProcessorInfo", {}).get("SupportedArchitectures", [])
            and "on-demand" in selected.get("SupportedUsageClasses", []), "x86_64 On-Demand 타입이 필요합니다.")
    gpus = selected.get("GpuInfo", {}).get("Gpus", [])
    require(len(gpus) == 1 and gpus[0].get("Manufacturer") == "NVIDIA"
            and gpus[0].get("Name") == "L4" and gpus[0].get("Count") == 1,
            "이 계약은 단일 NVIDIA L4 GPU를 가진 G6 타입만 지원합니다.")
    images = aws.call("ec2", "describe-images", "--owners", "amazon", "--image-ids", args.ami_id).get("Images", [])
    require(len(images) == 1 and images[0].get("ImageId") == args.ami_id,
            "이 리전에서 Amazon 소유 AMI를 찾지 못했습니다. 선택한 ID/소유자/리전을 확인하세요.")
    root = validate_ami(images[0], selected)
    zones = aws.call("ec2", "describe-availability-zones", "--filters",
                     "Name=state,Values=available", "Name=zone-type,Values=availability-zone").get("AvailabilityZones", [])
    allowed = {z["ZoneName"] for z in zones if z.get("State") == "available"
               and z.get("ZoneType") == "availability-zone"
               and z.get("OptInStatus") in ("opt-in-not-required", "opted-in")}
    offerings = aws.items("ec2", "describe-instance-type-offerings", "InstanceTypeOfferings",
                          "--location-type", "availability-zone", "--filters",
                          f"Name=instance-type,Values={args.instance_type}")
    available = sorted(allowed & {o["Location"] for o in offerings})
    zone = args.availability_zone or (available[0] if available else None)
    require(zone in available, "선택한 리전/AZ에서 이 인스턴스 타입을 제공하지 않습니다.")
    network = {}
    for label, code, operation, key in (
            ("Vpc", "L-F678F1CE", "describe-vpcs", "Vpcs"),
            ("InternetGateway", "L-A4707A72", "describe-internet-gateways", "InternetGateways")):
        limit = quota(aws, "vpc", code)
        used = len(aws.items("ec2", operation, key))
        require(used + 1 <= limit, f"{label} quota 부족: 사용 {used}, 추가 1, 한도 {limit}")
        network[label] = {"Used": used, "Required": 1, "Quota": limit}
    limit = quota(aws, "ec2", "L-DB2E81BA")
    used, reserved = gpu_usage(aws, selected)
    needed = selected["VCpuInfo"]["DefaultVCpus"]
    require(used + reserved + needed <= limit,
            f"G/VT vCPU quota 부족: 실행 {used}, 미사용 예약 {reserved}, 추가 {needed}, 한도 {limit}")
    return {"Mode": "check", "AccountId": identity["Account"], "Region": aws.region,
            "StackName": args.stack_name, "AmiId": args.ami_id, "AmiName": images[0]["Name"],
            "AmiOwnerId": images[0]["OwnerId"], "RootDeviceName": root,
            "InstanceType": args.instance_type, "AvailabilityZone": zone,
            "Network": network, "GVtVcpu": {"Running": used, "UnusedReservations": reserved,
                                           "Required": needed, "Quota": limit},
            "Access": "SSM; no KeyName and no inbound ports",
            "Limitations": "AZ offering/quota checks do not reserve capacity; 4096 environments and training are unverified."}


def wait_for(label, probe, ready, seconds):
    deadline = time.monotonic() + seconds
    while True:
        value = probe()
        if ready(value):
            return value
        remaining = deadline - time.monotonic()
        require(remaining > 0, f"{label}: {seconds}초 대기 제한 초과. status로 현재 상태를 확인하세요.")
        time.sleep(min(10, remaining))


def ssm_information(aws, identifier):
    information = aws.call("ssm", "describe-instance-information", "--filters",
                           f"Key=InstanceIds,Values={identifier}").get("InstanceInformationList", [])
    return next((item for item in information if item.get("InstanceId") == identifier), {})


def status(aws, args):
    stack = owned_stack(aws, args.stack_name)
    resources = inventory(aws, stack)
    identifier = resources.get("TrainingInstance")
    result = {"StackId": stack["StackId"], "StackStatus": stack["StackStatus"], "Resources": resources,
              "Outputs": {o["OutputKey"]: o["OutputValue"] for o in stack.get("Outputs", [])}}
    if identifier:
        host = instance(aws, identifier)
        result["InstanceState"] = host["State"]["Name"]
        result["SsmPingStatus"] = ssm_information(aws, identifier).get("PingStatus", "NotRegistered")
    return result


def deploy(aws, args):
    plan = check(aws, args)
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    parameters = [{"ParameterKey": key, "ParameterValue": plan[key]} for key in
                  ("AmiId", "InstanceType", "AvailabilityZone", "RootDeviceName")]
    response = aws.call("cloudformation", "create-stack", "--stack-name", args.stack_name,
                        "--template-body", f"file://{TEMPLATE}", "--parameters", json.dumps(parameters),
                        "--capabilities", "CAPABILITY_IAM", "--tags",
                        json.dumps([{"Key": "Workshop", "Value": WORKSHOP}]),
                        "--timeout-in-minutes", "20", "--on-failure", "ROLLBACK")
    stack_id = response["StackId"]
    print(f"생성 요청: {stack_id}", flush=True)

    def created(stack):
        require(stack is not None, "생성 중인 스택을 찾지 못했습니다.")
        state = stack["StackStatus"]
        require(state == "CREATE_IN_PROGRESS" or state == "CREATE_COMPLETE",
                f"스택 생성 실패/롤백: {state}. describe-stack-events로 원인을 확인하세요.")
        return state == "CREATE_COMPLETE"

    stack = wait_for("스택 생성", lambda: stack_or_none(aws, stack_id), created, args.wait_seconds)
    resources = inventory(aws, stack)
    require("TrainingInstance" in resources, "생성 완료 스택에 TrainingInstance가 없습니다.")
    wait_for("SSM Online (NVIDIA/학습 검증은 별도)",
             lambda: ssm_information(aws, resources["TrainingInstance"]),
             lambda data: data.get("PingStatus") == "Online" and data.get("PlatformType") == "Linux",
             args.wait_seconds)
    return status(aws, args)


def stop(aws, args):
    stack = owned_stack(aws, args.stack_name)
    require(not stack["StackStatus"].endswith("_IN_PROGRESS"), "진행 중인 스택 작업이 끝난 뒤 stop을 실행하세요.")
    resources = inventory(aws, stack)
    identifier = resources.get("TrainingInstance")
    require(identifier, "이 스택에 TrainingInstance가 없습니다.")
    host = instance(aws, identifier)
    tags = tags_of(host)
    require(tags.get("aws:cloudformation:stack-id") == stack["StackId"]
            and tags.get("Workshop") == WORKSHOP, "EC2의 스택 소속/워크숍 태그가 일치하지 않습니다.")
    state = host["State"]["Name"]
    require(state in ("running", "stopping", "stopped"), f"stop을 실행할 수 없는 EC2 상태: {state}")
    if state == "running":
        aws.call("ec2", "stop-instances", "--instance-ids", identifier)
    wait_for("EC2 stopped 확인", lambda: instance(aws, identifier),
             lambda current: current["State"]["Name"] == "stopped", args.wait_seconds)
    return {"TrainingInstanceId": identifier, "InstanceState": "stopped", "Verified": True,
            "Notice": "EBS 및 S3 저장 비용은 계속 발생합니다."}


def destroy(aws, args):
    require(args.confirm_stack_name == args.stack_name,
            "destroy에는 --confirm-stack-name에 동일한 스택 이름을 입력해야 합니다.")
    stack = owned_stack(aws, args.stack_name)
    require(not stack["StackStatus"].endswith("_IN_PROGRESS"), "진행 중인 스택 작업이 끝난 뒤 destroy를 실행하세요.")
    deployed = aws.call("cloudformation", "get-template", "--stack-name", stack["StackId"],
                        "--template-stage", "Original").get("TemplateBody")
    if isinstance(deployed, str):
        deployed = json.loads(deployed)
    require(isinstance(deployed, dict) and deployed.get("Metadata", {}).get("Workshop") == WORKSHOP,
            "배포된 템플릿의 워크숍 표식이 다릅니다. 수동으로 검토하세요.")
    for logical_id in ("ArtifactBucket", "ArtifactBucketPolicy"):
        resource = deployed.get("Resources", {}).get(logical_id, {})
        require(resource.get("DeletionPolicy") == "Retain" and resource.get("UpdateReplacePolicy") == "Retain",
                f"배포된 {logical_id}의 Retain 정책을 확인하지 못했습니다. 삭제하지 않습니다.")
    resources = inventory(aws, stack)
    bucket = resources.get("ArtifactBucket") or next((o["OutputValue"] for o in stack.get("Outputs", [])
                                                     if o["OutputKey"] == "ArtifactBucketName"), None)
    print(json.dumps({"DeletingStackId": stack["StackId"], "RetainedArtifactBucket": bucket,
                      "Notice": "EC2 루트 디스크는 삭제됩니다. S3 버전/삭제 마커는 자동 삭제하지 않습니다."},
                     ensure_ascii=False, indent=2), flush=True)
    aws.call("cloudformation", "delete-stack", "--stack-name", stack["StackId"])

    def deleted(current):
        if current is None:
            return True
        require(current["StackStatus"] != "DELETE_FAILED", "스택 DELETE_FAILED: 이벤트를 확인하세요. 추가 삭제는 수행하지 않습니다.")
        return current["StackStatus"] == "DELETE_COMPLETE"

    wait_for("스택 삭제", lambda: stack_or_none(aws, stack["StackId"]), deleted, args.wait_seconds)
    return {"StackId": stack["StackId"], "StackStatus": "DELETE_COMPLETE", "RetainedArtifactBucket": bucket,
            "ManualCleanup": "docs/cloud-contract.md의 버전별 수동 정리 절차를 확인하세요."}


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("command", nargs="?", choices=("check", "deploy", "status", "stop", "destroy"), default="check")
    cli.add_argument("--region", default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"))
    cli.add_argument("--profile", help="AWS CLI profile; 자격 증명은 파일에 저장하지 않습니다.")
    cli.add_argument("--stack", "--stack-name", dest="stack_name", default="physical-ai-microduck")
    cli.add_argument("--ami-id", help="이 리전에서 직접 선택한 Amazon GPU DLAMI ID; 기본값 없음")
    cli.add_argument("--instance-type", choices=INSTANCE_TYPES, default="g6.2xlarge")
    cli.add_argument("--availability-zone", help="생략하면 조회된 제공 AZ 중 이름순 첫 번째 선택")
    cli.add_argument("--confirm-stack-name", help="destroy에서만 사용; --stack-name 값과 정확히 일치")
    cli.add_argument("--wait-seconds", type=int, default=1200, help="각 상태 대기 제한: 1..3600초 (기본 1200)")
    return cli


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        require(args.region and re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d+", args.region), "--region 또는 AWS_REGION을 지정하세요.")
        require(re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,127}", args.stack_name), "스택 이름은 영문자로 시작하며 영문/숫자/하이픈 128자 이하여야 합니다.")
        require(1 <= args.wait_seconds <= 3600, "--wait-seconds 범위는 1..3600입니다.")
        if args.command in ("check", "deploy"):
            require(args.ami_id and re.fullmatch(r"ami-[0-9a-f]{17}", args.ami_id), "--ami-id에 직접 검증할 AMI ID를 지정하세요.")
        if args.command == "destroy":
            require(args.confirm_stack_name == args.stack_name, "destroy 확인값이 일치하지 않습니다: --confirm-stack-name")
        elif args.confirm_stack_name is not None:
            raise CloudError("--confirm-stack-name은 destroy에서만 사용합니다.")
        result = {"check": check, "deploy": deploy, "status": status, "stop": stop, "destroy": destroy}[args.command](Aws(args.region, args.profile), args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CloudError, KeyError, TypeError, ValueError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("중단했습니다. AWS 변경 요청은 계속 진행될 수 있습니다. status로 확인하세요.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
