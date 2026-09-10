#!/usr/bin/env python3
"""Remove only resources discovered from the explicitly confirmed workshop stack."""

import json
import os
import re
import subprocess
import sys


EXISTING_NETWORK_RESOURCE_TYPES = {
    "WorkshopSecurityGroup": "AWS::EC2::SecurityGroup",
    "ResultsBucket": "AWS::S3::Bucket",
    "ResultsBucketPolicy": "AWS::S3::BucketPolicy",
    "WorkshopRole": "AWS::IAM::Role",
    "WorkshopInstanceProfile": "AWS::IAM::InstanceProfile",
    "WorkshopLaunchTemplate": "AWS::EC2::LaunchTemplate",
    "WorkshopInstance": "AWS::EC2::Instance",
}


def aws(region, *args, json_output=True):
    command = ["aws", "--region", region, *args]
    if json_output:
        command += ["--output", "json"]
    result = subprocess.run(command, capture_output=True, text=True, check=True,
                            env={**os.environ, "AWS_PAGER": ""})
    if not json_output:
        return result.stdout
    try:
        # AWS CLI can print nothing for a successful empty object (e.g. an unversioned bucket).
        response = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        raise SystemExit(f"AWS 응답 형식 오류 ({' '.join(args[:2])}): 유효한 JSON 객체가 필요합니다.")
    if not isinstance(response, dict):
        raise SystemExit(f"AWS 응답 형식 오류 ({' '.join(args[:2])}): JSON 객체가 필요합니다.")
    return response


def main(region, stack_name):
    if os.environ.get("CONFIRM_DELETE_STACK") != stack_name:
        raise SystemExit("CONFIRM_DELETE_STACK과 삭제할 스택 이름이 일치해야 합니다.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,127}", stack_name):
        raise SystemExit("스택 이름 형식이 올바르지 않습니다.")
    stack = aws(region, "cloudformation", "describe-stacks", "--stack-name", stack_name)["Stacks"][0]
    tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
    resources = aws(region, "cloudformation", "list-stack-resources",
                    "--stack-name", stack["StackId"])["StackResourceSummaries"]
    by_id = {resource["LogicalResourceId"]: resource for resource in resources}
    resource_types = {name: resource.get("ResourceType") for name, resource in by_id.items()}
    network_parameters = [p for p in stack.get("Parameters", [])
                          if p.get("ParameterKey") in ("ExistingVpcId", "ExistingSubnetId")]
    if network_parameters:
        parameters = {p["ParameterKey"]: p.get("ParameterValue", "") for p in network_parameters}
        valid_parameters = len(network_parameters) == 2 and all(
            isinstance(parameters.get(name), str)
            and re.fullmatch(rf"{prefix}-[0-9a-f]{{8}}(?:[0-9a-f]{{9}})?", parameters[name])
            for name, prefix in (("ExistingVpcId", "vpc"), ("ExistingSubnetId", "subnet")))
        # An exact inventory excludes owned networks, nested stacks and custom resources.
        matches_template = (valid_parameters and resource_types == EXISTING_NETWORK_RESOURCE_TYPES
                            and not any(r.get("PhysicalResourceId") in parameters.values()
                                        for r in resources))
    else:
        required_types = {"WorkshopVpc": "AWS::EC2::VPC", "WorkshopInstance": "AWS::EC2::Instance",
                          "ResultsBucket": "AWS::S3::Bucket"}
        matches_template = all(resource_types.get(name) == kind for name, kind in required_types.items())
    if (tags.get("Workshop") != "physical-ai-isaac-aws" or not matches_template
            or len(by_id) != len(resources)):
        raise SystemExit("deploy.sh로 생성한 이 워크숍 스택인지 확인하지 못했습니다. 삭제하지 않습니다.")
    if stack["StackStatus"].endswith("_IN_PROGRESS"):
        raise SystemExit("스택 작업이 진행 중입니다. 완료 후 재시도하세요.")
    instance = by_id["WorkshopInstance"]
    bucket = by_id["ResultsBucket"]
    # Deleted resources are skipped to allow retrying DELETE_FAILED safely.
    instance_id = instance.get("PhysicalResourceId")
    if instance_id and instance.get("ResourceStatus") != "DELETE_COMPLETE":
        reservations = aws(region, "ec2", "describe-instances", "--filters",
                           f"Name=instance-id,Values={instance_id}")["Reservations"]
        instances = [i for r in reservations for i in r["Instances"]]
        state = instances[0]["State"]["Name"] if instances else "terminated"
        if state in ("pending", "running"):
            if state == "pending":
                aws(region, "ec2", "wait", "instance-running", "--instance-ids", instance_id,
                    json_output=False)
            aws(region, "ec2", "stop-instances", "--instance-ids", instance_id)
            state = "stopping"
        if state == "stopping":
            aws(region, "ec2", "wait", "instance-stopped", "--instance-ids", instance_id,
                json_output=False)
    bucket_name = bucket.get("PhysicalResourceId")
    if bucket_name and bucket.get("ResourceStatus") != "DELETE_COMPLETE":
        versioning = aws(region, "s3api", "get-bucket-versioning", "--bucket", bucket_name)
        if versioning.get("Status") in ("Enabled", "Suspended"):
            raise SystemExit("버킷 버전 관리가 변경되었습니다. 모든 버전/삭제 마커를 수동 정리한 뒤 "
                             "CloudFormation 콘솔에서 스택을 삭제하세요.")
        if versioning:
            raise SystemExit("버킷 버전 관리 응답을 확인하지 못했습니다. 버킷과 스택을 삭제하지 않습니다.")
        uploads = aws(region, "s3api", "list-multipart-uploads", "--bucket", bucket_name)
        for upload in uploads.get("Uploads", []):
            aws(region, "s3api", "abort-multipart-upload", "--bucket", bucket_name,
                "--key", upload["Key"], "--upload-id", upload["UploadId"])
        aws(region, "s3", "rm", f"s3://{bucket_name}", "--recursive", json_output=False)
    print(f"스택 삭제 시작: {stack['StackId']}", flush=True)
    aws(region, "cloudformation", "delete-stack", "--stack-name", stack["StackId"])
    aws(region, "cloudformation", "wait", "stack-delete-complete",
        "--stack-name", stack["StackId"], json_output=False)
    print("스택 삭제 완료. 별도로 만든 스냅샷/복사본/키페어는 AWS 콘솔에서 확인하세요.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: cleanup-resources.py REGION STACK_NAME (cleanup.sh를 사용하세요)")
    try:
        main(*sys.argv[1:])
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"AWS 정리 작업 실패:\n{error.stderr}\n"
                         "CloudFormation 이벤트를 확인하세요. EC2 정지만으로 EBS/S3 비용이 끝나지 않습니다.")
