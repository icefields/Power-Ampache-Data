"""CLI: python -m ampachedata init-credentials ...

First-run credentials bootstrap. The cleartext password is accepted ONCE here —
via hidden getpass prompt, stdin, or an environment variable — hashed with SHA256
in memory, and only the digest is written to the single CredentialsEntity row.
There is deliberately no --password flag: cleartext never appears in argv, shell
history, or ps. Nothing else is touched: no handshake, no SessionEntity write."""
import argparse
import getpass
import os
import sys

from .data.Bootstrap import storeCredentialsFromKey, storeCredentialsFromPassword
from .data.errors import AmpacheError, CredentialValidationError


def main(argv=None) -> int:
    args = _buildParser().parse_args(argv)
    try:
        return _runInitCredentials(args)
    except (EOFError, KeyboardInterrupt):
        print("aborted", file=sys.stderr)
        return 130


def _buildParser():
    parser = argparse.ArgumentParser(prog="python -m ampachedata")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser(
        "init-credentials",
        help="first-run bootstrap: write the single CredentialsEntity row (hash only)",
        description=(
            "Store the single CredentialsEntity row. The cleartext password is "
            "accepted once — hidden prompt, stdin, or env var — hashed with "
            "SHA256 in memory, and only the digest is stored. There is no "
            "--password flag: cleartext never appears in argv."
        ),
    )
    init.add_argument("--db-path", required=True,
                      help="path to an existing musicdb.db (never created)")
    init.add_argument("--username",
                      help="Ampache username (prompted when omitted interactively)")
    init.add_argument("--server-url",
                      help="https://server (prompted when omitted interactively)")
    source = init.add_mutually_exclusive_group()
    source.add_argument("--password-stdin", action="store_true",
                        help="read the cleartext password from one stdin line")
    source.add_argument("--password-env", metavar="VARNAME",
                        help="read the cleartext password from this environment variable")
    source.add_argument("--key", metavar="HASH",
                        help="pre-hashed 64-hex key (visible in argv/shell history — "
                             "prefer --key-stdin)")
    source.add_argument("--key-stdin", action="store_true",
                        help="read the pre-hashed 64-hex key from one stdin line")
    return parser


def _runInitCredentials(args) -> int:
    source = _secretSource(args)
    username = args.username
    serverUrl = args.server_url

    if source is None:  # interactive
        if not sys.stdin.isatty():
            print("error: no secret source given and stdin is not a TTY — pass "
                  "--password-stdin, --password-env VARNAME, --key, or --key-stdin",
                  file=sys.stderr)
            return 2
        if not username:
            username = input("Username: ").strip()
        if not serverUrl:
            serverUrl = input("Server URL: ").strip()
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Confirm password: "):
            print("error: passwords do not match", file=sys.stderr)
            return 2
        return _finish(storeCredentialsFromPassword, args.db_path, username, serverUrl, password)

    if not username or not serverUrl:
        print("error: --username and --server-url are required with " + source,
              file=sys.stderr)
        return 2
    if source == "--password-stdin":
        return _finish(storeCredentialsFromPassword, args.db_path, username, serverUrl,
                       _readSecretLine())
    if source == "--password-env":
        password = os.environ.get(args.password_env)
        if password is None:
            print("error: environment variable " + args.password_env + " is not set",
                  file=sys.stderr)
            return 2
        return _finish(storeCredentialsFromPassword, args.db_path, username, serverUrl, password)
    if source == "--key":
        return _finish(storeCredentialsFromKey, args.db_path, username, serverUrl, args.key)
    return _finish(storeCredentialsFromKey, args.db_path, username, serverUrl,
                   _readSecretLine())  # --key-stdin


def _secretSource(args):
    if args.password_stdin:
        return "--password-stdin"
    if args.password_env:
        return "--password-env"
    if args.key is not None:
        return "--key"
    if args.key_stdin:
        return "--key-stdin"
    return None


def _readSecretLine() -> str:
    line = sys.stdin.readline()
    if line.endswith("\n"):
        line = line[:-1]
    if line.endswith("\r"):
        line = line[:-1]
    return line


def _finish(storeFn, dbPath, username, serverUrl, secret) -> int:
    try:
        storeFn(dbPath, username, serverUrl, secret)
    except CredentialValidationError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    except AmpacheError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1
    print("Stored credentials for user '" + username + "' at " + serverUrl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
