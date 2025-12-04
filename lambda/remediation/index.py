import json
import logging
from typing import Dict, List

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

iam = boto3.client("iam")
ec2 = boto3.client("ec2")

def handler(event, context):
    """Attempt automated remediation actions based on the Step Functions payload."""
    logger.info("Starting remediation with payload: %s", json.dumps(event))

    actions: List[Dict[str, str]] = []
    errors: List[str] = []

    affected_user = event.get("affected_user")
    if affected_user:
        try:
            disabled = disable_access_keys(affected_user, event.get("access_key_id"))
            actions.append({"action": "DISABLE_ACCESS_KEYS", "details": disabled})
        except ClientError as exc:  # pragma: no cover - requires AWS
            logger.error("Failed to disable keys for %s: %s", affected_user, exc, exc_info=True)
            errors.append(f"iam:{exc.response['Error']['Code']}")

        mfa_device = event.get("mfa_serial")
        if mfa_device:
            try:
                iam.deactivate_mfa_device(UserName=affected_user, SerialNumber=mfa_device)
                actions.append({"action": "DEACTIVATE_MFA", "details": mfa_device})
            except ClientError as exc:  # pragma: no cover - requires AWS
                logger.error("Failed to deactivate MFA for %s: %s", affected_user, exc, exc_info=True)
                errors.append(f"iam:{exc.response['Error']['Code']}")

    sg_id = event.get("security_group_id")
    malicious_ip = event.get("malicious_ip")
    if sg_id and malicious_ip:
        try:
            revoke_ingress(sg_id, malicious_ip)
            actions.append({"action": "REVOKE_SG", "details": f"{sg_id}:{malicious_ip}"})
        except ClientError as exc:  # pragma: no cover - requires AWS
            logger.error("Failed to revoke ingress on %s: %s", sg_id, exc, exc_info=True)
            errors.append(f"ec2:{exc.response['Error']['Code']}")

    response = {
        "remediation_performed": bool(actions),
        "actions": actions,
        "errors": errors,
    }
    logger.info("Remediation result: %s", json.dumps(response))
    return {**event, "remediation": response}


def disable_access_keys(user_name: str, key_id: str | None) -> str:
    """Deactivate either a specific key or every active key for the user."""
    if key_id:
        iam.update_access_key(UserName=user_name, AccessKeyId=key_id, Status="Inactive")
        return key_id

    deactivated: List[str] = []
    paginator = iam.get_paginator("list_access_keys")
    for page in paginator.paginate(UserName=user_name):
        for metadata in page.get("AccessKeyMetadata", []):
            if metadata.get("Status") == "Active":
                iam.update_access_key(
                    UserName=user_name,
                    AccessKeyId=metadata["AccessKeyId"],
                    Status="Inactive",
                )
                deactivated.append(metadata["AccessKeyId"])

    return ",".join(deactivated)


def revoke_ingress(security_group_id: str, ip: str) -> None:
    """Remove ingress for the provided IP across all protocols."""
    ec2.revoke_security_group_ingress(
        GroupId=security_group_id,
        IpPermissions=[
            {
                "IpProtocol": "-1",
                "IpRanges": [{"CidrIp": f"{ip}/32", "Description": "AI-SOC remediation"}],
            }
        ],
    )
