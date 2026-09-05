#!/usr/bin/env python
"""
VORNEQ Baseline Health Check (Read-only)
- Runs Django system checks
- Detects missing migrations (without creating them)
- Performs HTTP smoke tests on critical routes
- Uses DummyCache and signed-cookie sessions to prevent any writes
- Outputs results to stdout/stderr only (no log files)
- Does NOT modify database, files, session, or cache
"""

import os
import sys
import django
from django.test import Client, override_settings
from django.core.management import call_command

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# ANSI colours for terminal output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

# Read-only overrides for cache and session
READ_ONLY_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

def print_header(text):
    print(f"\n{'='*60}")
    print(f" {text}")
    print(f"{'='*60}")

def print_success(text):
    print(f"{GREEN}✓{RESET} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{RESET} {text}")

def print_error(text):
    print(f"{RED}✗{RESET} {text}")

def check_migrations():
    """Check for missing migrations without writing anything."""
    print_header("Checking for missing migrations")
    try:
        # --check exits with non-zero if migrations are missing
        # --dry-run ensures no migration files are created
        call_command('makemigrations', '--check', '--dry-run', verbosity=1)
        print_success("No missing migrations detected.")
        return True
    except SystemExit as e:
        if e.code != 0:
            print_error("Missing migrations detected! Run 'python manage.py makemigrations' to generate them.")
            return False
        else:
            # Shouldn't happen, but just in case
            print_success("No missing migrations detected.")
            return True
    except Exception as e:
        print_error(f"Migration check failed with unexpected error: {e}")
        return False

def run_system_checks():
    """Run Django system checks (manage.py check)."""
    print_header("Running system checks")
    try:
        call_command('check', verbosity=1)
        print_success("System checks passed.")
        return True
    except Exception as e:
        print_error(f"System checks failed: {e}")
        return False

@override_settings(
    CACHES=READ_ONLY_CACHES,
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    ALLOWED_HOSTS=["testserver"],
)
def smoke_test_routes(routes):
    """Perform HTTP GET requests using Django's test client with read-only settings."""
    print_header("Smoke testing critical routes")
    client = Client()
    all_ok = True

    for path in routes:
        try:
            response = client.get(
                path,
                follow=True,
                # No HTTP_HOST needed; testserver is allowed by override
            )
            status = response.status_code
            final_url = response.redirect_chain[-1][0] if response.redirect_chain else path

            if 200 <= status < 400:
                print_success(f"{path} → {status} → {final_url}")
            else:
                print_error(f"{path} → {status} → {final_url}")
                all_ok = False
        except Exception as e:
            print_error(f"{path} → Exception: {e}")
            all_ok = False

    return all_ok

def main():
    """Main entry point."""
    print_header("VORNEQ Baseline Health Check")
    print("Running read-only checks... (no data will be modified)")

    # 1. System checks
    sys_check_ok = run_system_checks()

    # 2. Migration check
    migration_check_ok = check_migrations()

    # 3. Smoke test routes (list from baseline checklist, plus root)
    routes = [
        '/',           # Should redirect
        '/fa/',
        '/en/',
        '/fa/library/',
        '/fa/marketplace/',
        '/fa/accounts/login/',
        '/fa/accounts/signup/',
        '/fa/accounts/password/reset/',
        # Audio routes are discovered during manual baseline; not hardcoded here
    ]
    smoke_ok = smoke_test_routes(routes)

    # Final summary
    print_header("Summary")
    if sys_check_ok and migration_check_ok and smoke_ok:
        print_success("All baseline checks passed!")
        sys.exit(0)
    else:
        if not sys_check_ok:
            print_error("System checks failed.")
        if not migration_check_ok:
            print_error("Migration checks failed.")
        if not smoke_ok:
            print_error("Smoke tests failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
