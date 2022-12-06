from .chat import ChatProtocol


class PyMcServProtocol(ChatProtocol):
    def player_joined(self):
        ChatProtocol.player_joined(self)
