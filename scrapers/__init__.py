from .ted import TedScraper
from .mercell import MercellScraper
from .kommers import KommersScraper
from .eavrop import EAvropScraper
from .vinnova import VinnovaScraper
from .tillvaxtverket import TillvaxtverketScraper

ALL_SCRAPERS = [TedScraper, KommersScraper, EAvropScraper, MercellScraper, VinnovaScraper, TillvaxtverketScraper]
