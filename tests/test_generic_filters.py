import pytest

from secret_guard.scanner import is_hash_like_name, is_word_identifier, scan_line

RANDOM = "Vb5Nm8Qw2Z" + "x4Lk7Jh3Gf"
HEX40 = "9fceb02d0ae598e95d" + "c970b74767f19372d61af8"
SLASHED = "wJalrXUtnFEMI/K7" + "MDENG/bPxRfiCYk"


def generic(line):
    return [f for f in scan_line("f.txt", 1, line) if f.rule == "generic-secret"]


@pytest.mark.parametrize(
    "line",
    [
        'api_key_header = "X-Api-Key-Header-Name-Value"',
        'ssh_auth_sock = "/run/user/1000/keyring/ssh-agent-socket-path"',
        'token_url = "https://api.internal.corp/v1/oauth/token/refresh"',
        'config_path_token = "./secrets/token-file-location"',
        'auth_dir = "~/keys/auth-material-directory"',
        f'sha256_token = "{HEX40}"',
        f'password_hash = "{HEX40}"',
        f'etag_token = "{RANDOM}"',
        f'commit_token = "{RANDOM}"',
    ],
)
def test_non_secrets_are_not_flagged(line):
    assert generic(line) == []


@pytest.mark.parametrize(
    "line",
    [
        f'github_token = "{HEX40}"',  # token GitHub lama: 40 hex di bawah nama kredensial
        f'shared_secret = "{RANDOM}"',  # 'shared' bukan 'sha'
        f'api_key = "{SLASHED}"',  # '/' di tengah, bukan di awal
        'api_key = "Xk3Jd9-QxLmP2-vRtW7z-Yb4HnC"',  # bertanda '-', tapi berisi angka
        f'password = "{RANDOM}"',
    ],
)
def test_real_looking_secrets_are_still_flagged(line):
    assert len(generic(line)) == 1


def test_uuid_under_a_credential_name_is_still_flagged():
    # Kompromi yang disengaja: UUID memang dipakai sebagai token di dunia nyata.
    assert generic('session_token = "f47ac10b-58cc-4372-a567-0e02b2c3d479"')


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("X-Api-Key-Header-Name-Value", True),
        ("snake_case_words_only", True),
        ("two-words", False),
        ("Xk3-Jd9-QxL-mP2", False),
        ("", False),
    ],
)
def test_is_word_identifier(value, expected):
    assert is_word_identifier(value) is expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sha256_token", True),
        ("password_hash", True),
        ("MD5-Sum", True),
        ("file_checksum", True),
        ("shared_secret", False),
        ("api_key", False),
        ("shadow_token", False),
    ],
)
def test_is_hash_like_name(name, expected):
    assert bool(is_hash_like_name(name)) is expected


def test_prefix_outside_the_match_is_considered():
    # GENERIC mulai mencocokkan di 'token', jadi 'sha256_' ada di luar kecocokan.
    assert generic(f'sha256_token = "{HEX40}"') == []
    assert generic(f'plain_token = "{HEX40}"')
