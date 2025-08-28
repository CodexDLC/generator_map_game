from collections import namedtuple
from .generate import make_tab as make_generate_tab
from .grid import make_tab as make_grid_tab

TabHandle = namedtuple("TabHandle", "name frame on_show dispose")
TABS = [make_generate_tab, make_grid_tab]