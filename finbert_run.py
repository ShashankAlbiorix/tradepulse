from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Load FinBERT once
tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert")
model = AutoModelForSequenceClassification.from_pretrained("ProsusAI/finbert")

def get_sentiment(text: str) -> str:
    """Return sentiment verdict for given text using FinBERT."""
    inputs = tokenizer(text, return_tensors="pt", truncation=True)
    outputs = model(**inputs)
    probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
    labels = ["positive", "negative", "neutral"]
    return labels[torch.argmax(probs)]

if __name__ == "__main__":
    # Try multiple headlines
    headlines = [
    "Sensex tanks 1,045 pts, Nifty ends at 22,232 as oil tops $104",
    "Stock Market Crash: Investors Lose ₹10 Lakh Crore As Sensex Tanks 1,000 Points",
    "Adani Enterprises down 7% as Sensex slides 930 points, Nifty below 22,300"
    ]
    for h in headlines:
        print(f"Headline: {h}")
        print(f"Verdict: {get_sentiment(h)}\n")
