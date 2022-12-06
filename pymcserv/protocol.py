from typing import List
import sys

from quarry.net.server import ServerProtocol
from quarry.types.chat import SignedMessage, SignedMessageHeader, SignedMessageBody, Message, LastSeenMessage


class ChatRoomProtocol(ServerProtocol):
    previous_timestamp = 0  # Timestamp of last chat message sent by the client, used for out-of-order chat checking
    previous_signature = None  # Signature of the last chat message sent by the client, used as part of the next message's signature
    pending_messages = []  # Chat messages pending acknowledgement by the client
    previously_seen = []  # Chat messages acknowledged by the client in the last chat message

    def player_joined(self):
        # Call super. This switches us to "play" mode, marks the player as
        #   in-game, and does some logging.
        ServerProtocol.player_joined(self)

        # Send server data packet on 1.19+
        if self.protocol_version >= 760:
            self.send_packet('server_data',
                             self.buff_type.pack('????',
                                                 False,                      # Optional description
                                                 False,                      # Optional favicon
                                                 False,                      # Disable chat previews
                                                 self.factory.online_mode))  # Enforce chat signing when in online mode
        elif self.protocol_version == 759:  # 1.19 lacks enforce chat signing field
            self.send_packet('server_data', self.buff_type.pack('???', False, False, False))

        # Send join game packet
        self.factory.send_join_game(self)

        # Send "Player Position and Look" packet
        self.send_packet(
            "player_position_and_look",
            self.buff_type.pack("dddff?",
                0,                         # x
                500,                       # y  Must be >= build height to pass the "Loading Terrain" screen on 1.18.2
                0,                         # z
                0,                         # yaw
                0,                         # pitch
                0b00000),                  # flags
            self.buff_type.pack_varint(0),  # teleport id
            self.buff_type.pack("?", True))  # Leave vehicle,

        # Start sending "Keep Alive" packets
        self.ticker.add_loop(20, self.update_keep_alive)

        # Announce player join to other players
        self.factory.broadcast_player_join(self)

        # Send full player list
        self.factory.send_player_list_add(self, self.factory.players)

    def player_left(self):
        ServerProtocol.player_left(self)

        # Announce player leave to other players
        self.factory.broadcast_player_leave(self)

    def update_keep_alive(self):
        # Send a "Keep Alive" packet
        self.send_packet("keep_alive", self.buff_type.pack('Q', 0))

    def packet_chat_message(self, buff):
        if self.protocol_mode != 'play':
            return

        message = buff.unpack_string()

        # 1.19+, messages may be signed
        if self.protocol_version >= 759:
            timestamp = buff.unpack('Q')
            salt = buff.unpack('Q')
            signature = buff.unpack_byte_array()
            signature_version = 760 if self.protocol_version >= 760 else 759  # 1.19.1 signature format is different
            buff.unpack('?')  # Whether preview was accepted, not implemented here
            last_seen = []
            last_received = None

            # Ignore signature if player has no key (i.e offline mode)
            if self.public_key_data is None:
                signature = None
            else:
                # 1.19.1+ includes list of "last seen" messages
                if self.protocol_version >= 760:
                    last_seen = buff.unpack_last_seen_list()  # List of previously sent messages acknowledged by the client
                    last_received = buff.unpack_optional(buff.pack_last_seen_entry)  # Optional "last received" message

            header = SignedMessageHeader(self.uuid, self.previous_signature)
            body = SignedMessageBody(message, timestamp, salt, None, last_seen)
            signed_message = SignedMessage(header, signature, signature_version, body)

            # Validate the message
            if self.validate_signed_message(signed_message, last_received) is False:
                buff.discard()
                return

            # Update previous message data from current message
            self.previous_timestamp = signed_message.body.timestamp
            self.previous_signature = signed_message.signature
            self.previously_seen = signed_message.body.last_seen

            self.factory.broadcast_signed_chat(signed_message, self.display_name)
        else:
            self.factory.broadcast_unsigned_chat(message, self.uuid, self.display_name)

        buff.discard()

    def validate_signed_message(self, message: SignedMessage, last_received: LastSeenMessage = None):
        # Kick player if this message is older than the previous one
        if message.body.timestamp < self.previous_timestamp:
            self.logger.warning("{} sent out-of-order chat: {}".format(self.display_name, message.body.message))
            self.close(Message({'translate': 'multiplayer.disconnect.out_of_order_chat'}))
            return False

        if self.validate_last_seen(message.body.last_seen, last_received) is False:
            return False

        # Kick player if we cannot verify the message signature
        if self.public_key_data is not None and message.verify(self.public_key_data.key) is False:
            self.close(Message({'translate': 'multiplayer.disconnect.unsigned_chat'}))
            return False

    # Validate the last seen list (and optional last received message)
    # The last seen list is a list of the latest messages sent by other players, one per player
    def validate_last_seen(self, last_seen: List[LastSeenMessage], last_received: LastSeenMessage = None):
        errors = []
        profiles = []

        # The last seen list should never be shorter than the previous one
        if len(last_seen) < len(self.previously_seen):
            errors.append('Previously present messages removed from context')

        # Get indices of last seen messages to validate ordering
        indices = self.calculate_indices(last_seen, last_received)
        previous_index = -sys.maxsize - 1

        # Loop over indices to see if the message order is correct
        for index in indices:
            if index == -sys.maxsize - 1:  # Message wasn't in previously_seen or pending_messages lists
                errors.append('Unknown message')
            elif index < previous_index:  # Message is earlier than previous message
                errors.append('Messages received out of order')
            else:
                previous_index = index

        # Remove seen messages (and any older ones from the same players) from the pending list
        if previous_index >= 0:
            self.pending_messages = self.pending_messages[previous_index + 1::]

        # All last seen entries should be from different players
        for entry in last_seen:
            if entry.sender in profiles:
                errors.append('Multiple entries for single profile')
                break

            profiles.append(entry.sender)

        # Kick player if any validation fails
        if len(errors):
            self.logger.warning("Failed to validate message from {}, reasons: {}"
                                .format(self.display_name, ', '.join(errors)))
            self.close(Message({'translate': 'multiplayer.disconnect.chat_validation_failed'}))
            return False

        return True

    # Returns an array containing the positions of each of the given last_seen messages
    # (and the optional last_received message) in the previously_seen and pending_messages lists
    # A valid last_seen list should contain messages ordered oldest to newest, meaning the resulting array should
    # contain indices in ascending order
    def calculate_indices(self, last_seen: List[LastSeenMessage], last_received: LastSeenMessage = None):
        indices = [-sys.maxsize - 1] * len(last_seen)  # Populate starting lists with min value, indicating a message wasn't found

        # Get indices of any last seen messages which are in the previously seen list
        for index, value in enumerate(self.previously_seen):
            try:
                position = last_seen.index(value)
                indices[position] = -index - 1  # Negate previously seen entries to order them "before" pending entries
            except ValueError:  # Not in list
                continue

        # Get indices of any last seen messages which are in the pending messages list
        for index, value in enumerate(self.pending_messages):
            try:
                position = last_seen.index(value)
                indices[position] = index
            except ValueError:  # Not in list
                continue

        # List will be in descending order here, reverse it
        indices.reverse()

        # Get index of last received message if present
        if last_received is not None:
            try:
                indices.append(self.pending_messages.index(last_received))
            except ValueError:
                indices.append(-sys.maxsize - 1)
                pass

        return indices