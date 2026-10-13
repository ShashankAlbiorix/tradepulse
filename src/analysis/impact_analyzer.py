from typing import Dict, Any, List
from src.models.schemas import NewsArticle


class ImpactAnalyzer:
    """
    Evaluates news catalyst category, urgency, and estimated short-term market impact.
    """

    CATALYST_KEYWORDS: Dict[str, List[str]] = {
        "EARNINGS": ["quarterly profit", "q1", "q2", "q3", "q4", "revenue", "ebitda", "margin", "net profit", "guidance"],
        "M_AND_A": ["acquisition", "merger", "stake sale", "takeover", "buyout", "divestment"],
        "REGULATORY": ["rbi", "sebi", "cci", "penalty", "tax notice", "investigation", "compliance", "policy"],
        "DEAL_WINS": ["contract win", "multi-year deal", "order book", "partnership", "agreement", "client deal"],
        "PRODUCT_LAUNCH": ["new launch", "expansion", "capacity", "commercial production", "patent"]
    }

    def evaluate_impact(self, article: NewsArticle) -> Dict[str, Any]:
        """
        Rule-assisted catalyst categorization and impact severity rating.

        Args:
            article (NewsArticle): Article to evaluate.

        Returns:
            Dict[str, Any]: Identified category, severity score (1-5), and horizon.
        """
        combined_text = f"{article.title} {article.summary or ''}".lower()
        detected_category = "GENERAL_UPDATE"
        severity = 2

        for category, keywords in self.CATALYST_KEYWORDS.items():
            for kw in keywords:
                if kw in combined_text:
                    detected_category = category
                    severity = 4 if category in ["EARNINGS", "M_AND_A", "REGULATORY"] else 3
                    break
            if detected_category != "GENERAL_UPDATE":
                break

        return {
            "category": detected_category,
            "severity_score": severity,
            "timeframe": "1-3 Days" if severity >= 4 else "3-5 Days"
        }
