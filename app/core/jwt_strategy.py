import json
from typing import Dict, Any, Optional, TYPE_CHECKING

import jwt
from jwcrypto import jwk
from fastapi_users.authentication.strategy.jwt import JWTStrategy
from fastapi_users import models

from app.core.config import settings

if TYPE_CHECKING:
    pass


class RS256JWTStrategyWithKid(JWTStrategy[models.UP, models.ID]):
    """
    Custom JWT strategy that extends FastAPI Users JWTStrategy to add RS256 with kid header
    """

    def __init__(self, lifetime_seconds: int, key_id: str = "v1"):
        self.key_id = key_id

        self._setup_keys()

        super().__init__(
            secret=self.private_pem,
            lifetime_seconds=lifetime_seconds,
            token_audience=[settings.jwt.application_id],
            algorithm="RS256",
            public_key=self.public_pem,
        )

        self._setup_jwk()

    def _setup_keys(self):
        """Setup RSA key pair for RS256 signing"""
        from pathlib import Path

        key_file = Path("jwt_rsa_key.pem")

        if key_file.exists():
            with open(key_file, "rb") as f:
                key_data = f.read()
            self.rsa_key = jwk.JWK.from_pem(key_data)
        else:
            self.rsa_key = jwk.JWK.generate(kty="RSA", size=2048)
            with open(key_file, "wb") as f:
                f.write(self.rsa_key.export_to_pem(private_key=True, password=None))

        self.private_pem = self.rsa_key.export_to_pem(private_key=True, password=None)
        self.public_pem = self.rsa_key.export_to_pem(private_key=False, password=None)

    def _setup_jwk(self):
        """Setup JWK from public key PEM"""

        self.public_jwk = json.loads(self.rsa_key.export_public())
        self.public_jwk["kid"] = self.key_id

    async def write_token(self, user: models.UP) -> str:
        """Generate JWT token with kid header"""

        import time

        data = {
            "user_id": str(user.id),
            "aud": self.token_audience,
        }

        now = int(time.time())
        data["iat"] = now
        if self.lifetime_seconds:
            data["exp"] = now + self.lifetime_seconds

        if hasattr(user, "email"):
            data["email"] = str(user.email)

        data["sub"] = f"user:{user.id}"
        data["iss"] = settings.jwt.issuer

        headers = {"kid": self.key_id}

        return jwt.encode(
            data,
            self.encode_key,
            algorithm=self.algorithm,
            headers=headers,
        )

    async def read_token(
        self, token: Optional[str], user_manager
    ) -> Optional[models.UP]:
        """Override read_token to fix token validation"""
        if token is None:
            return None

        try:
            payload = jwt.decode(
                token,
                self.decode_key,
                algorithms=[self.algorithm],
                audience=self.token_audience,
            )

            user_id = payload.get("user_id")
            if user_id is None:
                return None

            parsed_user_id = user_manager.parse_id(user_id)
            if parsed_user_id is None:
                return None

            user = await user_manager.get(parsed_user_id)
            return user

        except (jwt.PyJWTError, Exception):
            return None

    def get_jwks(self) -> Dict[str, Any]:
        """Get JWKS for public key distribution"""
        return {"keys": [self.public_jwk]}
