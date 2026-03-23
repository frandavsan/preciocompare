from .cetrogar import CetrogarAdapter
from .fravega import FravegaAdapter
from .oncity import OncityAdapter

ADAPTERS = [
    CetrogarAdapter(),
    FravegaAdapter(),
    OncityAdapter(),
    # GarbarinoAdapter(),
]
