from config.settings import settings
from src.notify.telegram import _send

print(f"TOKEN 길이: {len(settings.telegram_bot_token)}")
print(f"CHAT_ID: {settings.telegram_chat_id}")
_send("GitHub Actions 텔레그램 테스트 성공")
print("전송 시도 완료")
