# VORNEQ development backend -> OpenAI E2E smoke.
# Default: offline mock, no key/no network. -Live: one owner-approved billable call.
# No GitHub/Render changes, no real database connection and no key files.
param([switch]$Live)
$ErrorActionPreference = 'Stop'
$root = 'C:\Users\hamid\Downloads\VORNEQ-AI-Dev-Integration-20261112'
$python = 'C:\Users\hamid\Downloads\VORNEQ-AI-PhaseC-20261112\.venv\Scripts\python.exe'
# Local gettext compilation is performed via the Babel Python API.
$original = @{}
$variables = @('VORNEQ_ENV','VORNEQ_AI_PHASE_B_ENABLED','VORNEQ_AI_PHASE_C_ENABLED',
               'VORNEQ_AI_PHASE_B_MODEL','VORNEQ_AI_LIVE_E2E_ACK','OPENAI_API_KEY',
               'DJANGO_SECRET_KEY','DJANGO_DEBUG','DJANGO_ALLOWED_HOSTS',
               'DJANGO_CSRF_TRUSTED_ORIGINS')
foreach ($name in $variables) {
    $original[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$keyPtr = [IntPtr]::Zero
$secret = $null
try {
    if (-not (Test-Path -LiteralPath $python)) { throw 'Isolated Python SDK is missing.' }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'manage.py'))) { throw 'Worktree missing.' }
    if ($env:DATABASE_URL -or $env:REDIS_URL -or $env:VORNEQ_DATABASE_URL) {
        throw 'External data connection detected; refusing to run.'
    }
    Set-Location -LiteralPath $root
    $env:VORNEQ_ENV = 'development'
    $env:VORNEQ_AI_PHASE_B_ENABLED = 'true'
    $env:VORNEQ_AI_PHASE_C_ENABLED = 'true'
    $env:VORNEQ_AI_PHASE_B_MODEL = 'gpt-6-luna'
    $env:DJANGO_SECRET_KEY = 'synthetic-development-secret-only-not-for-production'
    $env:DJANGO_DEBUG = '1'
    $env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1,testserver'
    $env:DJANGO_CSRF_TRUSTED_ORIGINS = 'http://localhost,http://127.0.0.1'
    $db = (& $python manage.py shell -c 'from django.db import connection; print(connection.vendor)' | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0 -or $db.Trim() -ne 'sqlite') {
        throw 'Not an isolated local SQLite development database.'
    }
    Write-Output 'DATABASE=LOCAL_SQLITE_TEST_DATABASE'
    & $python scripts/ai_dev_compile_catalogs.py
    if ($LASTEXITCODE -ne 0) { throw 'Local translation compilation failed.' }
    & $python manage.py collectstatic --noinput *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Local collectstatic failed.' }
    & $python manage.py check
    if ($LASTEXITCODE -ne 0) { throw 'Django system check failed.' }
    if (-not $Live) {
        Write-Output 'MODE=OFFLINE_BACKEND_E2E'
        Write-Output 'LIVE_PROVIDER_CALLS=0'
        Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
        & $python manage.py test apps.ai_core.tests.test_ai_backend_e2e_mock --verbosity 1
        $code = $LASTEXITCODE
        Write-Output ('OFFLINE_BACKEND_EXIT=' + $code)
        exit $code
    }
    Write-Output 'MODE=LIVE_BACKEND_E2E_DEVELOPMENT'
    Write-Output 'This will make ONE paid OpenAI Responses API request through the real Django endpoint.'
    Write-Output 'Only synthetic public text is sent. No private VORNEQ records, no production databases.'
    Write-Output 'The provider may charge API usage even if output validation fails.'
    Write-Output 'Ensure your OpenAI project has suitable billing limits before proceeding.'
    $limitConfirmation = Read-Host 'Confirm Enforce a hard limit is enabled in the OpenAI project (type LIMIT_CONFIRMED)'
    if ($limitConfirmation.Trim() -cne 'LIMIT_CONFIRMED') {
        Write-Output 'CANCELLED: project billing hard limit was not confirmed.'
        exit 0
    }
    $approval = Read-Host 'To authorize one billable live backend request, type YES'
    if ($approval.Trim() -ine 'YES') {
        Write-Output 'CANCELLED: no API request made.'
        exit 0
    }
    $secret = Read-Host 'Enter VORNEQ Development OpenAI API key (hidden, never written to disk)' -AsSecureString
    $keyPtr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPtr)
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        throw 'Empty API key; no request made.'
    }
    $env:VORNEQ_AI_LIVE_E2E_ACK = 'I_AUTHORIZE_ONE_REAL_OPENAI_CALL'
    & $python manage.py test apps.ai_core.tests.manual_ai_backend_live --verbosity 1
    $code = $LASTEXITCODE
    Write-Output ('LIVE_BACKEND_TEST_EXIT=' + $code)
    exit $code
}
finally {
    if ($keyPtr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPtr)
    }
    $secret = $null
    foreach ($name in $variables) {
        $value = $original[$name]
        if ($null -eq $value) {
            [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        } else {
            [Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}
