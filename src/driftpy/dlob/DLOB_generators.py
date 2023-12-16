from typing import Dict

def get_node_lists(order_lists):
    from driftpy.dlob.DLOB_node import MarketNodeLists
    order_lists: Dict[str, Dict[int, MarketNodeLists]]

    for _, node_lists in order_lists.get('perp', {}).items():
        yield node_lists.resting_limit['bid']
        yield node_lists.resting_limit['ask']
        yield node_lists.taking_limit['bid']
        yield node_lists.taking_limit['ask']
        yield node_lists.market['bid']
        yield node_lists.market['ask']
        yield node_lists.floating_limit['bid']
        yield node_lists.floating_limit['ask']
        yield node_lists.trigger['above']
        yield node_lists.trigger['below']

    for _, node_lists in order_lists.get('spot', {}).items():
        yield node_lists.resting_limit['bid']
        yield node_lists.resting_limit['ask']
        yield node_lists.taking_limit['bid']
        yield node_lists.taking_limit['ask']
        yield node_lists.market['bid']
        yield node_lists.market['ask']
        yield node_lists.floating_limit['bid']
        yield node_lists.floating_limit['ask']
        yield node_lists.trigger['above']
        yield node_lists.trigger['below']


