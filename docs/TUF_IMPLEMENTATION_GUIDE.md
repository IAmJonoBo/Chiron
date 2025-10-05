# TUF Implementation Guide

This guide provides a roadmap for completing The Update Framework (TUF) implementation with key management and signing capabilities.

## Overview

Chiron currently has a foundation for TUF metadata generation. This guide outlines the remaining work needed for a production-ready TUF implementation.

**Current Status**: Foundation complete (metadata structure, hash generation)
**Target**: Full TUF 1.0.0 implementation with key management

---

## 1. Current Implementation

### What Works

✅ **Metadata Generation**:

- Root metadata structure
- Targets metadata with SHA256/SHA512 hashes
- Snapshot metadata
- Timestamp metadata
- Platform detection
- Expiration management

✅ **Metadata Verification**:

- Required fields validation
- Expiration checking
- Spec version validation

✅ **Repository Management**:

- Initialize repository structure
- Save/load metadata
- File organization

### What's Missing

❌ **Key Management**:

- Key generation
- Key storage/retrieval
- Key rotation
- Threshold signatures

❌ **Signing**:

- Metadata signing
- Signature verification
- Keyless signing (Sigstore)

❌ **Advanced Features**:

- Delegations
- Multi-role support
- Consistent snapshots
- Key revocation

---

## 2. Key Management Requirements

### Key Types

**Root Keys**: Sign root metadata

- Highest security level
- Offline storage recommended
- Threshold: 2+ keys required

**Targets Keys**: Sign targets metadata

- Medium security level
- Can be online
- Threshold: 1+ keys

**Snapshot Keys**: Sign snapshot metadata

- Lower security level
- Should be online
- Threshold: 1 key

**Timestamp Keys**: Sign timestamp metadata

- Lowest security level
- Must be online
- Threshold: 1 key

### Key Generation

Implement key generation utilities:

```python
# In src/chiron/tuf_keys.py

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.backends import default_backend
from pathlib import Path
from typing import Literal


class TUFKeyManager:
    """Manage TUF signing keys."""

    def __init__(self, keys_dir: Path | str):
        """Initialize key manager.

        Args:
            keys_dir: Directory to store keys
        """
        self.keys_dir = Path(keys_dir)
        self.keys_dir.mkdir(parents=True, exist_ok=True)

    def generate_key(
        self,
        role: Literal["root", "targets", "snapshot", "timestamp"],
        key_type: Literal["ed25519", "rsa"] = "ed25519"
    ) -> dict[str, str]:
        """Generate a new signing key.

        Args:
            role: TUF role for this key
            key_type: Type of key to generate

        Returns:
            Dict with keyid and public key
        """
        if key_type == "ed25519":
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            # Serialize keys
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    password=self._get_password(role).encode()
                )
            )

            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

        elif key_type == "rsa":
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
                backend=default_backend()
            )
            # Similar serialization...

        # Generate key ID
        keyid = self._generate_keyid(public_pem)

        # Save keys
        self._save_key(role, keyid, private_pem, public_pem)

        return {
            "keyid": keyid,
            "public_key": public_pem.decode()
        }

    def _generate_keyid(self, public_key: bytes) -> str:
        """Generate key ID from public key."""
        import hashlib
        return hashlib.sha256(public_key).hexdigest()

    def _get_password(self, role: str) -> str:
        """Get password for key encryption.

        In production, use secure key management system.
        Supports multiple secure key storage backends:
        - Environment variables (default)
        - AWS Secrets Manager
        - Azure Key Vault
        - HashiCorp Vault
        - System keyring
        """
        import os

        # Priority 1: Check environment variable
        env_password = os.environ.get(f"TUF_{role.upper()}_KEY_PASSWORD")
        if env_password:
            return env_password

        # Priority 2: Try system keyring if available
        try:
            import keyring
            keyring_password = keyring.get_password("chiron-tuf", role)
            if keyring_password:
                logger.info(f"Retrieved {role} key password from system keyring")
                return keyring_password
        except ImportError:
            pass  # keyring not installed
        except Exception as e:
            logger.debug(f"Could not access keyring: {e}")

        # Priority 3: Try AWS Secrets Manager
        try:
            import boto3
            aws_secret_name = os.environ.get("TUF_AWS_SECRET_NAME")
            if aws_secret_name:
                client = boto3.client("secretsmanager")
                response = client.get_secret_value(SecretId=aws_secret_name)
                secrets = json.loads(response["SecretString"])
                password = secrets.get(f"{role}_key_password")
                if password:
                    logger.info(f"Retrieved {role} key password from AWS Secrets Manager")
                    return password
        except ImportError:
            pass  # boto3 not installed
        except Exception as e:
            logger.debug(f"Could not access AWS Secrets Manager: {e}")

        # Priority 4: Try Azure Key Vault
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            vault_url = os.environ.get("TUF_AZURE_VAULT_URL")
            if vault_url:
                credential = DefaultAzureCredential()
                client = SecretClient(vault_url=vault_url, credential=credential)
                secret = client.get_secret(f"tuf-{role}-key-password")
                if secret.value:
                    logger.info(f"Retrieved {role} key password from Azure Key Vault")
                    return secret.value
        except ImportError:
            pass  # azure libraries not installed
        except Exception as e:
            logger.debug(f"Could not access Azure Key Vault: {e}")

        # Priority 5: Try HashiCorp Vault
        try:
            import hvac

            vault_addr = os.environ.get("VAULT_ADDR")
            vault_token = os.environ.get("VAULT_TOKEN")
            if vault_addr and vault_token:
                client = hvac.Client(url=vault_addr, token=vault_token)
                if client.is_authenticated():
                    secret_path = f"secret/chiron/tuf/{role}"
                    secret = client.secrets.kv.v2.read_secret_version(path=secret_path)
                    password = secret["data"]["data"].get("password")
                    if password:
                        logger.info(f"Retrieved {role} key password from HashiCorp Vault")
                        return password
        except ImportError:
            pass  # hvac not installed
        except Exception as e:
            logger.debug(f"Could not access HashiCorp Vault: {e}")

        # Fallback: Use default (insecure, for development only)
        logger.warning(
            f"Using default password for {role} key - not secure for production! "
            "Set TUF_{role.upper()}_KEY_PASSWORD environment variable or configure "
            "a secure key storage backend."
        )
        return "changeme"

    def _save_key(
        self,
        role: str,
        keyid: str,
        private_pem: bytes,
        public_pem: bytes
    ) -> None:
        """Save key pair to disk."""
        # Save private key (secure location)
        private_path = self.keys_dir / f"{role}_{keyid}_private.pem"
        private_path.write_bytes(private_pem)
        private_path.chmod(0o600)  # Secure permissions

        # Save public key
        public_path = self.keys_dir / f"{role}_{keyid}_public.pem"
        public_path.write_bytes(public_pem)
        public_path.chmod(0o644)

    def load_key(self, role: str, keyid: str):
        """Load a signing key.

        Args:
            role: TUF role
            keyid: Key identifier

        Returns:
            Private key object
        """
        private_path = self.keys_dir / f"{role}_{keyid}_private.pem"

        if not private_path.exists():
            raise FileNotFoundError(f"Key not found: {private_path}")

        private_pem = private_path.read_bytes()
        password = self._get_password(role).encode()

        # Load and decrypt private key
        private_key = serialization.load_pem_private_key(
            private_pem,
            password=password,
            backend=default_backend()
        )

        return private_key
```

---

## 3. Metadata Signing

### Sign Metadata

Extend `TUFMetadata` class in `src/chiron/tuf_metadata.py`:

```python
from chiron.tuf_keys import TUFKeyManager
from cryptography.hazmat.primitives import hashes


class TUFMetadata:
    """TUF metadata generator and verifier."""

    def __init__(self, repo_path: Path | str, keys_dir: Path | str | None = None):
        """Initialize TUF metadata manager.

        Args:
            repo_path: Path to the repository
            keys_dir: Optional path to keys directory
        """
        self.repo_path = Path(repo_path)
        self.metadata_path = self.repo_path / "metadata"
        self.targets_path = self.repo_path / "targets"

        if keys_dir:
            self.key_manager = TUFKeyManager(keys_dir)
        else:
            self.key_manager = None

    def sign_metadata(
        self,
        metadata: dict[str, Any],
        role: str,
        keyids: list[str]
    ) -> dict[str, Any]:
        """Sign metadata with specified keys.

        Args:
            metadata: Metadata to sign
            role: TUF role
            keyids: List of key IDs to use for signing

        Returns:
            Signed metadata
        """
        if not self.key_manager:
            raise ValueError("Key manager not initialized")

        # Canonical JSON for signing
        canonical = self._canonicalize(metadata)

        signatures = []
        for keyid in keyids:
            # Load key
            private_key = self.key_manager.load_key(role, keyid)

            # Sign
            signature = private_key.sign(canonical.encode())

            signatures.append({
                "keyid": keyid,
                "sig": signature.hex()
            })

        # Add signatures to metadata
        signed_metadata = {
            "signed": metadata,
            "signatures": signatures
        }

        return signed_metadata

    def verify_signature(
        self,
        signed_metadata: dict[str, Any],
        public_keys: dict[str, str]
    ) -> tuple[bool, list[str]]:
        """Verify metadata signatures.

        Args:
            signed_metadata: Signed metadata
            public_keys: Dict of keyid -> public key PEM

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        if "signed" not in signed_metadata:
            return False, ["Missing 'signed' field"]

        if "signatures" not in signed_metadata:
            return False, ["Missing 'signatures' field"]

        # Canonical form of signed data
        canonical = self._canonicalize(signed_metadata["signed"])

        valid_signatures = 0
        for sig_entry in signed_metadata["signatures"]:
            keyid = sig_entry["keyid"]
            signature_hex = sig_entry["sig"]

            if keyid not in public_keys:
                errors.append(f"Unknown key: {keyid}")
                continue

            try:
                # Load public key
                public_key = serialization.load_pem_public_key(
                    public_keys[keyid].encode(),
                    backend=default_backend()
                )

                # Verify signature
                signature = bytes.fromhex(signature_hex)
                public_key.verify(signature, canonical.encode())
                valid_signatures += 1

            except Exception as e:
                errors.append(f"Signature verification failed for {keyid}: {e}")

        # Check threshold (simplified)
        threshold = signed_metadata["signed"].get("threshold", 1)
        if valid_signatures < threshold:
            errors.append(f"Insufficient signatures: {valid_signatures}/{threshold}")
            return False, errors

        return True, []

    def _canonicalize(self, data: dict) -> str:
        """Convert to canonical JSON for signing."""
        import json
        return json.dumps(data, sort_keys=True, separators=(',', ':'))
```

---

## 4. Keyless Signing with Sigstore

### Integrate Sigstore

For keyless signing (no key management required):

```python
# In src/chiron/tuf_sigstore.py

import subprocess
from pathlib import Path


class SigstoreSigner:
    """Sign TUF metadata using Sigstore."""

    def sign_metadata(self, metadata_path: Path) -> Path:
        """Sign metadata file using Sigstore.

        Args:
            metadata_path: Path to metadata file

        Returns:
            Path to signature file
        """
        signature_path = metadata_path.with_suffix(".sig")

        # Use cosign to sign
        result = subprocess.run(
            [
                "cosign",
                "sign-blob",
                "--yes",  # Keyless mode
                "--output-signature", str(signature_path),
                str(metadata_path)
            ],
            capture_output=True,
            text=True,
            check=True
        )

        return signature_path

    def verify_signature(
        self,
        metadata_path: Path,
        signature_path: Path
    ) -> bool:
        """Verify Sigstore signature.

        Args:
            metadata_path: Path to metadata file
            signature_path: Path to signature file

        Returns:
            True if valid, False otherwise
        """
        try:
            result = subprocess.run(
                [
                    "cosign",
                    "verify-blob",
                    "--signature", str(signature_path),
                    str(metadata_path)
                ],
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False
```

---

## 5. CLI Integration

### Add TUF Commands

Extend `src/chiron/cli/main.py`:

```python
import typer
from pathlib import Path

tuf_app = typer.Typer(help="TUF metadata management commands")


@tuf_app.command("init")
def tuf_init(
    repo_path: Path = typer.Option(".", help="Repository path"),
    keys_dir: Path = typer.Option("keys", help="Keys directory"),
):
    """Initialize TUF repository with keys."""
    from chiron.tuf_metadata import TUFMetadata
    from chiron.tuf_keys import TUFKeyManager

    # Initialize repository
    tuf = TUFMetadata(repo_path, keys_dir)
    tuf.initialize_repo()

    # Generate keys
    km = TUFKeyManager(keys_dir)

    typer.echo("Generating keys...")
    root_key = km.generate_key("root")
    targets_key = km.generate_key("targets")
    snapshot_key = km.generate_key("snapshot")
    timestamp_key = km.generate_key("timestamp")

    typer.secho(f"✅ Root key: {root_key['keyid']}", fg="green")
    typer.secho(f"✅ Targets key: {targets_key['keyid']}", fg="green")
    typer.secho(f"✅ Snapshot key: {snapshot_key['keyid']}", fg="green")
    typer.secho(f"✅ Timestamp key: {timestamp_key['keyid']}", fg="green")


@tuf_app.command("sign")
def tuf_sign(
    metadata_file: Path = typer.Argument(..., help="Metadata file to sign"),
    role: str = typer.Option(..., help="TUF role"),
    keyid: str = typer.Option(..., help="Key ID to use"),
    output: Path = typer.Option(None, help="Output file"),
):
    """Sign TUF metadata."""
    from chiron.tuf_metadata import TUFMetadata
    import json

    # Load metadata
    with open(metadata_file) as f:
        metadata = json.load(f)

    # Sign
    tuf = TUFMetadata(metadata_file.parent, keys_dir="keys")
    signed = tuf.sign_metadata(metadata, role, [keyid])

    # Save
    output_file = output or metadata_file.with_suffix(".signed.json")
    with open(output_file, "w") as f:
        json.dump(signed, f, indent=2)

    typer.secho(f"✅ Signed metadata saved to {output_file}", fg="green")


@tuf_app.command("verify")
def tuf_verify(
    signed_file: Path = typer.Argument(..., help="Signed metadata file"),
    keys_file: Path = typer.Option("keys/public_keys.json", help="Public keys file"),
):
    """Verify TUF metadata signature."""
    from chiron.tuf_metadata import TUFMetadata
    import json

    # Load signed metadata
    with open(signed_file) as f:
        signed_metadata = json.load(f)

    # Load public keys
    with open(keys_file) as f:
        public_keys = json.load(f)

    # Verify
    tuf = TUFMetadata(signed_file.parent)
    is_valid, errors = tuf.verify_signature(signed_metadata, public_keys)

    if is_valid:
        typer.secho("✅ Signature is valid", fg="green")
    else:
        typer.secho("❌ Signature verification failed:", fg="red")
        for error in errors:
            typer.echo(f"  - {error}")
        raise typer.Exit(1)


# Add to main app
app.add_typer(tuf_app, name="tuf")
```

---

## 6. Testing Requirements

### Unit Tests

Extend `tests/test_tuf_metadata.py`:

```python
class TestTUFSigning:
    """Test TUF signing functionality."""

    def test_key_generation(self, tmp_path):
        """Test key generation."""
        from chiron.tuf_keys import TUFKeyManager

        km = TUFKeyManager(tmp_path / "keys")
        key = km.generate_key("root", "ed25519")

        assert "keyid" in key
        assert "public_key" in key
        assert len(key["keyid"]) == 64  # SHA256 hex

    def test_sign_metadata(self, tmp_path):
        """Test metadata signing."""
        from chiron.tuf_metadata import TUFMetadata
        from chiron.tuf_keys import TUFKeyManager

        # Generate key
        km = TUFKeyManager(tmp_path / "keys")
        key = km.generate_key("root")

        # Create and sign metadata
        tuf = TUFMetadata(tmp_path, keys_dir=tmp_path / "keys")
        tuf.initialize_repo()

        metadata = tuf.generate_root_metadata()
        signed = tuf.sign_metadata(metadata, "root", [key["keyid"]])

        assert "signed" in signed
        assert "signatures" in signed
        assert len(signed["signatures"]) == 1

    def test_verify_signature(self, tmp_path):
        """Test signature verification."""
        # ... test implementation
```

---

## 7. Security Considerations

### Key Storage

**Development**:

- Store keys in local files
- Encrypt with passwords
- Use secure file permissions

**Production**:

- Use HSM (Hardware Security Module)
- Or cloud KMS (AWS KMS, Google Cloud KMS, Azure Key Vault)
- Implement key rotation
- Audit key access

### Key Rotation

Implement key rotation:

```python
def rotate_key(
    role: str,
    old_keyid: str,
    new_keyid: str,
    metadata: dict
) -> dict:
    """Rotate a key in metadata.

    Args:
        role: TUF role
        old_keyid: Key ID to replace
        new_keyid: New key ID
        metadata: Root or delegations metadata

    Returns:
        Updated metadata
    """
    # Remove old key
    if old_keyid in metadata["keys"]:
        del metadata["keys"][old_keyid]

    # Add new key
    # Update role keyids
    if role in metadata["roles"]:
        keyids = metadata["roles"][role]["keyids"]
        if old_keyid in keyids:
            keyids.remove(old_keyid)
        keyids.append(new_keyid)

    # Increment version
    metadata["version"] += 1

    return metadata
```

---

## 8. Production Deployment

### Infrastructure Requirements

1. **Key Management**:
   - Secure key storage (HSM/KMS)
   - Access control
   - Audit logging

2. **Repository**:
   - TUF metadata repository
   - Web server or CDN
   - HTTPS required

3. **Monitoring**:
   - Key usage tracking
   - Expiration alerts
   - Failed verification alerts

### Deployment Checklist

- [ ] Generate and securely store root keys
- [ ] Generate role keys (targets, snapshot, timestamp)
- [ ] Initialize TUF repository
- [ ] Generate initial metadata
- [ ] Sign all metadata
- [ ] Upload to repository
- [ ] Configure repository web server
- [ ] Set up monitoring and alerts
- [ ] Document key management procedures
- [ ] Test client integration

---

## 9. Integration Examples

### Use in Wheelhouse Build

```python
from chiron.tuf_metadata import TUFMetadata, create_tuf_repo
from pathlib import Path

# Build wheels
wheelhouse = Path("wheelhouse")
artifacts = list(wheelhouse.glob("*.whl"))

# Create TUF metadata
metadata_files = create_tuf_repo(wheelhouse / "tuf", artifacts)

# Sign metadata (in production)
tuf = TUFMetadata(wheelhouse / "tuf", keys_dir="keys")
for role, filepath in metadata_files.items():
    with open(filepath) as f:
        metadata = json.load(f)

    keyid = get_key_for_role(role)
    signed = tuf.sign_metadata(metadata, role, [keyid])

    with open(filepath, "w") as f:
        json.dump(signed, f, indent=2)
```

---

## 10. Timeline and Priorities

### Phase 1: Key Management (2-3 weeks)

- [ ] Implement key generation
- [ ] Implement key storage
- [ ] Add encryption/decryption
- [ ] Add unit tests

### Phase 2: Signing (2-3 weeks)

- [ ] Implement metadata signing
- [ ] Implement signature verification
- [ ] Add CLI commands
- [ ] Add integration tests

### Phase 3: Production Features (3-4 weeks)

- [ ] Implement key rotation
- [ ] Add delegation support
- [ ] Integrate with CI/CD
- [ ] Add monitoring

### Phase 4: Hardening (2 weeks)

- [ ] Security audit
- [ ] Performance optimization
- [ ] Documentation
- [ ] Production deployment

---

## References

- [TUF Specification](https://theupdateframework.github.io/specification/latest/)
- [TUF Python Reference Implementation](https://github.com/theupdateframework/python-tuf)
- [Sigstore](https://www.sigstore.dev/)
- [PEP 458 – Secure PyPI downloads with signed repository metadata](https://peps.python.org/pep-0458/)

---

## Conclusion

This guide provides a roadmap for completing TUF implementation in Chiron. The foundation is solid; the remaining work focuses on key management and signing infrastructure.

For initial releases, consider using Sigstore for keyless signing to avoid complex key management. Full TUF implementation can be added incrementally.
