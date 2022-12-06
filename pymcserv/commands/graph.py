from .nodes import *


def getRootCommandNode() -> RootCommandNode :
    testCommand = LiteralCommandNode()
    testCommand.name = "test"
    testCommand.executable = True

    node = RootCommandNode()
    node.children.append(testCommand)
    return node 
