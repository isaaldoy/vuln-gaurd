# ==================================
# File: scripts/get_network_info.ps1
# ==================================
# Description: Retrieves basic network configuration and adapter information.
# Output: Formatted text output.
# Requires Elevation: No (but the tool runs it elevated anyway on Windows)

# Ensure errors don't halt the script entirely when run via the tool
$ErrorActionPreference = 'Continue'

Write-Output "--- Network Configuration (Get-NetIPConfiguration) ---"
try {
    # Select specific properties for clarity
    Get-NetIPConfiguration | Format-List -Property InterfaceAlias, InterfaceDescription, IPv4Address, IPv4DefaultGateway, DNSServer | Out-String
} catch {
    Write-Warning "Failed to get network configuration: $($_.Exception.Message)"
}


Write-Output "`n--- Active Network Adapters (Get-NetAdapter) ---"
try {
    # Filter for Up status and select relevant properties
    Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Format-Table -AutoSize -Property Name, InterfaceDescription, Status, MacAddress, LinkSpeed | Out-String
} catch {
    Write-Warning "Failed to get network adapters: $($_.Exception.Message)"
}

# Example: Adding ipconfig /all output
Write-Output "`n--- IPConfig /all ---"
try {
    ipconfig /all | Out-String
} catch {
    Write-Warning "Failed to run ipconfig /all: $($_.Exception.Message)"
}


Write-Output "`n--- End of Network Info ---"

# Explicitly exit with 0 if successful completion
exit 0

