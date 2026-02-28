from .ted import TedScraper
from .mercell import MercellScraper
from .kommers import KommersScraper
from .eavrop import EAvropScraper

# Mercell excluded — requires authentication, TED covers same EU procurements
ALL_SCRAPERS = [TedScraper, KommersScraper, EAvropScraper]
