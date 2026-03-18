from ..platforms.vtex import VtexAdapter


class OncityAdapter(VtexAdapter):
    name = "oncity"
    base_url = "https://www.oncity.com"
    verify_ssl = False
