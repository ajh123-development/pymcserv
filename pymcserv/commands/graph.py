from .nodes import *


def getRootCommandNode() -> RootCommandNode :
    testCommand = LiteralCommandNode()
    testCommand.name = "msg"
    testCommand.executable = True

    testCommandArg1 = ArgumentCommandNode()
    testCommandArg1.name = "position"
    testCommandArg1.executable = True
    testCommandArg1.parser = "brigadier:string"
    testCommandArg1.properties = {"behavior": 1}
    testCommandArg1.suggestions = ""
    testCommand.children.append(testCommandArg1)

    node = RootCommandNode()
    node.children.append(testCommand)
    return node 
