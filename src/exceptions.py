# Upload Assistant © 2025 Audionut & wastaken7 — Licensed under UAPL v1.0
class LoginException(Exception):
    def __init__(self, *args, **kwargs):
        default_message = 'An error occured while logging in'
        # if any arguments are passed...
        # If you inherit from the exception that takes message as a keyword
        # maybe you will need to check kwargs here
        if args:
            # ... pass them to the super constructor
            super().__init__(*args, **kwargs)
        else:  # else, the exception was raised without arguments ...
            # ... pass the default message to the super constructor
            super().__init__(default_message, **kwargs)


class UploadException(Exception):
    def __init__(self, *args, **kwargs):
        default_message = 'An error occured while uploading'
        # if any arguments are passed...
        # If you inherit from the exception that takes message as a keyword
        # maybe you will need to check kwargs here
        if args:
            # ... pass them to the super constructor
            super().__init__(*args, **kwargs)
        else:  # else, the exception was raised without arguments ...
            # ... pass the default message to the super constructor
            super().__init__(default_message, **kwargs)


class XEMNotFound(Exception):
    pass


class WeirdSystem(Exception):
    pass


class ManualDateException(Exception):
    pass
