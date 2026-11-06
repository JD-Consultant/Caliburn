"""Join source layout wrapping without changing Latin word boundaries."""


def join_wrapped_lines(previous: str, following: str) -> str:
    """Keep a separator between Latin words, without adding one around CJK."""
    if not previous:
        return following
    separator = (
        " "
        if previous[-1].isascii()
        and previous[-1].isalnum()
        and following[:1].isascii()
        and following[:1].isalnum()
        else ""
    )
    return previous + separator + following
