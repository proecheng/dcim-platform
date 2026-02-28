# 终止占用 8080 端口的进程
$processes = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

if ($processes) {
    foreach ($pid in $processes) {
        Write-Host "Killing process $pid..."
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Done."
} else {
    Write-Host "No process found on port 8080."
}
