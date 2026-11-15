import pytest

from secret_guard.scanner import scan_line

SECRET = "Zx7Qm4Lp9vRt" + "2WbNc8Kd"  # dirakit saat runtime, tidak tertulis utuh


def rules(line):
    return [f.rule for f in scan_line("app.env", 1, line)]


@pytest.mark.parametrize(
    "line",
    [
        f"DB_PASSWORD={SECRET}",
        f"export API_TOKEN={SECRET}",
        f"  SECRET_KEY={SECRET}  # produksi",
        f"db-password={SECRET}",
    ],
)
def test_unquoted_dotenv_secret_is_flagged(line):
    assert rules(line) == ["generic-secret"]


@pytest.mark.parametrize(
    "line",
    [
        f"token = {SECRET}",  # spasi di sekitar '=' bukan bentuk dotenv
        "PORT=8080",
        "SECRET_KEY=${SECRET_KEY_FROM_VAULT}",
        "DB_PASSWORD_FILE=/run/secrets/db_password_file",
        "AUTH_ENDPOINT=https://login.example.com/oauth2/authorize",
        "BUILD_CHECKSUM_TOKEN=a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
        f"APP_NAME={SECRET}",  # nama kunci tidak memuat kata rahasia
        "DB_PASSWORD=abc123",
    ],
)
def test_unquoted_dotenv_lookalikes_are_not_flagged(line):
    assert rules(line) == []


def test_unquoted_finding_does_not_leak_secret():
    (finding,) = scan_line("app.env", 1, f"DB_PASSWORD={SECRET}")
    assert SECRET not in repr(finding)
