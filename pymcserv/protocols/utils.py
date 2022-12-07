from __future__ import annotations
import string

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from quarry.types.buffer import Buffer1_19_1


def hexdump(buffer: Buffer1_19_1):
    data = buffer.buff[buffer.pos:]
    lines = ['']
    bytes_read = 0
    while len(data) > 0:
        data_line, data = data[:16], data[16:]

        l_hex = []
        l_str = []
        for i, c in enumerate(data_line):
            l_hex.append(f"{c:02x}")
            try:
                c_str = data_line[i:i + 1].decode("ascii")
                l_str.append(c_str if c_str in string.printable else ".")
            except UnicodeDecodeError as ignored:
                l_str.append(".")

        l_hex.extend(['  '] * (16 - len(l_hex)))
        l_hex.insert(8, '')

        lines.append(f"{bytes_read:08x}  {' '.join(l_hex)}  |{''.join(l_str)}|")

        bytes_read += len(data_line)

    return "\n    ".join(lines + [f"{bytes_read:08x}"])