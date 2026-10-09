"""Generate an internal CA chain and a RouterOS HTTPS certificate for an IP."""

from __future__ import annotations

import argparse
import base64
import ipaddress
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def _name(common_name: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Bonso Internal PKI"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])


def _write(path: Path, data: bytes) -> None:
    path.write_bytes(data)


def _certificate_pem(certificate: x509.Certificate) -> bytes:
    return certificate.public_bytes(serialization.Encoding.PEM)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ip", required=True, help="Public IP of the RouterOS REST service")
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    router_ip = ipaddress.ip_address(args.ip)
    output_dir: Path = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    now = datetime.now(timezone.utc)
    key_password = secrets.token_urlsafe(32).encode("utf-8")

    root_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    root_subject = _name("Bonso MikroTik Root CA")
    root_cert = (
        x509.CertificateBuilder()
        .subject_name(root_subject).issuer_name(root_subject).public_key(root_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=1), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .sign(root_key, hashes.SHA256())
    )

    intermediate_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    intermediate_subject = _name("Bonso MikroTik Intermediate CA")
    intermediate_cert = (
        x509.CertificateBuilder()
        .subject_name(intermediate_subject).issuer_name(root_cert.subject).public_key(intermediate_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=1825))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .sign(root_key, hashes.SHA256())
    )

    router_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    router_cert = (
        x509.CertificateBuilder()
        .subject_name(_name(f"MikroTik {router_ip}")).issuer_name(intermediate_cert.subject)
        .public_key(router_key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(router_ip)]), critical=False)
        .sign(intermediate_key, hashes.SHA256())
    )

    encrypted = serialization.BestAvailableEncryption(key_password)
    _write(output_dir / "root-ca.crt.pem", _certificate_pem(root_cert))
    _write(output_dir / "root-ca.key.pem", root_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encrypted))
    _write(output_dir / "intermediate-ca.crt.pem", _certificate_pem(intermediate_cert))
    _write(output_dir / "intermediate-ca.key.pem", intermediate_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encrypted))
    _write(output_dir / "mikrotik-router.crt.pem", _certificate_pem(router_cert))
    _write(output_dir / "mikrotik-router.key.pem", router_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    router_fullchain = _certificate_pem(router_cert) + _certificate_pem(intermediate_cert)
    railway_chain = _certificate_pem(root_cert) + _certificate_pem(intermediate_cert)
    _write(output_dir / "mikrotik-router-fullchain.pem", router_fullchain)
    _write(output_dir / "railway-ca-chain.pem", railway_chain)
    _write(output_dir / "railway-ca-chain.b64", base64.b64encode(railway_chain))
    _write(output_dir / "ca-key-password.txt", key_password + b"\n")

    readme = f"""MikroTik internal TLS material for {router_ip}

Generated: {now.isoformat()}
Router certificate expiry: {(now + timedelta(days=825)).date().isoformat()}

Import into RouterOS:
  - mikrotik-router.crt.pem
  - mikrotik-router.key.pem
  - intermediate-ca.crt.pem
Assign the imported router certificate to /ip/service www-ssl.

Railway API Secret:
  MIKROTIK_CA_CERT_PEM_B64 = contents of railway-ca-chain.b64

Security:
  - root-ca.key.pem and intermediate-ca.key.pem are protected by ca-key-password.txt.
  - mikrotik-router.key.pem is unencrypted solely for RouterOS import; protect it
    and delete local copies after a verified import.
  - The server certificate has IP SAN {router_ip}; connecting by this IP is valid.
"""
    _write(output_dir / "README.txt", readme.encode("utf-8"))
    print(output_dir)


if __name__ == "__main__":
    main()
