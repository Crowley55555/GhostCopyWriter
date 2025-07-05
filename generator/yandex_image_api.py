from dotenv import load_dotenv
load_dotenv()
import os
import requests
import time

FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
IAM_TOKEN = os.getenv("YANDEX_IAM_TOKEN")

def generate_image(prompt):
    """
    Заглушка для Yandex Image API
    Возвращает None, так как теперь используется GigaChat для генерации изображений
    """
    print("Yandex Image API временно отключен. Используется GigaChat для генерации изображений.")
    return None

    # Закомментированный оригинальный код для справки:
    # if not FOLDER_ID or not IAM_TOKEN:
    #     print("YANDEX_FOLDER_ID или YANDEX_IAM_TOKEN не заданы!")
    #     return None

    # url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
    # headers = {
    #     "Authorization": f"Bearer {IAM_TOKEN}",
    #     "Content-Type": "application/json"
    # }
    # data = {
    #     "folderId": FOLDER_ID,
    #     "modelUri": "art://vqgan_imagenet_f16_16384",
    #     "generationOptions": {
    #         "preset": "TEXT2IMAGE"
    #     },
    #     "messages": [{
    #         "role": "user",
    #         "text": prompt
    #     }]
    # }

    # try:
    #     response = requests.post(url, headers=headers, json=data)
    #     response.raise_for_status()
    #     operation_id = response.json()["id"]
    # except Exception as e:
    #     print("Ошибка при отправке запроса на генерацию изображения:", e)
    #     return None

    # result_url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"
    # for _ in range(15):  # увеличено количество попыток
    #     time.sleep(2)
    #     try:
    #         status_resp = requests.get(result_url, headers=headers)
    #         status = status_resp.json()
    #         if status.get("done") and "response" in status:
    #             return status["response"]["image"]["url"]
    #     except Exception as e:
    #         print("Ошибка при получении статуса генерации:", e)
    #         return None
    # print("Не удалось получить изображение за отведённое время.")
    # return None
