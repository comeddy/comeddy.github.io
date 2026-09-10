#!/usr/bin/env python3
"""Deployment checks using the AWS CLI; --local makes no AWS/network calls."""

import ipaddress
import json
import os
import re
import subprocess
import sys


def fail(message):
    raise SystemExit(message)


def local_parameters():
    values = {name: os.environ.get(name, "") for name in
              ("AWS_REGION", "AMI_ID", "KEY_NAME", "SSH_CIDR", "STACK_NAME")}
    if not all(values.values()):
        fail("AWS_REGION, AMI_ID, KEY_NAME, SSH_CIDR, STACK_NAME을 설정하세요.")
    values["INSTANCE_TYPE"] = os.environ.get("INSTANCE_TYPE", "g6.4xlarge")
    if values["INSTANCE_TYPE"] not in ("g6.4xlarge", "g6e.2xlarge"):
        fail("INSTANCE_TYPE은 g6.4xlarge 또는 g6e.2xlarge만 허용합니다.")
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", values["AWS_REGION"]):
        fail("AWS_REGION 형식이 올바르지 않습니다.")
    if not re.fullmatch(r"ami-[0-9a-f]{8}(?:[0-9a-f]{9})?", values["AMI_ID"]):
        fail("AMI_ID는 리전에서 직접 확인한 ami-... 값이어야 합니다.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,127}", values["STACK_NAME"]):
        fail("STACK_NAME은 영문자로 시작하는 128자 이하 영문/숫자/하이픈이어야 합니다.")
    try:
        network = ipaddress.ip_network(values["SSH_CIDR"], strict=True)
    except ValueError:
        fail("SSH_CIDR은 현재 공인 IPv4/32 형식이어야 합니다.")
    if network.version != 4 or network.prefixlen != 32:
        fail("SSH_CIDR은 IPv4 주소 하나(/32)만 허용합니다.")
    if any(char in values["KEY_NAME"] for char in ("\n", "\r", "\0")):
        fail("KEY_NAME에 제어 문자를 사용할 수 없습니다.")
    values.update({name: os.environ.get(name, "") for name in
                   ("EXISTING_VPC_ID", "EXISTING_SUBNET_ID")})
    if bool(values["EXISTING_VPC_ID"]) != bool(values["EXISTING_SUBNET_ID"]):
        fail("EXISTING_VPC_ID와 EXISTING_SUBNET_ID는 함께 설정해야 합니다.")
    for name, prefix in (("EXISTING_VPC_ID", "vpc"), ("EXISTING_SUBNET_ID", "subnet")):
        if values[name] and not re.fullmatch(rf"{prefix}-[0-9a-f]{{8}}(?:[0-9a-f]{{9}})?", values[name]):
            fail(f"{name} 형식이 올바르지 않습니다.")
    return values


def aws(values, *args):
    result = subprocess.run(
        ["aws", "--region", values["AWS_REGION"], "--output", "json", *args],
        capture_output=True, text=True, check=False,
        env={**os.environ, "AWS_PAGER": ""},
    )
    if result.returncode:
        fail(f"AWS 읽기 조회 실패 ({' '.join(args[:2])}):\n{result.stderr}")
    return json.loads(result.stdout)


def check_new_network(values, account):
    quotas = aws(values, "service-quotas", "list-service-quotas", "--service-code", "vpc")["Quotas"]
    # Observed Service Quotas codes: VPCs per Region / Internet gateways per Region.
    specs = (("L-F678F1CE", "VPC", "describe-vpcs", "Vpcs"),
             ("L-A4707A72", "InternetGateway", "describe-internet-gateways", "InternetGateways"))
    result = {"NetworkMode": "new"}
    exhausted = []
    for code, name, operation, key in specs:
        quota = next((q for q in quotas if q.get("QuotaCode") == code), None)
        if quota is None:
            fail(f"{name} quota를 확인하지 못했습니다 ({code}). Service Quotas 조회 권한을 확인하세요.")
        count = len(aws(values, "ec2", operation, "--filters", f"Name=owner-id,Values={account}")[key])
        result[f"{name}Quota"] = quota["Value"]
        result[f"Observed{name}Count"] = count
        if count + 1 > quota["Value"]:
            exhausted.append(f"{name}: 한도 {quota['Value']}, 조회 사용량 {count}, 추가 필요 1")
    if exhausted:
        fail("네트워크 quota 부족: " + "; ".join(exhausted) +
             ". EXISTING_VPC_ID와 EXISTING_SUBNET_ID로 기존 public 네트워크를 지정하거나 "
             "Service Quotas에서 증액하세요. 자동 변경은 하지 않습니다.")
    return result


def check_existing_network(values, zones):
    vpc_id, subnet_id = values["EXISTING_VPC_ID"], values["EXISTING_SUBNET_ID"]
    vpcs = aws(values, "ec2", "describe-vpcs", "--vpc-ids", vpc_id)["Vpcs"]
    if len(vpcs) != 1 or vpcs[0].get("VpcId") != vpc_id or vpcs[0].get("State") != "available":
        fail("EXISTING_VPC_ID가 available 상태의 VPC여야 합니다.")
    subnets = aws(values, "ec2", "describe-subnets", "--subnet-ids", subnet_id)["Subnets"]
    if (len(subnets) != 1 or subnets[0].get("SubnetId") != subnet_id
            or subnets[0].get("State") != "available"):
        fail("EXISTING_SUBNET_ID가 available 상태의 subnet이어야 합니다.")
    subnet = subnets[0]
    if subnet["VpcId"] != vpc_id:
        fail("EXISTING_SUBNET_ID가 EXISTING_VPC_ID에 속하지 않습니다.")
    if subnet.get("AvailableIpAddressCount", 0) < 1 or subnet.get("Ipv6Native", False):
        fail("기존 subnet에 사용 가능한 IPv4 주소가 최소 1개 필요합니다.")
    az = subnet["AvailabilityZone"]
    if az not in zones:
        fail(f"기존 subnet AZ {az}는 {values['INSTANCE_TYPE']} 제공 목록에 없습니다: {zones}")
    if os.environ.get("AVAILABILITY_ZONE") not in (None, "", az):
        fail("AVAILABILITY_ZONE이 기존 subnet AZ와 일치하지 않습니다.")
    tables = aws(values, "ec2", "describe-route-tables", "--filters",
                 f"Name=vpc-id,Values={vpc_id}",
                 f"Name=association.subnet-id,Values={subnet_id}")["RouteTables"]
    explicit = bool(tables)
    if not explicit:
        tables = aws(values, "ec2", "describe-route-tables", "--filters",
                     f"Name=vpc-id,Values={vpc_id}", "Name=association.main,Values=true")["RouteTables"]
    if len(tables) != 1 or tables[0].get("VpcId") != vpc_id:
        fail("기존 subnet의 유효 route table을 확인하지 못했습니다.")
    table = tables[0]
    associations = [a for a in table.get("Associations", [])
                    if (a.get("SubnetId") == subnet_id if explicit else a.get("Main"))]
    if len(associations) != 1 or associations[0].get("AssociationState", {}).get("State") != "associated":
        fail("기존 subnet의 route table 연결이 associated 상태여야 합니다.")
    routes = [r for r in table.get("Routes", []) if r.get("DestinationCidrBlock") == "0.0.0.0/0"
              and r.get("State") == "active" and r.get("GatewayId", "").startswith("igw-")]
    if len(routes) != 1:
        fail("기존 subnet의 유효 route table에 active 0.0.0.0/0 IGW 경로가 필요합니다.")
    igw_id = routes[0]["GatewayId"]
    gateways = aws(values, "ec2", "describe-internet-gateways",
                   "--internet-gateway-ids", igw_id)["InternetGateways"]
    # EC2 reports an attached internet gateway's attachment state as "available".
    if (len(gateways) != 1 or gateways[0].get("InternetGatewayId") != igw_id
            or not any(a.get("VpcId") == vpc_id and a.get("State") == "available"
                       for a in gateways[0].get("Attachments", []))):
        fail("기존 subnet의 IGW가 같은 VPC에 연결된 available 상태여야 합니다.")
    return {"NetworkMode": "existing", "ExistingVpcId": vpc_id, "ExistingSubnetId": subnet_id,
            "AvailabilityZone": az, "AvailableIpAddressCount": subnet["AvailableIpAddressCount"],
            "RouteTableId": table["RouteTableId"], "InternetGatewayId": igw_id}


def check_aws(values):
    instance_type = values["INSTANCE_TYPE"]
    identity = aws(values, "sts", "get-caller-identity")
    print(f"대상 계정: {identity['Account']} / {identity['Arn']}", file=sys.stderr)
    # This wrapper creates a new workshop only; updating a live GPU host can replace data.
    stacks = aws(values, "cloudformation", "list-stacks").get("StackSummaries", [])
    if any(s["StackName"] == values["STACK_NAME"] and s["StackStatus"] != "DELETE_COMPLETE"
           for s in stacks):
        fail("같은 이름의 스택이 존재합니다. 새 STACK_NAME을 쓰거나 기존 스택을 정리하세요.")
    images = aws(values, "ec2", "describe-images", "--image-ids", values["AMI_ID"])["Images"]
    if len(images) != 1:
        fail("선택한 리전에서 AMI를 찾지 못했습니다.")
    image = images[0]
    # Canonical's published commercial-region account; a custom image requires an explicit owner.
    trusted_owner = os.environ.get("AMI_OWNER_ID", "099720109477")
    if image["OwnerId"] != trusted_owner:
        fail("AMI 소유자가 예상과 다릅니다. 신뢰한 Ubuntu 22.04 이미지 소유자만 AMI_OWNER_ID로 지정하세요.")
    if (image.get("State") != "available" or image.get("Architecture") != "x86_64"
            or image.get("VirtualizationType") != "hvm" or image.get("RootDeviceType") != "ebs"
            or image.get("Platform") == "windows"):
        fail("available 상태의 Ubuntu x86_64 HVM EBS AMI가 필요합니다.")
    if trusted_owner == "099720109477":
        if not image.get("Name", "").startswith("ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-"):
            fail("Canonical의 표준 Ubuntu Server 22.04 amd64 AMI를 선택하세요.")
    root_device = image["RootDeviceName"]
    if root_device not in ("/dev/sda1", "/dev/xvda"):
        fail(f"이 템플릿에서 지원하지 않는 루트 장치: {root_device}")
    disks = [d for d in image.get("BlockDeviceMappings", []) if "Ebs" in d]
    if len(disks) != 1 or disks[0]["DeviceName"] != root_device:
        fail("루트 EBS 볼륨 하나만 가진 AMI를 선택하세요.")
    if disks[0]["Ebs"].get("VolumeSize", 0) > 200:
        fail("AMI 루트 스냅샷이 200GiB보다 큽니다.")
    aws(values, "ec2", "describe-key-pairs", "--key-names", values["KEY_NAME"])
    offerings = aws(
        values, "ec2", "describe-instance-type-offerings", "--location-type", "availability-zone",
        "--filters", f"Name=instance-type,Values={instance_type}",
    )["InstanceTypeOfferings"]
    zones = sorted(o["Location"] for o in offerings)
    if not zones:
        fail(f"이 리전에는 {instance_type} 제공 AZ가 없습니다.")
    if values.get("EXISTING_VPC_ID"):
        network = check_existing_network(values, zones)
        az = network["AvailabilityZone"]
    else:
        az = os.environ.get("AVAILABILITY_ZONE") or zones[0]
        if az not in zones:
            fail(f"AVAILABILITY_ZONE을 제공 목록에서 선택하세요: {zones}")
        network = check_new_network(values, identity["Account"])
    quotas = aws(values, "service-quotas", "list-service-quotas", "--service-code", "ec2")["Quotas"]
    quota = next((q for q in quotas if q["QuotaName"] == "Running On-Demand G and VT instances"), None)
    if quota is None:
        fail("G 및 VT On-Demand vCPU quota를 확인하지 못했습니다. Service Quotas 콘솔을 확인하세요.")
    reservations = aws(
        values, "ec2", "describe-instances", "--filters",
        "Name=instance-state-name,Values=pending,running",
    )["Reservations"]
    existing = [
        i for r in reservations for i in r["Instances"]
        if i["InstanceType"].split(".")[0].startswith(("g", "vt"))
        and i.get("InstanceLifecycle") != "spot"
    ]
    types = sorted({instance_type, *(i["InstanceType"] for i in existing)})
    details = aws(values, "ec2", "describe-instance-types", "--instance-types", *types)["InstanceTypes"]
    vcpus = {d["InstanceType"]: d["VCpuInfo"]["DefaultVCpus"] for d in details}
    needed = vcpus[instance_type]
    used = sum(vcpus[i["InstanceType"]] for i in existing)
    if used + needed > quota["Value"]:
        fail(f"G/VT vCPU quota 부족: 한도 {quota['Value']}, 조회 사용량 {used}, 추가 필요 {needed}. "
             "Service Quotas에서 미리 증액하세요. 자동 증액은 하지 않습니다.")
    print("AMI의 실제 OS/드라이버 상태는 부팅 후 확인합니다. AZ 제공 여부는 실제 GPU 용량 보장이 아닙니다.",
          file=sys.stderr)
    return {
        **network, "Account": identity["Account"], "Region": values["AWS_REGION"],
        "AmiId": values["AMI_ID"], "AmiName": image.get("Name"), "AmiOwner": image["OwnerId"],
        "InstanceType": instance_type, "AvailabilityZone": az, "RootDeviceName": root_device,
        "GVtOnDemandQuota": quota["Value"], "ObservedUsedVcpus": used, "RequiredVcpus": needed,
    }


if __name__ == "__main__":
    if sys.argv[1:] not in (["--local"], ["--aws"]):
        fail("Usage: preflight.py --local|--aws")
    parameters = local_parameters()
    if sys.argv[1] == "--aws":
        print(json.dumps(check_aws(parameters), ensure_ascii=False, indent=2))
