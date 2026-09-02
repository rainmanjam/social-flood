"""Tests for keyed identity digests.

The property under test is that a digest is never *precomputable*. API keys are
short and often human-chosen, so a bare ``sha256(api_key)`` written into Redis
can be recovered by hashing a wordlist. A keyed digest cannot.
"""

import hashlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core import identity


def _with_secret(secret):
    return patch(
        "app.core.config.get_settings",
        return_value=SimpleNamespace(SECRET_KEY=secret),
    )


class TestNotPrecomputable:
    """The regression this module exists to prevent."""

    def test_digest_is_not_a_bare_sha256(self):
        # If this ever equals the plain digest, the wordlist attack is back.
        key = "short-api-key"
        bare = hashlib.sha256(key.encode()).hexdigest()[:32]
        with _with_secret("a-real-secret"):
            assert identity.keyed_digest(key) != bare

    def test_still_not_bare_sha256_without_a_secret(self):
        # The fallback must be salted, not unkeyed -- that was the old bug.
        key = "short-api-key"
        bare = hashlib.sha256(key.encode()).hexdigest()[:32]
        with _with_secret(""):
            assert identity.keyed_digest(key) != bare

    def test_settings_failure_still_does_not_fall_back_to_bare_sha256(self):
        key = "short-api-key"
        bare = hashlib.sha256(key.encode()).hexdigest()[:32]
        with patch("app.core.config.get_settings", side_effect=RuntimeError("boom")):
            assert identity.keyed_digest(key) != bare

    def test_changing_the_secret_changes_the_digest(self):
        # Proves the digest is genuinely keyed rather than merely hashed.
        with _with_secret("secret-one"):
            a = identity.keyed_digest("k")
        with _with_secret("secret-two"):
            b = identity.keyed_digest("k")
        assert a != b


class TestBasicProperties:
    def test_raw_value_never_appears_in_the_digest(self):
        with _with_secret("s"):
            assert "super-secret-key" not in identity.keyed_digest("super-secret-key")

    def test_deterministic_for_a_fixed_secret(self):
        with _with_secret("s"):
            assert identity.keyed_digest("k") == identity.keyed_digest("k")

    def test_different_values_differ(self):
        with _with_secret("s"):
            assert identity.keyed_digest("k1") != identity.keyed_digest("k2")

    def test_default_length_is_128_bits(self):
        with _with_secret("s"):
            assert len(identity.keyed_digest("k")) == 32

    @pytest.mark.parametrize("length", [8, 16, 64])
    def test_length_is_configurable(self, length):
        with _with_secret("s"):
            assert len(identity.keyed_digest("k", length=length)) == length

    def test_unicode_values_are_handled(self):
        with _with_secret("s"):
            assert len(identity.keyed_digest("clé-æ-日本")) == 32


class TestFallbackIsStableWithinAProcess:
    def test_same_process_gives_a_stable_digest_without_a_secret(self):
        # Not stable across restarts (documented), but must not change
        # mid-process or every stored owner id would be orphaned at once.
        with _with_secret(""):
            assert identity.keyed_digest("k") == identity.keyed_digest("k")
