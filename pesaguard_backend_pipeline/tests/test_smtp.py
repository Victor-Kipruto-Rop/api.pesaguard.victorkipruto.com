"""Live SMTP connectivity test. Sends only with explicit arguments.

Manual use:
    python tests/test_smtp.py --check-only
    python tests/test_smtp.py --send --to recipient@example.com

Never runs from pytest; pytest collection imports this module only.
"""
import argparse
import sys
from pathlib import Path


def create_service():
    # Delay application imports and dotenv loading until an explicit CLI action.
    backend = str(Path(__file__).resolve().parents[1])
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from email_service import EmailService
    return EmailService()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Explicit SMTP configuration or delivery test")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check-only", action="store_true", help="Validate configuration without networking")
    action.add_argument("--send", action="store_true", help="Attempt one live test email; no retries")
    parser.add_argument("--to", dest="recipient", help="Single recipient for --send")
    args = parser.parse_args(argv)
    if args.send and (not args.recipient or "@" not in args.recipient or any(
        char in args.recipient for char in "\r\n,; "
    )):
        parser.error("--send requires --to with one email address")

    service = None
    try:
        service = create_service()
        error = service.configuration_error()
        if error:
            print(f"ERROR: {error}")
            return 1
        if args.check_only:
            print("Configuration valid. No connection, authentication, or send attempted.")
            return 0
        success, _ = service._send_email(
            args.recipient, "PesaGuard SMTP Test",
            "<p>This is an explicitly requested PesaGuard SMTP test email.</p>",
            "This is an explicitly requested PesaGuard SMTP test email.",
        )
        if success:
            print("SMTP server accepted the message. Inbox delivery requires recipient confirmation.")
            return 0
        print("SMTP test failed. Check sanitized backend diagnostics; no automatic retry was made.")
        return 1
    except Exception as exc:
        print(f"SMTP test failed ({type(exc).__name__}); details withheld.")
        return 1
    finally:
        if service is not None:
            service._executor.shutdown(wait=True)


if __name__ == "__main__":
    raise SystemExit(main())

