@echo off
rem ===========================================================================
rem  Copy this file to  bin\sign_config.bat  (it is git-ignored) and enable ONE method.
rem  NEVER commit passwords, .pfx files or tokens PINs.
rem ===========================================================================

rem ---- A) Certificate on a USB token, HSM or cloud signer that Windows can see -------------
rem      (DigiCert KeyLocker, SSL.com eSigner, Certum SimplySign, Sectigo ... after their setup)
rem set SIGN_METHOD=thumbprint
rem set SIGN_THUMBPRINT=0123456789ABCDEF0123456789ABCDEF01234567
rem   or pick the certificate by its subject name:
rem set SIGN_METHOD=subject
rem set SIGN_SUBJECT=Your Company Name

rem ---- B) A .pfx file: self-signed or internal-CA certificates (see bin\make_test_cert.ps1) -----
rem      Public CAs no longer issue exportable .pfx files (key must stay in hardware).
rem set SIGN_METHOD=pfx
rem set SIGN_PFX=C:\keys\test-signing.pfx
rem set SIGN_PASSWORD=...   (better: set it in your shell, not in this file)

rem ---- C) Azure Artifact Signing (formerly Trusted Signing) ------------------------------------
rem set SIGN_METHOD=azure
rem set SIGN_AZURE_DLIB=C:\tools\ArtifactSigning\bin\x64\Azure.CodeSigning.Dlib.dll
rem set SIGN_AZURE_JSON=C:\tools\ArtifactSigning\metadata.json

rem ---- D) Any other signing command (e.g. SSL.com CodeSignTool). It receives the file path. ----
rem set SIGN_METHOD=custom
rem set SIGN_COMMAND=C:\tools\mysigner.bat

rem Optional: another timestamp server (the timestamp keeps signatures valid after the
rem certificate expires, so never turn it off).
rem set SIGN_TIMESTAMP=http://timestamp.sectigo.com
rem Optional: full path of signtool.exe if it is not in the Windows SDK folder.
rem set SIGNTOOL=C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe
