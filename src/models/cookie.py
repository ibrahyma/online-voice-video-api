from pydantic import BaseModel


class Cookie(BaseModel):
    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    expirationDate: float = 0

class CookiePayload(BaseModel):
    cookies: list[Cookie]
