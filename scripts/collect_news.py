import os
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

IST = ZoneInfo("Asia/Kolkata")

PIB_FEED = (
    "https://pib.gov.in/RssMain.aspx"
    "?ModId=6&Lang=1&Regid=3"
)

MODEL = "gemini-3.5-flash-lite"

def fetch_news():
    request = urllib.request.Request(
        PIB_FEED,
        headers={"User-Agent": "RailwayExamHub/1.0"}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        root = ET.fromstring(response.read())

    articles = []
    seen = set()

    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        description = item.findtext("description", "").strip()
        pub_date = item.findtext("pubDate", "")

        if not title or not link or link in seen:
            continue

        seen.add(link)

        description = re.sub(
            r"<[^>]+>", " ", description
        ).strip()

        articles.append({
            "title": title,
            "description": description[:1500],
            "source": "PIB",
            "url": link,
            "published": pub_date
        })

    return articles[:30]


def generate_with_gemini(articles):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("Gemini key unavailable. Saving news only.")
        return None

    prompt = """
You are an educational content assistant for Indian
Railway recruitment examinations.

Use ONLY the supplied news articles.

Create:
1. Important current affairs summaries.
2. Exactly 20 MCQs if sufficient facts exist.
3. Four options per question.
4. Correct answer and short explanation.
5. Original source URL for each question.

Do not invent facts, dates, statistics or events.
Do not use outside knowledge to fill missing facts.
If information is insufficient, create fewer questions.

Return valid JSON only, in this structure:
{
  "summary": [],
  "questions": [
    {
      "question": "",
      "options": ["", "", "", ""],
      "answer": "",
      "explanation": "",
      "source_url": ""
    }
  ]
}

NEWS:
""" + json.dumps(articles, ensure_ascii=False)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/" + MODEL + ":generateContent?"
        + urllib.parse.urlencode({"key": api_key})
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8000
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=90) as response:
        result = json.loads(response.read())

    text = result["candidates"][0]["content"]["parts"][0]["text"]

    return json.loads(text)


def main():
    now = datetime.now(IST)

    print("Railway Exam Hub: Daily Current Affairs")
    print("Date:", now.strftime("%d-%m-%Y"))

    articles = fetch_news()
    print("Articles collected:", len(articles))

    ai_content = None

    try:
        ai_content = generate_with_gemini(articles)
        print("Gemini generation completed.")
    except Exception as error:
        print("Gemini unavailable:", str(error))
        print("Continuing with collected news.")

    output = {
        "date": now.strftime("%Y-%m-%d"),
        "updated": now.isoformat(),
        "source": "PIB",
        "articles": articles,
        "ai_content": ai_content,
        "review_status": "needs_review"
    }

    folder = Path("current-affairs-data")
    folder.mkdir(exist_ok=True)

    output_file = folder / "daily.json"

    output_file.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print("Saved:", output_file)


if __name__ == "__main__":
    main()
