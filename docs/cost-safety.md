# Cost Safety Notes

This project is constrained for AWS Free Tier demos, but no cloud setup can guarantee zero billing once resources are created. The scripts minimize chargeable surface area and make teardown explicit.

## Allowed

- CloudTrail `lookup_events` Event History reads.
- IAM credential report and IAM read APIs.
- One external/account Access Analyzer.
- One short-lived EC2 instance with an 8 GB delete-on-termination root volume.
- AWS Budget notification with email subscribers.

## Blocked By Design

- S3 log buckets or report buckets.
- CloudTrail trails, CloudTrail Lake, or data events.
- Load balancers, NAT Gateways, Elastic IPs, and managed databases.
- Access Analyzer unused access, internal access, and custom policy checks.
- Stored AWS access keys in the application.

## Required Before Deploy

```powershell
$env:BILLING_ALERT_EMAIL="you@example.com"
.\scripts\aws-preflight.ps1
```

Confirm the AWS Budget email subscription, deploy, then run teardown after the demo:

```powershell
.\scripts\deploy-ec2.ps1
.\scripts\teardown-aws.ps1
```

