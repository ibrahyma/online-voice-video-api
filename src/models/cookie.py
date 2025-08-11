from pydantic import BaseModel


class Cookie(BaseModel):
    name: str = ""
    hostOnly: bool = False
    value: str = ""
    domain: str = ""
    path: str = "/"
    secure: bool = False
    session: bool = True
    expirationDate: int = 0

class CookiePayload(BaseModel):
    cookies: list[Cookie]
