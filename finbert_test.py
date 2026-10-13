# finbert_test.py
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

# Load FinBERT model and tokenizer
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
    # Example headline
    headline = "Markets rally after Federal Reserve announces rate cuts"
    verdict = get_sentiment(headline)
    print(f"Headline: {headline}")
    print(f"Verdict: {verdict}")
