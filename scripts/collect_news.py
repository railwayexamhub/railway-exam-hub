import os
import json
import re
import html
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

# Railway Exam Hub configuration

IST = ZoneInfo("Asia/Kolkata")

MODEL = "gemini-3.5-flash-lite"

PIB_FEED = (
    "https://pib.gov.in/RssMain.aspx"
    "?ModId=6&Lang=1&Regid=3"
)


def fetch_news():

    print("Collecting official PIB news...")

    request = urllib.request.Request(
        PIB_FEED,
        headers={
            "User-Agent": "RailwayExamHub/1.0"
        }
    )

    with urllib.request.urlopen(
        request, timeout=30
    ) as response:

        root = ET.fromstring(response.read())

    articles = []
    seen = set()

    for item in root.findall(".//item"):

        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()

        description = item.findtext(
            "description", ""
        ).strip()

        pub_date = item.findtext("pubDate", "")

        if not title or not link:
            continue

        if link in seen:
            continue

        seen.add(link)

        description = html.unescape(
            re.sub(r"<[^>]+>", " ", description)
        )

        articles.append({
            "title": title,
            "description": description[:1500],
            "source": "PIB",
            "url": link,
            "published": pub_date
        })

    print("News collected:", len(articles))

    return articles[:30]


def generate_with_gemini(articles):

    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        print("Gemini API key unavailable.")
        return None

    if not articles:
        print("No news available for Gemini.")
        return None

    print("Sending selected news to Gemini...")

    prompt = """
You are a professional Indian Railway examination
current affairs content creator.

LANGUAGE REQUIREMENT:
Write ALL content in ENGLISH ONLY.
This includes summaries, questions, options,
answers and explanations.
Never generate Hindi or any other language.
Translate Hindi news into English before
creating educational content.

Prepare educational material for:
Prepare educational material for:

RRB Group D
RRB NTPC
RRB ALP
RRB Technician
RRB JE
Station Master

Use ONLY the supplied news articles.

Create the following:

1. Important current affairs summaries.
2. Up to 20 multiple-choice questions.
3. Four options per question.
4. Correct answer.
5. Short explanation.
6. Original source URL.

Questions must be factually correct.

IMPORTANT RULES:

- Never invent news or statistics.
- Never invent dates or government schemes.
- Do not use facts absent from the supplied news.
- Do not create duplicate questions.
- If there is insufficient information,
  create fewer questions.
- Keep source URLs for verification.

Return valid JSON only:

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

NEWS ARTICLES:

""" + json.dumps(
        articles,
        ensure_ascii=False
    )

    url = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        + MODEL
        + ":generateContent"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8000
        }
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        },
        method="POST"
    )

    with urllib.request.urlopen(
        request, timeout=90
    ) as response:

        result = json.loads(response.read())

    response_text = (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
    )

    generated = json.loads(response_text)

    questions = generated.get("questions", [])

    valid_questions = []

    for question in questions:

        options = question.get("options", [])

        if (
            question.get("question")
            and len(options) == 4
            and question.get("answer")
            and question.get("explanation")
            and question.get("source_url")
        ):
            valid_questions.append(question)

    generated["questions"] = valid_questions[:20]

    print(
        "Gemini generated questions:",
        len(valid_questions)
    )

    return generated


def save_data(articles, ai_content):

    now = datetime.now(IST)

    output = {
        "website": "Railway Exam Hub",
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
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("Daily data saved:", output_file)
    
# Save monthly archive
    archive_folder = folder / "archive"
    archive_folder.mkdir(exist_ok=True)

    month_name = now.strftime("%Y-%m")
    archive_file = archive_folder / f"{month_name}.json"

    if archive_file.exists():
        with open(archive_file, "r", encoding="utf-8") as f:
            monthly_data = json.load(f)
    else:
        monthly_data = {
            "month": month_name,
            "days": []
        }

    daily_entry = output.copy()

    monthly_data["days"] = [
        day for day in monthly_data["days"]
        if day.get("date") != output["date"]
    ]

    monthly_data["days"].append(daily_entry)

    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(
            monthly_data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("Monthly archive saved:", archive_file)

    # Keep current month and previous five months
    current_month = now.year * 12 + now.month - 1
    oldest_month = current_month - 5

    for old_file in archive_folder.glob("????-??.json"):
        try:
            year, month = map(int, old_file.stem.split("-"))
            file_month = year * 12 + month - 1

            if file_month < oldest_month:
                old_file.unlink()
                print("Deleted old archive:", old_file)

        except (ValueError, OSError):
            print("Could not process archive:", old_file)

def main():

    print("--------------------------------")
    print("RAILWAY EXAM HUB")
    print("DAILY CURRENT AFFAIRS")
    print("--------------------------------")

    now = datetime.now(IST)

    print("Date:", now.strftime("%d-%m-%Y"))

    articles = fetch_news()

    ai_content = None

    try:

        ai_content = generate_with_gemini(
            articles
        )

        print("Gemini processing completed.")

    except Exception as error:

        print("Gemini unavailable:", str(error))

        print(
            "Using Python news collection backup."
        )

    save_data(articles, ai_content)

    print("Automation completed.")


if __name__ == "__main__":

    main()
