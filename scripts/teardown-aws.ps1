param(
    [string]$StatePath = $(Join-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)) "deploy-state.json")
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $StatePath)) {
    throw "State file not found: $StatePath"
}
if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
    $awsPath = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (Test-Path $awsPath) {
        Set-Alias -Name aws -Value $awsPath -Scope Script
    } else {
        throw "AWS CLI is not available on PATH."
    }
}

$state = Get-Content -Raw -LiteralPath $StatePath | ConvertFrom-Json
$region = $state.region

if ($state.instanceId) {
    Write-Host "Terminating instance $($state.instanceId)"
    aws ec2 terminate-instances --region $region --instance-ids $state.instanceId | Out-Null
    aws ec2 wait instance-terminated --region $region --instance-ids $state.instanceId
}

if ($state.securityGroupId) {
    try { aws ec2 delete-security-group --region $region --group-id $state.securityGroupId | Out-Null } catch { Write-Warning $_ }
}

if ($state.keyName) {
    try { aws ec2 delete-key-pair --region $region --key-name $state.keyName | Out-Null } catch { Write-Warning $_ }
}
if ($state.keyPath -and (Test-Path $state.keyPath)) {
    Remove-Item -LiteralPath $state.keyPath -Force
}

if ($state.profileName -and $state.roleName) {
    try { aws iam remove-role-from-instance-profile --instance-profile-name $state.profileName --role-name $state.roleName | Out-Null } catch { Write-Warning $_ }
    try { aws iam delete-instance-profile --instance-profile-name $state.profileName | Out-Null } catch { Write-Warning $_ }
}
if ($state.roleName -and $state.policyName) {
    try { aws iam delete-role-policy --role-name $state.roleName --policy-name $state.policyName | Out-Null } catch { Write-Warning $_ }
}
if ($state.roleName) {
    try { aws iam delete-role --role-name $state.roleName | Out-Null } catch { Write-Warning $_ }
}

if ($state.analyzerName) {
    $arn = aws accessanalyzer list-analyzers --region $region --type ACCOUNT --query "analyzers[?name=='$($state.analyzerName)'].arn | [0]" --output text
    if ($arn -and $arn -ne "None") {
        try { aws accessanalyzer delete-analyzer --region $region --analyzer-name $state.analyzerName | Out-Null } catch { Write-Warning $_ }
    }
}

Remove-Item -LiteralPath $StatePath -Force
Write-Host "Teardown complete."
