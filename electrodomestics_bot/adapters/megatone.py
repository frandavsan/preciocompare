from ..platforms.megatone import MegatoneAdapter as _MegatonePlatform


class MegatoneAdapter(_MegatonePlatform):
    name = "megatone"
    base_url = "https://www.megatone.net"
    _doofinder_hashid = "7d78864dfd68192d967ce98f7af00970"
