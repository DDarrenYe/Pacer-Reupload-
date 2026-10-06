class ParseError(ValueError):
    """Raised when an uploaded file can't be turned into a run.

    The message is shown to the user, so keep it specific and actionable.
    """
