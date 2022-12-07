from __future__ import annotations
from ..protocols.chat import ChatProtocol
from ..protocols import utils
import struct

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from quarry.types.buffer import Buffer1_19_1


class TabCompleteProtocol(ChatProtocol):
    def packet_tab_complete(self, buff: Buffer1_19_1):
        trans_id = buff.unpack_varint()
        msg = buff.unpack_string()

        array = []
        array.append(("msg", False))
        array.append(("123", False))

        output = b""
        for e in array:
            output+=self.buff_type.pack("s?", e[0].encode("utf-8"), e[1])

        self.send_packet(
            "tab_complete",
            self.buff_type.pack_varint(trans_id),
            self.buff_type.pack_varint(3), # Start of the text to replace.
            self.buff_type.pack_varint(3), # Length of the text to replace.
            self.buff_type.pack_varint(len(array)), # Number of elements in the following array.
            self.buff_type.pack_byte_array(output)
        )

