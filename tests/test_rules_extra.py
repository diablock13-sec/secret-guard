import pytest

from secret_guard.scanner import scan_line

STRIPE = "sk_" + "live_" + "51Hx7Kq2ZmX9vLp4RwYc7Nb3"
GOOGLE = "AIza" + "SyD3k9QxLmP2vRtW7zYb4HnCe8UaFs1GoXi"
JWT = (
    "eyJhbGciOiJIUzI1NiJ9."
    + "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    + "k3Jd9QxLmP2vRtW7zYb4HnCe8UaFs1GoXi5"
)
PASSWORD = "t8Kq2ZmX9vLp" + "4RwYc7Nb"


def rules(line):
    return {f.rule for f in scan_line("f.txt", 1, line)}


# ---- Stripe ----


def test_stripe_live_key_detected():
    assert "stripe-secret-key" in rules(f'KEY = "{STRIPE}"')


def test_stripe_restricted_live_key_detected():
    assert "stripe-secret-key" in rules(f'KEY = "{STRIPE.replace("sk_", "rk_", 1)}"')


def test_stripe_test_key_not_detected():
    test_key = "sk_" + "test_51Hx7Kq2ZmX9vLp4RwYc7Nb3"
    assert "stripe-secret-key" not in rules(f'KEY = "{test_key}"')


def test_stripe_key_too_short_not_detected():
    assert "stripe-secret-key" not in rules('KEY = "sk_' + 'live_abc"')


# ---- Google ----


def test_google_key_detected():
    assert "google-api-key" in rules(f'maps = "{GOOGLE}"')


def test_google_key_ending_with_hyphen_detected():
    key = "AIza" + "SyD3k9QxLmP2vRtW7zYb4HnCe8UaFs1GoX" + "-"
    assert "google-api-key" in rules(f'maps = "{key}"')


def test_google_key_wrong_length_not_detected():
    short = "AIza" + "SyD3k9QxLmP2vRtW7zYb4HnCe8UaFs1GoX"
    assert "google-api-key" not in rules(f'maps = "{short}"')


# ---- JWT ----


def test_jwt_detected_in_bearer_header():
    assert "jwt" in rules(f"Authorization: Bearer {JWT}")


def test_two_part_token_is_not_a_jwt():
    assert "jwt" not in rules("x = eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0")


# ---- kredensial di URL ----


@pytest.mark.parametrize(
    "line",
    [
        f'DATABASE_URL = "postgres://admin:{PASSWORD}@db.internal:5432/app"',
        f"mysql://root:{PASSWORD}@localhost/test",
        f"redis://default:{PASSWORD}@cache:6379",
    ],
)
def test_url_with_real_looking_password_detected(line):
    assert "url-credentials" in rules(line)


@pytest.mark.parametrize(
    "line",
    [
        'DATABASE_URL = "postgres://user:password@localhost:5432/app"',
        'DATABASE_URL = "postgres://admin:${DB_PASSWORD}@db.internal/app"',
        "postgres://admin:changeme1234@localhost/app",
        "postgres://admin:<your-password>@localhost/app",
        "postgres://admin:xxxxxxxxxx@localhost/app",
        "curl http://localhost:8080/path?email=dev@example.com",
        "git clone https://github.com/acme/private.git",
        "remote = ssh://git@github.com/acme/repo.git",
        "postgres://admin:short@localhost/app",
    ],
)
def test_url_without_real_credentials_not_detected(line):
    assert "url-credentials" not in rules(line)


# ---- kunci JSON pada regex umum ----


def test_json_style_key_detected():
    secret = "Vb5Nm8Qw2Z" + "x4Lk7Jh3Gf"
    assert "generic-secret" in rules(f'"client_secret": "{secret}"')


def test_json_style_short_value_not_detected():
    assert "generic-secret" not in rules('"client_secret": "short"')


# ---- pratinjau tidak pernah memuat rahasia utuh ----


@pytest.mark.parametrize(
    ("secret", "line"),
    [
        (STRIPE, f'KEY = "{STRIPE}"'),
        (GOOGLE, f'maps = "{GOOGLE}"'),
        (JWT, f"Authorization: Bearer {JWT}"),
        (PASSWORD, f"mysql://root:{PASSWORD}@localhost/test"),
    ],
)
def test_previews_never_contain_the_secret(secret, line):
    findings = scan_line("f.txt", 1, line)
    assert findings
    assert all(secret not in f.preview for f in findings)
