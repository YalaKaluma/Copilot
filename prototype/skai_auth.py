"""Minimal AWS Cognito SRP login used by the SKAI Growth prototype."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74"
    "020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374"
    "FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE"
    "386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598D"
    "A48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED5"
    "29077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E7"
    "72C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718399549"
    "7CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521A"
    "BDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8C"
    "DB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733"
    "EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074"
    "E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
)
G_HEX = "2"
INFO_BITS = b"Caldera Derived Key"


class SkaiAuthError(RuntimeError):
    pass


def tenant_codes_from_token(token: str) -> list[str]:
    """Read allowed Cognito tenant groups without exposing the token."""
    try:
        payload_part = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(payload_part + "==="))
        groups = payload.get("cognito:groups") or []
        return sorted(
            group
            for group in groups
            if isinstance(group, str) and not group.endswith("_admin")
        )
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return []


def _pad_hex(value: str) -> str:
    if len(value) % 2:
        return f"0{value}"
    if value[0] in "89ABCDEFabcdef":
        return f"00{value}"
    return value


def _hex_bytes(value: str) -> bytes:
    return binascii.unhexlify(_pad_hex(value))


def _hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _hex_hash(value: str) -> bytes:
    return _hash(_hex_bytes(value))


def _hkdf(ikm: bytes, salt: bytes) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    first = hmac.new(prk, INFO_BITS + b"\x01", hashlib.sha256).digest()
    return first[:16]


class CognitoSrpAuthenticator:
    def __init__(self, region: str, user_pool_id: str, client_id: str) -> None:
        try:
            self.pool_name = user_pool_id.split("_", 1)[1]
        except IndexError as exc:
            raise SkaiAuthError("The Cognito User Pool ID is not valid.") from exc
        self.client_id = client_id
        self.client = boto3.client("cognito-idp", region_name=region)
        self.n = int(N_HEX, 16)
        self.g = int(G_HEX, 16)
        self.k = int.from_bytes(
            _hex_hash(_pad_hex(N_HEX) + _pad_hex(G_HEX)), "big"
        )

    def authenticate(self, username: str, password: str) -> str:
        a = int.from_bytes(os.urandom(128), "big") % self.n
        while a == 0:
            a = int.from_bytes(os.urandom(128), "big") % self.n
        a_pub = pow(self.g, a, self.n)

        try:
            initial = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_SRP_AUTH",
                AuthParameters={"USERNAME": username, "SRP_A": _pad_hex(format(a_pub, "x"))},
            )
            if initial.get("ChallengeName") != "PASSWORD_VERIFIER":
                raise SkaiAuthError(
                    f"Unsupported Cognito challenge: {initial.get('ChallengeName')}"
                )
            params = initial.get("ChallengeParameters", {})
            srp_username = params.get("USER_ID_FOR_SRP") or username
            salt_hex = params["SALT"]
            b_hex = params["SRP_B"]
            secret_block = params["SECRET_BLOCK"]

            b_value = int(b_hex, 16)
            u_value = int.from_bytes(
                _hex_hash(_pad_hex(format(a_pub, "x")) + _pad_hex(b_hex)), "big"
            )
            user_hash = _hash(
                f"{self.pool_name}{srp_username}:{password}".encode()
            )
            x_value = int.from_bytes(
                _hash(_hex_bytes(salt_hex) + user_hash), "big"
            )
            shared = pow(
                (b_value - self.k * pow(self.g, x_value, self.n)) % self.n,
                a + u_value * x_value,
                self.n,
            )
            key = _hkdf(
                _hex_bytes(format(shared, "x")), _hex_bytes(format(u_value, "x"))
            )
            now = datetime.now(UTC)
            timestamp = f"{now:%a} {now:%b} {now.day} {now:%H:%M:%S} UTC {now:%Y}"
            message = (
                f"{self.pool_name}{srp_username}".encode()
                + base64.b64decode(secret_block)
                + timestamp.encode()
            )
            signature = base64.b64encode(
                hmac.new(key, message, hashlib.sha256).digest()
            ).decode()
            verified = self.client.respond_to_auth_challenge(
                ClientId=self.client_id,
                ChallengeName="PASSWORD_VERIFIER",
                ChallengeResponses={
                    "USERNAME": srp_username,
                    "PASSWORD_CLAIM_SECRET_BLOCK": secret_block,
                    "TIMESTAMP": timestamp,
                    "PASSWORD_CLAIM_SIGNATURE": signature,
                },
            )
        except ClientError as exc:
            error = exc.response.get("Error", {})
            code = str(error.get("Code", ""))
            message = str(error.get("Message", "Authentication failed"))
            normalized = message.lower()
            if code == "NotAuthorizedException":
                if "incorrect username or password" in normalized:
                    raise SkaiAuthError("Incorrect SKAI username or password.") from exc
                if "secret hash" in normalized:
                    raise SkaiAuthError(
                        "The configured Cognito app client requires a client secret. "
                        "Ask the platform owner for a public app client that supports "
                        "USER_SRP_AUTH, or for the associated client secret."
                    ) from exc
                raise SkaiAuthError(
                    "Cognito rejected the login, but did not identify the username or "
                    f"password as incorrect. Cognito response: {message}"
                ) from exc
            if code == "UserNotFoundException":
                raise SkaiAuthError(
                    "This username was not found in the configured Cognito user pool. "
                    "Check that the pool belongs to the same SKAI environment."
                ) from exc
            if code in {"ResourceNotFoundException", "InvalidParameterException"}:
                raise SkaiAuthError(
                    "The Cognito region, User Pool ID, or Client ID appears incorrect. "
                    f"Cognito response: {message}"
                ) from exc
            raise SkaiAuthError(
                f"SKAI Cognito login failed ({code or 'unknown error'}): {message}"
            ) from exc
        except KeyError as exc:
            raise SkaiAuthError("Cognito returned an incomplete login challenge.") from exc

        result = verified.get("AuthenticationResult") or {}
        token = result.get("IdToken")
        if not token:
            raise SkaiAuthError("Cognito did not return a SKAI ID token.")
        return token
