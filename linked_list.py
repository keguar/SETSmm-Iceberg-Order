
def init(owner):
    owner.head = None
    owner.tail = None


def head(owner):
    return owner.head


def tail(owner):
    return owner.tail


def next(node):
    return node.next_node


def prev(node):
    return node.prev_node


def insert_before(owner, new_node, node):
    new_node.next_node = node
    if node:
        new_node.prev_node = node.prev_node
        node.prev_node = new_node
    else:
        new_node.prev_node = owner.tail
        owner.tail = new_node
    if new_node.prev_node:
        new_node.prev_node.next_node = new_node
    else:
        owner.head = new_node


def set_head(owner, node):
    owner.head = node
    if owner.head:
        owner.head.prev_node = None
    else:
        owner.tail = None
