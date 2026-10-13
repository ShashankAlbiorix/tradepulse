from typing import List, Dict
from pydantic import BaseModel


class TrackedEntity(BaseModel):
    """
    Represents a company or ticker tracked by the news sentiment agent.
    """
    symbol: str
    name: str
    sector: str
    aliases: List[str]
    keywords: List[str]


TRACKED_ENTITIES: List[TrackedEntity] = [
    TrackedEntity(
        symbol="RELIANCE",
        name="Reliance Industries Ltd",
        sector="Energy & Retail",
        aliases=["Reliance", "RIL", "Jio", "Reliance Retail", "Reliance Jio"],
        keywords=["Mukesh Ambani", "O2C", "telecom subscriber", "petrochemical"]
    ),
    TrackedEntity(
        symbol="TCS",
        name="Tata Consultancy Services Ltd",
        sector="IT Services",
        aliases=["TCS", "Tata Consultancy"],
        keywords=["deal wins", "constant currency", "BFSI", "operating margin"]
    ),
    TrackedEntity(
        symbol="HDFCBANK",
        name="HDFC Bank Ltd",
        sector="Banking & Finance",
        aliases=["HDFC Bank", "HDFC"],
        keywords=["net interest margin", "NIM", "gross NPA", "deposit growth", "loan growth"]
    ),
    TrackedEntity(
        symbol="INFY",
        name="Infosys Ltd",
        sector="IT Services",
        aliases=["Infosys"],
        keywords=["guidance", "large deals", "Salil Parekh", "digital revenue"]
    ),
    TrackedEntity(
        symbol="ICICIBANK",
        name="ICICI Bank Ltd",
        sector="Banking & Finance",
        aliases=["ICICI Bank", "ICICI"],
        keywords=["asset quality", "CASA ratio", "provisions", "net profit"]
    ),
    TrackedEntity(
        symbol="TATAMOTORS",
        name="Tata Motors Ltd",
        sector="Automobile",
        aliases=["Tata Motors", "TaMo", "JLR", "Jaguar Land Rover"],
        keywords=["EV sales", "commercial vehicles", "passenger vehicles", "JLR margins"]
    ),
    TrackedEntity(
        symbol="SBIN",
        name="State Bank of India",
        sector="Public Sector Bank",
        aliases=["SBI", "State Bank of India", "State Bank"],
        keywords=["credit growth", "NPA recovery", "treasury income"]
    ),
    TrackedEntity(
        symbol="BHARTIARTL",
        name="Bharti Airtel Ltd",
        sector="Telecom",
        aliases=["Airtel", "Bharti Airtel"],
        keywords=["ARPU", "5G expansion", "mobile data", "tariff hike"]
    ),
    TrackedEntity(
        symbol="LT",
        name="Larsen & Toubro Ltd",
        sector="Infrastructure & Engineering",
        aliases=["Larsen & Toubro", "L&T", "Larsen"],
        keywords=["order inflow", "infrastructure", "hydrocarbon", "defense order"]
    ),
    TrackedEntity(
        symbol="MPHASIS",
        name="Mphasis Ltd",
        sector="IT Services",
        aliases=["Mphasis"],
        keywords=["direct channel", "cloud migration", "partnership", "Scotland"]
    ),
    TrackedEntity(
        symbol="ITC",
        name="ITC Ltd",
        sector="FMCG & Hotels",
        aliases=["ITC"],
        keywords=["cigarette volume", "hotel demerger", "agri business", "FMCG margins"]
    ),
    TrackedEntity(
        symbol="ADANIENT",
        name="Adani Enterprises Ltd",
        sector="Diversified Conglomerate",
        aliases=["Adani", "Adani Enterprises", "Gautam Adani"],
        keywords=["airports", "green hydrogen", "capex", "mining"]
    )
]

TICKER_MAP: Dict[str, TrackedEntity] = {e.symbol: e for e in TRACKED_ENTITIES}
