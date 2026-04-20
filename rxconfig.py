from reflex.config import Config
from reflex.plugins.sitemap import SitemapPlugin

config = Config(
    app_name='ams_han_reflex_app',
    disable_plugins=[SitemapPlugin],
)
