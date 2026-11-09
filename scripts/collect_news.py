from datetime import datetime
from zoneinfo import ZoneInfo

def main():
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    print("Railway Exam Hub")
    print("Daily Current Affairs Automation")
    print("Date:", now.strftime("%d-%m-%Y"))
    print("Status: Ready")

if __name__ == "__main__":
    main()
