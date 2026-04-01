from .castillo import CastilloAdapter
from .cetrogar import CetrogarAdapter
from .fravega import FravegaAdapter
from .megatone import MegatoneAdapter
from .monteshermanos import MontesHermanosAdapter
from .oncity import OncityAdapter

ADAPTERS = [
    CastilloAdapter(),
    CetrogarAdapter(),
    FravegaAdapter(),
    MegatoneAdapter(),
    MontesHermanosAdapter(),
    OncityAdapter(),
    # GarbarinoAdapter(),
]
