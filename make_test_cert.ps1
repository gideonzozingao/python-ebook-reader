# Creates a SELF-SIGNED code-signing certificate to test the signing pipeline.
# Self-signed means only PCs that choose to trust it will accept it; it does NOT remove
# SmartScreen warnings for other people. Use it for testing or for a closed group (see BUILD.md).
#
#   powershell -ExecutionPolicy Bypass -File .\make_test_cert.ps1            (test only)
#   powershell -ExecutionPolicy Bypass -File .\make_test_cert.ps1 -Trust     (also trust it on THIS PC)
param(
    [string]$Subject = "CN=Book Reader (test signing)",
    [string]$PfxPath = "$PSScriptRoot\test-signing.pfx",
    [switch]$Trust
)
$cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $Subject `
    -CertStoreLocation Cert:\CurrentUser\My -KeyExportPolicy Exportable -KeyUsage DigitalSignature `
    -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(2)
$password = Read-Host "Choose a password for the .pfx file" -AsSecureString
Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $password | Out-Null
if ($Trust) {   # Windows asks you to confirm adding a root certificate
    $cer = "$env:TEMP\book-reader-test.cer"
    Export-Certificate -Cert $cert -FilePath $cer | Out-Null
    Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\TrustedPublisher | Out-Null
    Import-Certificate -FilePath $cer -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
}
Write-Host ""
Write-Host "Created: $PfxPath"
Write-Host "Thumbprint: $($cert.Thumbprint)"
Write-Host "In sign_config.bat use:  set SIGN_METHOD=thumbprint  and  set SIGN_THUMBPRINT=$($cert.Thumbprint)"
Write-Host "   or:  set SIGN_METHOD=pfx, SIGN_PFX=$PfxPath, SIGN_PASSWORD=<your password>"
