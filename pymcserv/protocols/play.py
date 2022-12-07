from .chat import ChatProtocol
from ..commands.tab_complete import TabCompleteProtocol


class PyMcServProtocol(TabCompleteProtocol):
    def player_joined(self):
        ChatProtocol.player_joined(self)
