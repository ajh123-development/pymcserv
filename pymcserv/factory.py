from typing import List

from quarry.net.server import ServerFactory
from quarry.types.chat import SignedMessage, LastSeenMessage
from quarry.types.uuid import UUID
from quarry.data.data_packs import data_packs, dimension_types

from pymcserv.protocol import *


class ChatRoomFactory(ServerFactory):
    protocol = ChatRoomProtocol
    motd = "Chat Room Server"

    def send_join_game(self, player):
        # Build up fields for "Join Game" packet
        entity_id = 0
        max_players = 0
        hashed_seed = 42
        view_distance = 2
        simulation_distance = 2
        game_mode = 3
        prev_game_mode = 3
        is_hardcore = False
        is_respawn_screen = True
        is_reduced_debug = False
        is_debug = False
        is_flat = False

        dimension_codec = data_packs[player.protocol_version]
        dimension_name = "minecraft:overworld"
        dimension_tag = dimension_types[player.protocol_version, dimension_name]
        world_count = 1
        world_name = "chat"

        join_game = [
            player.buff_type.pack("i?Bb", entity_id, is_hardcore, game_mode, prev_game_mode),
            player.buff_type.pack_varint(world_count),
            player.buff_type.pack_string(world_name),
            player.buff_type.pack_nbt(dimension_codec),
        ]

        if player.protocol_version >= 759:  # 1.19+ needs just dimension name, <1.19 needs entire dimension nbt
            join_game.append(player.buff_type.pack_string(dimension_name))
        else:
            join_game.append(player.buff_type.pack_nbt(dimension_tag))

        join_game.append(player.buff_type.pack_string(world_name))
        join_game.append(player.buff_type.pack("q", hashed_seed))
        join_game.append(player.buff_type.pack_varint(max_players))
        join_game.append(player.buff_type.pack_varint(view_distance)),

        if player.protocol_version >= 757:  # 1.18
            join_game.append(player.buff_type.pack_varint(simulation_distance))

        join_game.append(player.buff_type.pack("????", is_reduced_debug, is_respawn_screen, is_debug, is_flat))

        if player.protocol_version >= 759:  # 1.19
            join_game.append(player.buff_type.pack("?", False))

        # Send "Join Game" packet
        player.send_packet("join_game", *join_game)

    # Sends a signed chat message to supporting clients
    def broadcast_signed_chat(self, message: SignedMessage, sender_name):
        for player in self.players:
            if player.protocol_mode != 'play':
                continue

            # Only send signed messages to clients that support the same signing method
            if message.signature_version == player.protocol_version:
                self.send_signed_chat(player, message, sender_name)
            else:
                self.send_unsigned_chat(player, message.body.message, message.header.sender, sender_name)

    def send_signed_chat(self, player: ChatRoomProtocol, message: SignedMessage, sender_name):
        # Add to player's pending messages for later last seen validation
        if self.online_mode:
            player.pending_messages.append(LastSeenMessage(message.header.sender, message.signature))

        if player.protocol_version >= 760:
            player.send_packet("chat_message",
                               player.buff_type.pack_signed_message(message),
                               player.buff_type.pack_varint(0),  # Chat filtering result, 0 = not filtered
                               player.buff_type.pack_varint(0),  # Message type
                               player.buff_type.pack_chat(sender_name),  # Sender display name
                               player.buff_type.pack('?', False))  # No team name

        # 1.19 packet format is different
        else:
            player.send_packet("chat_message",
                               player.buff_type.pack_chat(message.body.message),  # Original message
                               # Optional decorated message
                               player.buff_type.pack_optional(player.buff_type.pack_chat,
                                                              message.body.decorated_message),
                               player.buff_type.pack_varint(0),  # Message type, 0 = chat
                               player.buff_type.pack_uuid(message.header.sender),  # Sender UUID
                               player.buff_type.pack_chat(sender_name),  # Sender display name
                               player.buff_type.pack('?', False),  # Optional team name
                               # Timestamp, salt
                               player.buff_type.pack('QQ', message.body.timestamp, message.body.salt),
                               player.buff_type.pack_byte_array(message.signature or b''))  # Signature

    # Sends an unsigned chat message, using system messages on supporting clients
    def broadcast_unsigned_chat(self, message: str, sender: UUID, sender_name: str):
        for player in self.players:
            if player.protocol_mode != 'play':
                continue

            self.send_unsigned_chat(player, message, sender, sender_name)

    def send_unsigned_chat(self, player: ChatRoomProtocol, message: str, sender: UUID, sender_name: str):
        # 1.19+ Send as system message to avoid client signature warnings
        if player.protocol_version >= 759:
            self.send_system(player, "<%s> %s" % (sender_name, message))
        else:  # Send regular chat message
            player.send_packet("chat_message",
                               player.buff_type.pack_chat("<%s> %s" % (sender_name, message)),
                               player.buff_type.pack('B', 0),
                               player.buff_type.pack_uuid(sender))

    # Sends a system message, falling back to chat messages on older clients
    def broadcast_system(self, message: str):
        for player in self.players:
            if player.protocol_mode != 'play':
                continue

            self.send_system(player, message)

    @staticmethod
    def send_system(player: ChatRoomProtocol, message: str):
        if player.protocol_version >= 760:  # 1.19.1+
            player.send_packet("system_message",
                               player.buff_type.pack_chat(message),
                               player.buff_type.pack('?', False))  # Overlay, false = display in chat
        elif player.protocol_version == 759:  # 1.19
            player.send_packet("system_message",
                               player.buff_type.pack_chat(message),
                               player.buff_type.pack_varint(1))
        else:
            player.send_packet("chat_message",
                               player.buff_type.pack_chat(message),
                               player.buff_type.pack('B', 0),
                               player.buff_type.pack_uuid(UUID(int=0)))

    # Announces player join
    def broadcast_player_join(self, joined: ChatRoomProtocol):
        self.broadcast_system("\u00a7e%s has joined." % joined.display_name)
        self.broadcast_player_list_add(joined)

    # Announces player leave
    def broadcast_player_leave(self, left: ChatRoomProtocol):
        self.broadcast_system("\u00a7e%s has left." % left.display_name)
        self.broadcast_player_list_remove(left)

    # Sends player list entry for new player to other players
    def broadcast_player_list_add(self, added: ChatRoomProtocol):
        for player in self.players:
            # Exclude the added player, they will be sent the full player list separately
            if player.protocol_mode == 'play' and player != added:
                self.send_player_list_add(player, [added])

    @staticmethod
    def send_player_list_add(player: ChatRoomProtocol, added: List[ChatRoomProtocol]):
        data = [
            player.buff_type.pack_varint(0),  # Action - 0 = Player add
            player.buff_type.pack_varint(len(added)),  # Player entry count
        ]

        for entry in added:
            if entry.protocol_mode != 'play':
                continue

            data.append(player.buff_type.pack_uuid(entry.uuid))  # Player UUID
            data.append(player.buff_type.pack_string(entry.display_name))  # Player name
            data.append(player.buff_type.pack_varint(0))  # Empty properties list
            data.append(player.buff_type.pack_varint(3))  # Gamemode
            data.append(player.buff_type.pack_varint(0))  # Latency
            data.append(player.buff_type.pack('?', False))  # No display name

            # Add signature for 1.19+ clients if it exists
            if player.protocol_version >= 759:
                data.append(player.buff_type.pack_optional(player.buff_type.pack_player_public_key, entry.public_key_data))

        player.send_packet('player_list_item', *data)

    # Sends player list update for leaving player to other players
    def broadcast_player_list_remove(self, removed: ChatRoomProtocol):
        for player in self.players:
            if player.protocol_mode == 'play' and player != removed:
                player.send_packet('player_list_item',
                                   player.buff_type.pack_varint(4),  # Action - 4 = Player remove
                                   player.buff_type.pack_varint(1),  # Player entry count
                                   player.buff_type.pack_uuid(removed.uuid))  # Player UUID