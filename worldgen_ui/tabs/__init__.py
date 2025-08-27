from collections import namedtuple
from .generate import make_tab as make_generate_tab
from .extract  import make_tab as make_extract_tab
from .scatter  import make_tab as make_scatter_tab

TabHandle = namedtuple("TabHandle", "name frame on_show dispose")
TABS = [make_generate_tab, make_extract_tab, make_scatter_tab]
