from agents.base import build_rehearsal_graph


def build_graph(checkpointer=None):
    return build_rehearsal_graph("investor", checkpointer=checkpointer)


def create_graph():
    return build_graph()