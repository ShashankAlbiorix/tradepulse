import os
import re
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import requests
from bs4 import BeautifulSoup
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# Load NOSIBLE Qwen3-0.6B Financial Sentiment LLM
MODEL_NAME = "NOSIBLE/financial-sentiment-v1.1-base"

print(f"Loading {MODEL_NAME}...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
device = "cuda" if torch.cuda.is_available() else "cpu"
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
    device_map="auto" if torch.cuda.is_available() else None,
    trust_remote_code=True
)
if device == "cpu":
    model.to("cpu")
model.eval()

def fetch_article_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()
    paragraphs = [p.get_text().strip() for p in soup.find_all("p") if p.get_text().strip()]
    return " ".join(paragraphs)[:3000]

def get_sentiment(text: str) -> dict:
    messages = [
        {"role": "system", "content": "Classify the financial sentiment as positive, neutral, or negative."},
        {"role": "user", "content": text}
    ]
    
    # Format prompt via chat template (supports up to 2048 tokens)
    input_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(input_text, return_tensors="pt", truncation=True, max_length=2048).to(model.device)
    
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=128,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
        )
    
    # Extract only the newly generated tokens
    new_tokens = output_ids[0][inputs.input_ids.shape[1]:]
    verdict = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    
    # Strip reasoning tags to get the final classification
    clean_text = re.sub(r"<think>.*?</think>", "", verdict, flags=re.DOTALL).strip().lower()
    target_eval = clean_text if clean_text else verdict.lower()
    
    if "positive" in target_eval or "bullish" in target_eval:
        standard_label = "BULLISH"
    elif "negative" in target_eval or "bearish" in target_eval:
        standard_label = "BEARISH"
    elif "neutral" in target_eval:
        standard_label = "NEUTRAL"
    else:
        standard_label = "NEUTRAL"

    return {
        "raw_response": verdict,
        "standard_verdict": standard_label
    }

if __name__ == "__main__":
    url = "https://www.livemint.com/news/india/if-there-s-a-good-time-it-is-now-former-shipping-secretary-on-india-s-shipbuilding-push-11791544472104.html"
    print(f"Fetching article from: {url}")
    article = fetch_article_text(url)
    if article:
        result = get_sentiment(article)
        print("\n--- Model Analysis Result ---")
        print("Raw Verdict:", result["raw_response"])
        print("TradePulse Verdict:", result["standard_verdict"])

