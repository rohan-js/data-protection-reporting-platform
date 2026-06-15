param(
    [string]$Region = "ap-south-1",
    [string]$BudgetName = "dprp-free-tier-guardrail",
    [decimal]$BudgetLimitUsd = 1.00
)

$ErrorActionPreference = "Stop"

function Require-AwsCli {
    if (Get-Command aws -ErrorAction SilentlyContinue) {
        return
    }
    $awsPath = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (Test-Path $awsPath) {
        Set-Alias -Name aws -Value $awsPath -Scope Script
        return
    }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "AWS CLI is not installed and winget is unavailable. Install AWS CLI v2, then rerun this script."
    }
    Write-Host "Installing AWS CLI v2 through winget..."
    winget install --id Amazon.AWSCLI --source winget --accept-package-agreements --accept-source-agreements
    if (Test-Path $awsPath) {
        Set-Alias -Name aws -Value $awsPath -Scope Script
        return
    }
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        throw "AWS CLI installation finished but aws is not on PATH. Open a new PowerShell terminal and rerun this script."
    }
}

function Require-Env($Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Set `$env:$Name before running this script."
    }
    return $value
}

Require-AwsCli
$email = Require-Env "BILLING_ALERT_EMAIL"

aws configure set default.region $Region
$identity = aws sts get-caller-identity | ConvertFrom-Json
$accountId = $identity.Account
Write-Host "Using AWS account $accountId in region $Region"

$budget = @{
    BudgetName = $BudgetName
    BudgetLimit = @{ Amount = "$BudgetLimitUsd"; Unit = "USD" }
    TimeUnit = "MONTHLY"
    BudgetType = "COST"
    CostTypes = @{
        IncludeTax = $true
        IncludeSubscription = $true
        UseBlended = $false
        IncludeRefund = $false
        IncludeCredit = $false
        IncludeUpfront = $true
        IncludeRecurring = $true
        IncludeOtherSubscription = $true
        IncludeSupport = $true
        IncludeDiscount = $true
        UseAmortized = $false
    }
}

$notifications = @(
    @{
        Notification = @{
            NotificationType = "ACTUAL"
            ComparisonOperator = "GREATER_THAN"
            Threshold = 0.01
            ThresholdType = "ABSOLUTE_VALUE"
        }
        Subscribers = @(@{ SubscriptionType = "EMAIL"; Address = $email })
    },
    @{
        Notification = @{
            NotificationType = "FORECASTED"
            ComparisonOperator = "GREATER_THAN"
            Threshold = 0.50
            ThresholdType = "ABSOLUTE_VALUE"
        }
        Subscribers = @(@{ SubscriptionType = "EMAIL"; Address = $email })
    }
)

$tmp = New-TemporaryFile
$tmpNotifications = New-TemporaryFile
try {
    $budget | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmp -Encoding utf8
    $notifications | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tmpNotifications -Encoding utf8
    aws budgets describe-budget --account-id $accountId --budget-name $BudgetName --region us-east-1 2>$null | Out-Null
    $exists = $LASTEXITCODE -eq 0
    if ($exists) {
        Write-Host "Budget $BudgetName already exists."
    } else {
        aws budgets create-budget --account-id $accountId --budget file://$tmp --notifications-with-subscribers file://$tmpNotifications --region us-east-1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "AWS failed to create budget $BudgetName."
        }
        Write-Host "Created budget $BudgetName. Confirm the subscription email from AWS."
    }
} finally {
    Remove-Item -LiteralPath $tmp,$tmpNotifications -Force -ErrorAction SilentlyContinue
}

$forbiddenChecks = @{
    "Elastic IPs" = { aws ec2 describe-addresses --region $Region --query "Addresses[].AllocationId" --output text }
    "Load balancers" = { aws elbv2 describe-load-balancers --region $Region --query "LoadBalancers[].LoadBalancerArn" --output text 2>$null }
    "NAT gateways" = { aws ec2 describe-nat-gateways --region $Region --query "NatGateways[?State!='deleted'].NatGatewayId" --output text }
    "CloudTrail trails" = { aws cloudtrail describe-trails --region $Region --query "trailList[].Name" --output text }
}

foreach ($name in $forbiddenChecks.Keys) {
    $value = & $forbiddenChecks[$name]
    if (-not [string]::IsNullOrWhiteSpace($value)) {
        Write-Warning "$name already exist in $Region. This project will not create or manage them: $value"
    }
}

Write-Host "Preflight complete. No project resources were provisioned."
