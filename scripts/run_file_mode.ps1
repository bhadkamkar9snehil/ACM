# Run ACM in file mode for a given equipment
param(
    [string]$Equip = "FD_FAN",
    [string]$Config = "configs/config_table.csv",
    [switch]$EnableReport
)

$EquipArg = $Equip
$ConfigArg = (Resolve-Path $Config).Path

$reportFlag = ""
if ($EnableReport) { $reportFlag = "--enable-report" }

python -m core.acm_main --equip $EquipArg --config $ConfigArg $reportFlag
