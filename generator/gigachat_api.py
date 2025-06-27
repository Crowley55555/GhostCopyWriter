import os
import base64
from dotenv import load_dotenv

from langchain_gigachat.chat_models import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage

load_dotenv()

CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
CLIENT_SECRET = os.getenv("GIGACHAT_CLIENT_SECRET")
SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")

# Отладочный вывод для диагностики проблем с переменными окружения
print("CLIENT_ID:", repr(CLIENT_ID))
print("CLIENT_SECRET:", repr(CLIENT_SECRET))
print("SCOPE:", repr(SCOPE))

def _get_base64_credentials():
    creds = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
    return base64.b64encode(creds).decode()

def _init_client():
    return GigaChat(
        credentials=_get_base64_credentials(),
        scope=SCOPE,
        verify_ssl_certs=False
    )

def generate_text(data):
    giga = _init_client()
    messages = [
        SystemMessage(content="Ты — опытный SMM‑копирайтер."),
        HumanMessage(content=(
            f"Напиши {data['template_type']} пост в тоне {data['tone']} "
            f"для {data['platform']}. Тема: {data['topic']}"
        ))
    ]
    resp = giga.invoke(messages)
    return resp.content

def generate_image_gigachat(topic):
    giga = _init_client()
    messages = [
        SystemMessage(content="Ты — талантливый художник и копирайтер."),
        HumanMessage(content=f"Создай иллюстрацию по теме: {topic}")
    ]
    resp = giga.invoke(messages)
    print("GigaChat image response:", resp)
    print("GigaChat image response content:", getattr(resp, 'image_url', None), resp.content)
    return getattr(resp, "image_url", resp.content)
