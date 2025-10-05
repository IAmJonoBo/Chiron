"""Tests for chiron.deps.signing module - artifact signing and verification."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest

from chiron.deps.signing import (
    CosignSigner,
    SigningResult,
    sign_wheelhouse_bundle,
    verify_wheelhouse_bundle,
)


class TestSigningResult:
    """Tests for SigningResult dataclass."""

    def test_signing_result_success(self) -> None:
        """Test successful signing result."""
        result = SigningResult(
            success=True,
            signature_path=Path("/tmp/test.sig"),
            certificate_path=Path("/tmp/test.crt"),
        )
        assert result.success is True
        assert result.signature_path == Path("/tmp/test.sig")
        assert result.certificate_path == Path("/tmp/test.crt")
        assert result.error_message is None

    def test_signing_result_failure(self) -> None:
        """Test failed signing result."""
        result = SigningResult(success=False, error_message="cosign not found")
        assert result.success is False
        assert result.signature_path is None
        assert result.certificate_path is None
        assert result.error_message == "cosign not found"


class TestCosignSigner:
    """Tests for CosignSigner class."""

    def test_initialization_keyless(self) -> None:
        """Test CosignSigner initialization with keyless mode."""
        signer = CosignSigner(keyless=True)
        assert signer.keyless is True

    def test_initialization_with_keys(self) -> None:
        """Test CosignSigner initialization with key-based signing."""
        signer = CosignSigner(keyless=False)
        assert signer.keyless is False

    @patch("chiron.deps.signing.shutil.which")
    def test_sign_blob_cosign_not_found(self, mock_which: Mock) -> None:
        """Test sign_blob when cosign is not available."""
        mock_which.return_value = None
        signer = CosignSigner()

        result = signer.sign_blob(Path("/tmp/test.tar.gz"))

        assert result.success is False
        assert result.error_message == "cosign not found in PATH"
        assert result.signature_path is None

    @patch("chiron.deps.signing.shutil.which")
    def test_sign_blob_artifact_not_found(self, mock_which: Mock) -> None:
        """Test sign_blob when artifact doesn't exist."""
        mock_which.return_value = "/usr/bin/cosign"
        signer = CosignSigner()

        artifact_path = Path("/tmp/nonexistent.tar.gz")
        result = signer.sign_blob(artifact_path)

        assert result.success is False
        assert "Artifact not found" in result.error_message
        assert result.signature_path is None

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_sign_blob_success(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test successful blob signing."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(returncode=0, stderr="")

        # Create a test artifact
        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")

        signer = CosignSigner(keyless=True)
        result = signer.sign_blob(artifact)

        assert result.success is True
        assert result.signature_path is not None
        assert result.signature_path.name == "test.tar.gz.sig"
        assert result.error_message is None

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "/usr/bin/cosign" in call_args[0][0]
        assert "sign-blob" in call_args[0][0]
        assert "--yes" in call_args[0][0]
        assert str(artifact) in call_args[0][0]
        assert call_args[1]["env"]["COSIGN_EXPERIMENTAL"] == "1"

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_sign_blob_with_custom_output(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test signing with custom output path."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(returncode=0, stderr="")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")
        signature_path = tmp_path / "custom.sig"

        signer = CosignSigner()
        result = signer.sign_blob(artifact, signature_path)

        assert result.success is True
        assert result.signature_path == signature_path

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_sign_blob_subprocess_failure(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test signing when subprocess fails."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(returncode=1, stderr="signing failed")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")

        signer = CosignSigner()
        result = signer.sign_blob(artifact)

        assert result.success is False
        assert result.error_message == "signing failed"
        assert result.signature_path is None

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_sign_blob_exception_handling(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test signing exception handling."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.side_effect = Exception("Unexpected error")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")

        signer = CosignSigner()
        result = signer.sign_blob(artifact)

        assert result.success is False
        assert "Unexpected error" in result.error_message

    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_cosign_not_found(self, mock_which: Mock) -> None:
        """Test verify_blob when cosign is not available."""
        mock_which.return_value = None
        signer = CosignSigner()

        result = signer.verify_blob(
            Path("/tmp/test.tar.gz"), Path("/tmp/test.tar.gz.sig")
        )

        assert result is False

    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_artifact_not_found(self, mock_which: Mock) -> None:
        """Test verify_blob when artifact doesn't exist."""
        mock_which.return_value = "/usr/bin/cosign"
        signer = CosignSigner()

        result = signer.verify_blob(
            Path("/tmp/nonexistent.tar.gz"), Path("/tmp/test.sig")
        )

        assert result is False

    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_signature_not_found(
        self, mock_which: Mock, tmp_path: Path
    ) -> None:
        """Test verify_blob when signature doesn't exist."""
        mock_which.return_value = "/usr/bin/cosign"

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")

        signer = CosignSigner()
        result = signer.verify_blob(artifact, Path("/tmp/nonexistent.sig"))

        assert result is False

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_success(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test successful blob verification."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")
        signature = tmp_path / "test.tar.gz.sig"
        signature.write_text("signature")

        signer = CosignSigner(keyless=True)
        result = signer.verify_blob(artifact, signature)

        assert result is True

        # Verify subprocess was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "/usr/bin/cosign" in call_args[0][0]
        assert "verify-blob" in call_args[0][0]
        assert "--signature" in call_args[0][0]
        assert str(signature) in call_args[0][0]
        assert str(artifact) in call_args[0][0]
        assert call_args[1]["env"]["COSIGN_EXPERIMENTAL"] == "1"

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_with_certificate(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test verification with certificate."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")
        signature = tmp_path / "test.tar.gz.sig"
        signature.write_text("signature")
        cert = tmp_path / "test.crt"
        cert.write_text("certificate")

        signer = CosignSigner()
        result = signer.verify_blob(artifact, signature, certificate_path=cert)

        assert result is True
        call_args = mock_run.call_args
        assert "--certificate" in call_args[0][0]
        assert str(cert) in call_args[0][0]

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_with_identity(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test verification with certificate identity."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")
        signature = tmp_path / "test.tar.gz.sig"
        signature.write_text("signature")

        signer = CosignSigner()
        result = signer.verify_blob(
            artifact,
            signature,
            certificate_identity="user@example.com",
            certificate_oidc_issuer="https://accounts.google.com",
        )

        assert result is True
        call_args = mock_run.call_args
        assert "--certificate-identity" in call_args[0][0]
        assert "user@example.com" in call_args[0][0]
        assert "--certificate-oidc-issuer" in call_args[0][0]
        assert "https://accounts.google.com" in call_args[0][0]

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_failure(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test verification failure."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.return_value = Mock(
            returncode=1, stderr="verification failed", stdout=""
        )

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")
        signature = tmp_path / "test.tar.gz.sig"
        signature.write_text("signature")

        signer = CosignSigner()
        result = signer.verify_blob(artifact, signature)

        assert result is False

    @patch("chiron.deps.signing.subprocess.run")
    @patch("chiron.deps.signing.shutil.which")
    def test_verify_blob_exception_handling(
        self, mock_which: Mock, mock_run: Mock, tmp_path: Path
    ) -> None:
        """Test verification exception handling."""
        mock_which.return_value = "/usr/bin/cosign"
        mock_run.side_effect = Exception("Unexpected error")

        artifact = tmp_path / "test.tar.gz"
        artifact.write_text("test content")
        signature = tmp_path / "test.tar.gz.sig"
        signature.write_text("signature")

        signer = CosignSigner()
        result = signer.verify_blob(artifact, signature)

        assert result is False


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    @patch("chiron.deps.signing.CosignSigner.sign_blob")
    def test_sign_wheelhouse_bundle_default_output(self, mock_sign: Mock) -> None:
        """Test sign_wheelhouse_bundle with default output."""
        mock_sign.return_value = SigningResult(
            success=True, signature_path=Path("/tmp/bundle.tar.gz.sig")
        )

        bundle = Path("/tmp/bundle.tar.gz")
        result = sign_wheelhouse_bundle(bundle)

        assert result.success is True
        mock_sign.assert_called_once()
        # Check that signature path is based on bundle path
        call_args = mock_sign.call_args
        assert call_args[0][0] == bundle
        assert ".sig" in str(call_args[0][1])

    @patch("chiron.deps.signing.CosignSigner.sign_blob")
    def test_sign_wheelhouse_bundle_custom_output(self, mock_sign: Mock) -> None:
        """Test sign_wheelhouse_bundle with custom output directory."""
        mock_sign.return_value = SigningResult(
            success=True, signature_path=Path("/output/bundle.tar.gz.sig")
        )

        bundle = Path("/tmp/bundle.tar.gz")
        output_dir = Path("/output")
        result = sign_wheelhouse_bundle(bundle, output_dir)

        assert result.success is True
        mock_sign.assert_called_once()
        call_args = mock_sign.call_args
        assert call_args[0][1] == output_dir / "bundle.tar.gz.sig"

    @patch("chiron.deps.signing.CosignSigner.verify_blob")
    def test_verify_wheelhouse_bundle_success(self, mock_verify: Mock) -> None:
        """Test verify_wheelhouse_bundle success."""
        mock_verify.return_value = True

        bundle = Path("/tmp/bundle.tar.gz")
        signature = Path("/tmp/bundle.tar.gz.sig")
        result = verify_wheelhouse_bundle(bundle, signature)

        assert result is True
        mock_verify.assert_called_once_with(bundle, signature)

    @patch("chiron.deps.signing.CosignSigner.verify_blob")
    def test_verify_wheelhouse_bundle_failure(self, mock_verify: Mock) -> None:
        """Test verify_wheelhouse_bundle failure."""
        mock_verify.return_value = False

        bundle = Path("/tmp/bundle.tar.gz")
        signature = Path("/tmp/bundle.tar.gz.sig")
        result = verify_wheelhouse_bundle(bundle, signature)

        assert result is False
        mock_verify.assert_called_once_with(bundle, signature)
