# =======================================
# File: scripts/check_common_ports.ps1
# =======================================
# Description: Checks if common TCP ports are open on the local machine using Test-NetConnection.
# Output: Table showing port status.
# Requires Elevation: No (but Test-NetConnection might behave differently depending on firewall rules)

param(
    # Target machine to scan. Defaults to localhost.
    [string]$Target = "localhost"
)

# Ensure errors don't halt the script entirely when run via the tool
$ErrorActionPreference = 'Continue'

Write-Output "--- Checking Common Ports on $Target ---"

# List of common ports and their typical services
$CommonPorts = @{
    "FTP"     = 21
    "SSH"     = 22
    "Telnet"  = 23
    "SMTP"    = 25
    "DNS"     = 53
    "HTTP"    = 80
    "POP3"    = 110
    "IMAP"    = 143
    "HTTPS"   = 443
    "SMB"     = 445
    "SMTPS"   = 465 # Added SMTPS
    "IMAPS"   = 993 # Added IMAPS
    "POP3S"   = 995 # Added POP3S
    "MSSQL"   = 1433 # Added MS SQL Server
    "MySQL"   = 3306 # Added MySQL
    "RDP"     = 3389
    "PostgreSQL" = 5432 # Added PostgreSQL
    "VNC"     = 5900 # Added VNC
    "HTTP-Alt"= 8080 # Added HTTP Alt
}

$Results = @() # Initialize an array to store results

# Iterate through the defined ports
foreach ($Name, $Port in $CommonPorts.GetEnumerator()) {
    Write-Output "Testing Port $Port ($Name)..."

    # Use Test-NetConnection. -InformationLevel Quiet returns $true/$false.
    # Timeout set to 1 second. ErrorAction SilentlyContinue suppresses connection errors.
    # WarningAction SilentlyContinue suppresses other warnings (like name resolution issues if $Target is not localhost).
    $ConnectionTest = Test-NetConnection -ComputerName $Target -Port $Port -InformationLevel Quiet -TimeoutSeconds 1 -ErrorAction SilentlyContinue -WarningAction SilentlyContinue

    # Create a custom object for each result
    $ResultObject = [PSCustomObject]@{
        PortName = $Name
        Port     = $Port
        IsOpen   = $ConnectionTest # Will be $true or $false
        Status   = if ($ConnectionTest) { "Open" } else { "Closed/Filtered" }
    }
    $Results += $ResultObject # Add the result to the array
}

Write-Output "`n--- Port Scan Results for $Target ---"
# Display the results in a formatted table
if ($Results.Count -gt 0) {
    $Results | Format-Table -AutoSize | Out-String
} else {
    Write-Output "No ports were tested or no results generated."
}

Write-Output "`n--- End of Port Check ---"

# Explicitly exit with 0 if successful completion
exit 0
