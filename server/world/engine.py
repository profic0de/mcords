class ClientSideError(Exception):
    def __init__(self, message=""):
        super().__init__(message)

class JoinGameError(Exception):
    def __init__(self, message=""):
        super().__init__(message)