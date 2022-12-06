from __future__ import annotations
from typing import List, Dict


class Node:
    def __init__(self) -> None:
        self.name: str = ""
        self.executable: bool = False
        self.redirect: int = None
        self.suggestions: str = None
        self.children: List[Node] = []

    def as_dict(self):
        c = {}
        for child in self.children:
            c[len(c)]=(child.as_dict())
        return {
            "type": None,
            "executable": self.executable,
            "redirect": self.redirect,
            "suggestions": self.suggestions,
            "children": c,
            "name": self.name
        }


class RootCommandNode(Node):
    def as_dict(self):
        c = {}
        for child in self.children:
            c[len(c)]=(child.as_dict())
        return {
            "type": "root",
            "executable": self.executable,
            "redirect": self.redirect,
            "suggestions": self.suggestions,
            "children": c,
            "name": None
        }


class LiteralCommandNode(Node):
    def as_dict(self):
        c = {}
        for child in self.children:
            c[len(c)]=(child.as_dict())
        return {
            "type": "literal",
            "executable": self.executable,
            "redirect": self.redirect,
            "suggestions": self.suggestions,
            "children": c,
            "name": self.name
        }


class ArgumentCommandNode(Node):
    def __init__(self) -> None:
        super().__init__()
        self.parser: str = ""
        self.properties: Dict = {}
        self.suggestions: str = ""

    def as_dict(self):
        c = {}
        for child in self.children:
            c[len(c)]=(child.as_dict())    
        return {
            "type": "argument",
            "executable": self.executable,
            "redirect": self.redirect,
            "suggestions": self.suggestions,
            "children": c,
            "parser": self.parser,
            "properties": self.properties,
            "name": self.name
        }