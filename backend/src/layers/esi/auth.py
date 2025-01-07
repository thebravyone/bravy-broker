import os

import requests
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

EVE_CLIENT_ID = os.getenv("EVE_CLIENT_ID")
EVE_SECRET_KEY = os.getenv("EVE_SECRET_KEY")

SSO_METADATA_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server/"


class ESIAuth:
    """
    A class to handle EVE Online SSO authentication.

    Attributes:
        `refresh_token` (str): The refresh token used to obtain access tokens.
        `metadata` (dict): Metadata obtained from the SSO metadata URL.
        `jwks_cache` (list): Cached JSON Web Key Set (JWKS) for token validation.

    Methods:
        `get_access_token()`:
            Exchanges the refresh token for an access token and validates it.
            Returns a dictionary containing the access token and its expiration time.
    """

    def __init__(self, refresh_token: str):
        self.refresh_token = refresh_token
        self.metadata = self.__get_metadata()
        self.jwks = self.__get_jwks()

    def get_access_token(self):

        try:
            token_endpoint: str = self.metadata.get("token_endpoint")
        except KeyError:
            raise MetadataError("token_endpoint not found in metadata")

        auth = HTTPBasicAuth(EVE_CLIENT_ID, EVE_SECRET_KEY)

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "login.eveonline.com",
        }

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
        }

        try:
            response = requests.post(
                token_endpoint,
                auth=auth,
                headers=headers,
                data=data,
            )
            response.raise_for_status()
            access_token = response.json()
            jwt_content = self.__validate_access_token(access_token.get("access_token"))
            return {
                "access_token": access_token.get("access_token"),
                "expiration_unix": jwt_content.get("exp"),
            }
        except HTTPError as e:
            raise Exception(f"Failed to exchange refresh token: {e}")

    def __get_metadata(self):
        try:
            response = requests.get(SSO_METADATA_URL)
            response.raise_for_status()
            return response.json()
        except HTTPError as e:
            raise Exception(f"Failed to retrieve metadata: {e}")

    def __get_jwks(self):

        try:
            jwks_uri: str = self.metadata.get("jwks_uri")
        except KeyError:
            raise MetadataError("jwks_uri not found in metadata")

        try:
            response = requests.get(jwks_uri)
            response.raise_for_status()
            data = response.json()
        except HTTPError as e:
            raise Exception(f"Failed to retrieve jwks: {e}")

        jwks = data.get("keys")
        if jwks is None:
            raise KeyError(f"Invalid data received from the the jwks endpoint: {data}")

        return jwks

    def __validate_access_token(self, access_token: str):
        ALGORITHM = "RS256"
        AUDIENCE = "EVE Online"
        ISSUERS = ("login.eveonline.com", "https://login.eveonline.com")

        jwks = self.__get_jwks()

        jwk = next((item for item in jwks if item.get("alg") == ALGORITHM), None)

        if jwk is None:
            raise Exception(f"No JWK found with algorithm {ALGORITHM}")

        try:
            contents = jwt.decode(
                token=access_token,
                key=jwk,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                issuer=ISSUERS,
            )
            return contents
        except ExpiredSignatureError:
            raise Exception("The access token has expired")
        except JWTError as e:
            raise Exception(f"Failed to decode access token: {e}")


class MetadataError(Exception):
    """Exception raised for errors in the metadata."""

    pass
