"""Target guard: tests may only ever reach local hosts."""

import pytest

from qe.config import PROJECT_ROOT, Settings, UnsafeTargetError

pytestmark = pytest.mark.unit


def test_defaults_point_at_local_aut():
    s = Settings.from_env({})
    assert s.api_url == "http://localhost:8080"
    assert s.ui_url == "http://localhost:5173"
    assert s.aut_dir == PROJECT_ROOT.parent / "git-demo" / "starter_code"


@pytest.mark.parametrize("url", ["http://127.0.0.1:8080/", "http://[::1]:8080", "https://localhost:8443"])
def test_loopback_urls_are_accepted_and_normalised(url):
    s = Settings.from_env({"AUT_API_URL": url})
    assert s.api_url == url.rstrip("/")


@pytest.mark.parametrize(
    "url",
    [
        "https://api.example.com",          # remote host
        "http://localhost.example.com",     # loopback name used as a prefix
        "http://localhost@example.com",     # userinfo trick: real host is example.com
        "http://10.0.0.5:8080",             # private network but not loopback
        "ftp://localhost/x",                # wrong scheme
    ],
)
def test_non_local_or_unsafe_urls_are_rejected(url):
    with pytest.raises(UnsafeTargetError):
        Settings.from_env({"AUT_API_URL": url})


def test_ui_url_is_validated_too():
    with pytest.raises(UnsafeTargetError):
        Settings.from_env({"AUT_UI_URL": "https://shop.example.com"})


def test_compose_service_names_need_explicit_opt_in():
    with pytest.raises(UnsafeTargetError):
        Settings.from_env({"AUT_API_URL": "http://backend:8080"})
    s = Settings.from_env({"AUT_API_URL": "http://backend:8080", "QE_ALLOWED_HOSTS": "backend, frontend"})
    assert s.api_url == "http://backend:8080"
