class InvalidSession(Exception):
    """
    The session is invalid
    Catchall base class
    """

    pass


class InvalidSession_NoSessionCookie(InvalidSession):
    """
    The session is invalid because there is no cookie.
    This is supported by the func_invalid_logger factory callable
    """

    pass


class InvalidSession_Lazycreate(InvalidSession):
    """
    The session is expected to lazycreate.
    This SHOULD NOT be accessed outside of the package.
    If you encounter this, please file a bug report with details of the situation.
    """

    pass


class InvalidSession_NotInBackend(InvalidSession):
    """
    The session is not in the backend.
    This is supported by the func_invalid_logger factory callable
    """

    pass


class InvalidSession_DeserializationError(InvalidSession):
    """
    The session did not deserialize correctly.
    This is only raised/caught/silently handled if `deserialized_fails_new` is True
    This is supported by the func_invalid_logger factory callable
    """

    pass


class InvalidSession_PayloadTimeout(InvalidSession):
    """
    The session is invalid because the loaded payload exceeds a timeout value
    This is supported by the func_invalid_logger factory callable
    """

    pass


class InvalidSession_PayloadLegacy(InvalidSession):
    """
    The session is invalid because it is a legacy format
    This is supported by the func_invalid_logger factory callable
    """

    pass


class RawDeserializationError(Exception):
    """
    Core class for deserialization errors.
    The `message` is the caught exception.
    This allows deserializers to switch with keeping a consistent interface.
    This is only raised if `deserialized_fails_new` is not True
    """

    pass
