from ..platforms.vtex import VtexAdapter


class CetrogarAdapter(VtexAdapter):
    name = "cetrogar"
    base_url = "https://www.cetrogar.com.ar"
    _free_shipping_override = False  # Cetrogar charges for home delivery; skip simulation
