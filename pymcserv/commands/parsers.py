import quarry.types.buffer.v1_13_2

# From https://wiki.vg/Command_Data#Parsers
PARSERS = [None for _ in range(0, 47+1)]
PARSERS[0 ] = "brigadier:bool"
PARSERS[1 ] = "brigadier:float"
PARSERS[2 ] = "brigadier:double"
PARSERS[4 ] = "brigadier:long"
PARSERS[5 ] = "brigadier:string"
PARSERS[6 ] = "minecraft:entity"
PARSERS[7 ] = "minecraft:game_profile"
PARSERS[8 ] = "minecraft:block_pos"
PARSERS[9 ] = "minecraft:column_pos"
PARSERS[3 ] = "brigadier:double"
PARSERS[10] = "minecraft:vec3"
PARSERS[11] = "minecraft:vec2"
PARSERS[12] = "minecraft:block_state"
PARSERS[13] = "minecraft:block_predicate"
PARSERS[14] = "minecraft:item_stack"
PARSERS[15] = "minecraft:item_predicate"
PARSERS[16] = "minecraft:color"
PARSERS[17] = "minecraft:component"
PARSERS[18] = "minecraft:message"
PARSERS[19] = "minecraft:nbt"
PARSERS[20] = "minecraft:nbt_tag"
PARSERS[21] = "minecraft:nbt_path"
PARSERS[22] = "minecraft:objective"
PARSERS[23] = "minecraft:objective_criteria"
PARSERS[24] = "minecraft:operation"
PARSERS[25] = "minecraft:operation"
PARSERS[26] = "minecraft:angle"
PARSERS[27] = "minecraft:rotation"
PARSERS[28] = "minecraft:scoreboard_slot"
PARSERS[29] = "minecraft:score_holder"
PARSERS[30] = "minecraft:swizzle"
PARSERS[31] = "minecraft:team"
PARSERS[32] = "minecraft:item_slot"
PARSERS[33] = "minecraft:resource_location"
PARSERS[34] = "minecraft:mob_effect"
PARSERS[35] = "minecraft:function"
PARSERS[36] = "minecraft:entity_anchor"
PARSERS[37] = "minecraft:int_range"
PARSERS[38] = "minecraft:float_range"
PARSERS[39] = "minecraft:item_enchantment"
PARSERS[40] = "minecraft:entity_summon"
PARSERS[41] = "minecraft:dimension"
PARSERS[42] = "minecraft:time"
PARSERS[43] = "minecraft:resource_or_tag"
PARSERS[44] = "minecraft:resource"
PARSERS[45] = None # These don't have a name for some reason?
PARSERS[46] = None # These don't have a name for some reason?
PARSERS[47] = "minecraft:uuid"


# A modified version of the original inside quarry.types.buffer.v1_13_2
def pack_commands(cls: quarry.types.buffer.v1_13_2.Buffer1_13_2, root_node):
    """
    Packs a command graph.
    """

    # Enumerate nodes
    nodes = [root_node]
    idx = 0
    while idx < len(nodes):
        node = nodes[idx]
        children = list(node['children'].values())
        if node['redirect']:
            children.append(node['redirect'])

        for child in children:
            if child not in nodes:
                nodes.append(child)
        idx += 1

    # Pack nodes
    out = cls.pack_varint(len(nodes))
    for node in nodes:
        out += pack_command_node(cls, node, nodes)

    out += cls.pack_varint(nodes.index(root_node))

    return out

# A modified version of the original inside quarry.types.buffer.v1_13_2
def pack_command_node(cls: quarry.types.buffer.v1_13_2.Buffer1_13_2, node, nodes):
    """
    Packs a command node.
    """

    out = b""

    flags = (
        ['root', 'literal', 'argument'].index(node['type']) |
        int(node['executable']) << 2 |
        int(node['redirect'] is not None) << 3 |
        int(node['suggestions'] is not None) << 4)
    out += cls.pack('B', flags)
    out += cls.pack_varint(len(node['children']))

    for child in node['children'].values():
        out += cls.pack_varint(nodes.index(child))

    if node['redirect'] is not None:
        out += cls.pack_varint(nodes.index(node['redirect']))

    if node['name'] is not None:
        out += cls.pack_string(node['name'])

    if node['type'] == 'argument':
        out += cls.pack_varint(PARSERS.index(node['parser']))
        out += pack_command_node_properties(cls, node['parser'], node['properties'])
    if node['suggestions'] is not None:
        out += cls.pack_string(node['suggestions'])

    return out

# A modified version of the original inside quarry.types.buffer.v1_13_2
def pack_command_node_properties(cls: quarry.types.buffer.v1_13_2.Buffer1_13_2, parser, properties):
    """
    Packs the properties of an ``argument`` command node.
    """

    namespace, parser = parser.split(":", 1)
    out = b""

    if namespace == "brigadier":
        if parser == "bool":
            pass
        elif parser == "string":
            out += cls.pack_varint(properties['behavior'])
        elif parser in ("double", "float", "integer"):
            fmt = parser[0]
            flags = (
                int(properties['min'] is not None) |
                int(properties['max'] is not None) << 1)
            out += cls.pack('B', flags)
            if properties['min'] is not None:
                out += cls.pack(fmt, properties['min'])
            if properties['max'] is not None:
                out += cls.pack(fmt, properties['max'])

    elif namespace == "minecraft":
        if parser in ('entity', 'score_holder'):
            out += cls.pack('?', properties['allow_multiple'])

        elif parser == 'range':
            out += cls.pack('?', properties['allow_decimals'])

    return out