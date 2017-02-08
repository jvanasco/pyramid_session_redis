class InvalidSession(Exception):
    """The session is invalid"""
    pass


class TimedOutSession(InvalidSession):
    """The session is invalid"""
    pass


class LegacySession(InvalidSession):
    """The session is invalid"""
    pass
