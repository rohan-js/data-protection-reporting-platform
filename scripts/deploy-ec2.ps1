param(
    [string]$Region = "ap-south-1",
    [string]$InstanceType = "t3.micro",
    [int]$AutoTerminateHours = 4,
    [string]$ProjectName = "dprp"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$StatePath = Join-Path $Root "deploy-state.json"
$KeyName = "$ProjectName-key"
$RoleName = "$ProjectName-ec2-role"
$ProfileName = "$ProjectName-instance-profile"
$PolicyName = "$ProjectName-read-policy"
$SgName = "$ProjectName-sg"
$AnalyzerName = "$ProjectName-external-analyzer"

if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    $awsPath = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (Test-Path $awsPath) {
        Set-Alias -Name aws -Value $awsPath -Scope Script
    } else {
        throw "AWS CLI is not available. Run scripts\aws-preflight.ps1 first."
    }
}
if (-not (Get-Command ssh -ErrorAction SilentlyContinue) -or -not (Get-Command scp -ErrorAction SilentlyContinue)) {
    throw "OpenSSH ssh/scp are required on PATH."
}

$identity = aws sts get-caller-identity | ConvertFrom-Json
$accountId = $identity.Account
$callerIp = (Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()
try {
    $callerIpv6 = (Invoke-RestMethod -Uri "https://api64.ipify.org").Trim()
    if ($callerIpv6 -notmatch ":") { $callerIpv6 = $null }
} catch {
    $callerIpv6 = $null
}
Write-Host "Deploying to account $accountId. IPv4 SSH/HTTP fallback will be restricted to $callerIp/32."

function AwsJson($Command) {
    Invoke-Expression $Command | ConvertFrom-Json
}

$vpc = AwsJson "aws ec2 describe-vpcs --region $Region --filters Name=isDefault,Values=true --query 'Vpcs[0]' --output json"
if (-not $vpc.VpcId) { throw "No default VPC found in $Region." }
$subnet = AwsJson "aws ec2 describe-subnets --region $Region --filters Name=vpc-id,Values=$($vpc.VpcId) Name=default-for-az,Values=true --query 'Subnets[0]' --output json"
if (-not $subnet.SubnetId) { throw "No default subnet found in $Region." }
$allSubnets = AwsJson "aws ec2 describe-subnets --region $Region --filters Name=vpc-id,Values=$($vpc.VpcId) --output json"
$ipv6Subnet = $allSubnets.Subnets | Where-Object {
    $_.Ipv6CidrBlockAssociationSet | Where-Object { $_.Ipv6CidrBlockState.State -eq "associated" }
} | Select-Object -First 1
$useIpv6 = $null -ne $callerIpv6 -and $null -ne $ipv6Subnet
if ($useIpv6) {
    $subnet = $ipv6Subnet
    Write-Host "IPv6 path available. Launching without public IPv4 in subnet $($subnet.SubnetId)."
} else {
    Write-Warning "IPv6 path unavailable. Falling back to temporary public IPv4; teardown promptly to avoid public IPv4 charges."
}

$sg = aws ec2 describe-security-groups --region $Region --filters Name=group-name,Values=$SgName Name=vpc-id,Values=$($vpc.VpcId) --query "SecurityGroups[0].GroupId" --output text
if ($sg -eq "None" -or [string]::IsNullOrWhiteSpace($sg)) {
    $sg = aws ec2 create-security-group --region $Region --group-name $SgName --description "DPRP demo access" --vpc-id $vpc.VpcId --query GroupId --output text
    aws ec2 create-tags --region $Region --resources $sg --tags Key=Project,Value=$ProjectName | Out-Null
}
try {
    aws ec2 authorize-security-group-ingress --region $Region --group-id $sg --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,IpRanges=[{CidrIp=$callerIp/32,Description='SSH from deploy host'}]" | Out-Null
} catch {}
try {
    aws ec2 authorize-security-group-ingress --region $Region --group-id $sg --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,IpRanges=[{CidrIp=$callerIp/32,Description='HTTP from deploy host'}]" | Out-Null
} catch {}
if ($useIpv6) {
    try {
        aws ec2 authorize-security-group-ingress --region $Region --group-id $sg --ip-permissions "IpProtocol=tcp,FromPort=22,ToPort=22,Ipv6Ranges=[{CidrIpv6=$callerIpv6/128,Description='SSH from deploy host IPv6'}]" | Out-Null
    } catch {}
    try {
        aws ec2 authorize-security-group-ingress --region $Region --group-id $sg --ip-permissions "IpProtocol=tcp,FromPort=80,ToPort=80,Ipv6Ranges=[{CidrIpv6=$callerIpv6/128,Description='HTTP from deploy host IPv6'}]" | Out-Null
    } catch {}
}

$trust = @{
    Version = "2012-10-17"
    Statement = @(@{
        Effect = "Allow"
        Principal = @{ Service = "ec2.amazonaws.com" }
        Action = "sts:AssumeRole"
    })
} | ConvertTo-Json -Depth 10
$trustFile = New-TemporaryFile
$policyFile = New-TemporaryFile
try {
    $trust | Set-Content -LiteralPath $trustFile -Encoding utf8
    try { aws iam create-role --role-name $RoleName --assume-role-policy-document file://$trustFile | Out-Null } catch {}

    $policy = @{
        Version = "2012-10-17"
        Statement = @(
            @{
                Effect = "Allow"
                Action = @("cloudtrail:LookupEvents")
                Resource = "*"
            },
            @{
                Effect = "Allow"
                Action = @(
                    "iam:GenerateCredentialReport",
                    "iam:GetCredentialReport",
                    "iam:GetAccountSummary",
                    "iam:ListUsers",
                    "iam:ListRoles",
                    "iam:ListMFADevices"
                )
                Resource = "*"
            },
            @{
                Effect = "Allow"
                Action = @("access-analyzer:ListAnalyzers", "access-analyzer:ListFindings", "access-analyzer:GetFinding")
                Resource = "*"
            }
        )
    } | ConvertTo-Json -Depth 10
    $policy | Set-Content -LiteralPath $policyFile -Encoding utf8
    aws iam put-role-policy --role-name $RoleName --policy-name $PolicyName --policy-document file://$policyFile | Out-Null
    try { aws iam create-instance-profile --instance-profile-name $ProfileName | Out-Null } catch {}
    try { aws iam add-role-to-instance-profile --instance-profile-name $ProfileName --role-name $RoleName | Out-Null } catch {}
} finally {
    Remove-Item -LiteralPath $trustFile,$policyFile -Force -ErrorAction SilentlyContinue
}

try {
    aws accessanalyzer create-analyzer --region $Region --analyzer-name $AnalyzerName --type ACCOUNT | Out-Null
    Write-Host "Created external Access Analyzer $AnalyzerName"
} catch {
    Write-Host "Access Analyzer $AnalyzerName already exists or cannot be created by current caller."
}

$keyPath = Join-Path $Root "$KeyName.pem"
if (-not (Test-Path $keyPath)) {
    aws ec2 create-key-pair --region $Region --key-name $KeyName --query KeyMaterial --output text | Set-Content -LiteralPath $keyPath -Encoding ascii
    icacls $keyPath /inheritance:r | Out-Null
    icacls $keyPath /remove:g "Authenticated Users" "BUILTIN\Users" "Everyone" | Out-Null
    icacls $keyPath /grant:r "$env:USERNAME`:(R)" | Out-Null
}

$ami = aws ssm get-parameter --region $Region --name "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64" --query "Parameter.Value" --output text
$userData = @"
#!/bin/bash
set -euxo pipefail
dnf update -y
dnf install -y nginx nodejs npm unzip
dnf install -y python3.12 python3.12-pip || dnf install -y python3.11 python3.11-pip
mkdir -p /opt/dprp
chown ec2-user:ec2-user /opt/dprp
systemctl enable nginx
shutdown -h +$($AutoTerminateHours * 60) "DPRP demo auto-stop"
"@
$userDataFile = New-TemporaryFile
$userData | Set-Content -LiteralPath $userDataFile -Encoding ascii

if ($useIpv6) {
    $networkInterface = "DeviceIndex=0,SubnetId=$($subnet.SubnetId),Groups=[$sg],Ipv6AddressCount=1,AssociatePublicIpAddress=false"
    $instanceId = aws ec2 run-instances `
        --region $Region `
        --image-id $ami `
        --instance-type $InstanceType `
        --key-name $KeyName `
        --iam-instance-profile Name=$ProfileName `
        --network-interfaces $networkInterface `
        --instance-initiated-shutdown-behavior terminate `
        --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=8,VolumeType=gp3,DeleteOnTermination=true}" `
        --metadata-options "HttpTokens=required,HttpEndpoint=enabled" `
        --user-data file://$userDataFile `
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$ProjectName-demo},{Key=Project,Value=$ProjectName}]" `
        --query "Instances[0].InstanceId" `
        --output text
} else {
    $instanceId = aws ec2 run-instances `
        --region $Region `
        --image-id $ami `
        --instance-type $InstanceType `
        --key-name $KeyName `
        --iam-instance-profile Name=$ProfileName `
        --security-group-ids $sg `
        --subnet-id $subnet.SubnetId `
        --instance-initiated-shutdown-behavior terminate `
        --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=8,VolumeType=gp3,DeleteOnTermination=true}" `
        --metadata-options "HttpTokens=required,HttpEndpoint=enabled" `
        --user-data file://$userDataFile `
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$ProjectName-demo},{Key=Project,Value=$ProjectName}]" `
        --query "Instances[0].InstanceId" `
        --output text
}
Remove-Item -LiteralPath $userDataFile -Force

aws ec2 wait instance-running --region $Region --instance-ids $instanceId
$publicIp = aws ec2 describe-instances --region $Region --instance-ids $instanceId --query "Reservations[0].Instances[0].PublicIpAddress" --output text
$ipv6Address = aws ec2 describe-instances --region $Region --instance-ids $instanceId --query "Reservations[0].Instances[0].Ipv6Address" --output text
if ($useIpv6) {
    if ([string]::IsNullOrWhiteSpace($ipv6Address) -or $ipv6Address -eq "None") {
        throw "IPv6 launch was requested, but the instance has no IPv6 address."
    }
    $sshTarget = "ec2-user@[$ipv6Address]"
    $scpTarget = "ec2-user@[$ipv6Address]:/home/ec2-user/dprp-upload.zip"
    $dashboardUrl = "http://[$ipv6Address]"
} else {
    if ([string]::IsNullOrWhiteSpace($publicIp) -or $publicIp -eq "None") {
        throw "Instance launched without public IPv4 and IPv6 was unavailable."
    }
    $sshTarget = "ec2-user@$publicIp"
    $scpTarget = "ec2-user@${publicIp}:/home/ec2-user/dprp-upload.zip"
    $dashboardUrl = "http://$publicIp"
}

$archive = Join-Path $Root "dprp-upload.zip"
Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $Root "backend"),(Join-Path $Root "frontend"),(Join-Path $Root "README.md") -DestinationPath $archive -Force

Write-Host "Waiting for SSH at $sshTarget..."
Start-Sleep -Seconds 60
scp -o StrictHostKeyChecking=no -i $keyPath $archive $scpTarget
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upload application archive to $scpTarget."
}
$remoteScript = @"
set -euxo pipefail
sudo rm -rf /opt/dprp/*
sudo unzip -q /home/ec2-user/dprp-upload.zip -d /opt/dprp
sudo chown -R ec2-user:ec2-user /opt/dprp
cd /opt/dprp/frontend
npm install
npm run build
cd /opt/dprp
PYBIN=`$(command -v python3.12 || command -v python3.11)
`$PYBIN -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt
cat > /tmp/dprp.service <<'SERVICE'
[Unit]
Description=Data Protection Reporting Platform API
After=network.target

[Service]
WorkingDirectory=/opt/dprp
Environment=AWS_REGION=$Region
Environment=ACCESS_ANALYZER_NAME=$AnalyzerName
Environment=ENABLE_SCHEDULER=true
ExecStart=/opt/dprp/.venv/bin/python -m uvicorn app.main:app --app-dir /opt/dprp/backend --host 127.0.0.1 --port 8000
Restart=always
User=ec2-user

[Install]
WantedBy=multi-user.target
SERVICE
sudo mv /tmp/dprp.service /etc/systemd/system/dprp.service
cat > /tmp/dprp-nginx.conf <<'NGINX'
server {
    listen 80;
    server_name _;
    root /opt/dprp/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host `$host;
        proxy_set_header X-Real-IP `$remote_addr;
    }

    location / {
        try_files `$uri /index.html;
    }
}
NGINX
sudo mv /tmp/dprp-nginx.conf /etc/nginx/conf.d/dprp.conf
sudo rm -f /etc/nginx/conf.d/default.conf
sudo systemctl daemon-reload
sudo systemctl enable --now dprp
sudo systemctl restart nginx
"@
ssh -o StrictHostKeyChecking=no -i $keyPath $sshTarget $remoteScript
if ($LASTEXITCODE -ne 0) {
    throw "Remote installation failed on $sshTarget."
}

$state = @{
    region = $Region
    instanceId = $instanceId
    securityGroupId = $sg
    keyName = $KeyName
    keyPath = $keyPath
    roleName = $RoleName
    profileName = $ProfileName
    policyName = $PolicyName
    analyzerName = $AnalyzerName
    publicIp = $publicIp
    ipv6Address = $ipv6Address
} | ConvertTo-Json -Depth 5
$state | Set-Content -LiteralPath $StatePath -Encoding utf8
Write-Host "Dashboard: $dashboardUrl"
Write-Host "Auto-stop scheduled in $AutoTerminateHours hours. Run scripts\teardown-aws.ps1 to delete resources."
