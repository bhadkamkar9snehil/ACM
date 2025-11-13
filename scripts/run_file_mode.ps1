# Run ACM in file mode for a given equipment
param(
    [string]$Equip = "FD_FAN",
    [string]$Config = "configs/config_table.csv",
    [string]$Artifacts = "artifacts",
    [switch]$EnableReport
)

$EquipArg = $Equip
$ArtifactsArg = (Resolve-Path $Artifacts).Path
$ConfigArg = (Resolve-Path $Config).Path

$reportFlag = ""
if ($EnableReport) { $reportFlag = "--enable-report" }

python -m core.acm_main --equip $EquipArg --artifact-root $ArtifactsArg --config $ConfigArg --mode batch $reportFlag
