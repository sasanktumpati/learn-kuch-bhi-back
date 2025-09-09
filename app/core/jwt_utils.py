import json
import time
from typing import Dict, Any
import jwt
from jwcrypto import jwk


class JWTManager:
    def __init__(
        self, issuer: str, application_id: str, token_lifetime_seconds: int = 3600
    ):
        self.issuer = issuer
        self.application_id = application_id
        self.token_lifetime_seconds = token_lifetime_seconds
        self.key_id = "v1"

        # Initialize RSA key pair
        self._setup_keys()

    def _setup_keys(self):
        # For demo: generate an in-memory RSA keypair
        # In production: load from secure storage
        self.rsa_key = jwk.JWK.generate(kty="RSA", size=2048)

        # Export public key as JWK with kid
        self.public_jwk = json.loads(self.rsa_key.export_public())
        self.public_jwk["kid"] = self.key_id

        # Export PEM format for PyJWT
        self.private_pem = self.rsa_key.export_to_pem(private_key=True, password=None)
        self.public_pem = self.rsa_key.export_to_pem(private_key=False, password=None)

    def generate_token(self, user_data: Dict[str, Any]) -> str:
        """Generate a JWT token for the user"""
        now = int(time.time())

        payload = {
            "iss": self.issuer,
            "aud": self.application_id,
            "sub": user_data["sub"],
            "email": user_data.get("email"),
            "name": user_data.get("name"),
            "iat": now,
            "exp": now + self.token_lifetime_seconds,
        }

        # Add additional claims from user_data if present
        for key, value in user_data.items():
            if key not in ["sub", "email", "name"] and value is not None:
                payload[key] = value

        # Include kid in header
        headers = {"kid": self.key_id}

        token = jwt.encode(
            payload, self.private_pem, algorithm="RS256", headers=headers
        )
        return token

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token"""
        try:
            decoded = jwt.decode(
                token,
                self.public_pem,
                algorithms=["RS256"],
                audience=self.application_id,
                issuer=self.issuer,
            )
            return decoded
        except jwt.PyJWTError as e:
            raise ValueError(f"Invalid token: {e}")

    def get_jwks(self) -> Dict[str, Any]:
        """Get JWKS (JSON Web Key Set) for public key distribution"""
        return {"keys": [self.public_jwk]}


# Initialize JWT manager using settings
from app.core.config import settings

jwt_manager = JWTManager(
    issuer=settings.jwt.issuer,
    application_id=settings.jwt.application_id,
    token_lifetime_seconds=settings.jwt.token_lifetime_seconds,
)
