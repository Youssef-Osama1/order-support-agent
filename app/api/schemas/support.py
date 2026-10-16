from typing import Annotated

from pydantic import BaseModel, StringConstraints

CustomerMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000)
]
CustomerEmail = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        max_length=254,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


class ChatRequest(BaseModel):
    message: CustomerMessage
    customer_email: CustomerEmail
