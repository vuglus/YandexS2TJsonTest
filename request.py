import time
import requests
import traceback
import json
import urllib3
import os
import sys
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

API_KEY = os.getenv("API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")


def pretty_api_error(response):
    try:
        data = response.json()
    except Exception:
        return response.text

    if "error" in data:
        err = data["error"]
        if isinstance(err, dict):
            code = err.get("code", "unknown")
            msg = err.get("message", "no message")
            details = err.get("details", [])
            return f"API Error [{code}]: {msg}\nDetails: {json.dumps(details, ensure_ascii=False, indent=2)}"
        else:
            # если error = строка
            return f"API Error: {data}"

    return json.dumps(data, ensure_ascii=False, indent=2)


def main(file_path: str):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    file_uri = f"https://storage.yandexcloud.net/{file_path}"

    request_data = {
        "uri": file_uri,
        "recognitionModel": {
            "model": "general",
            "audioFormat": {
                "containerAudio": {
                    "containerAudioType": "MP3"
                }
            },
            "languageRestriction": {
                "restrictionType": "WHITELIST",
                "languageCode": ["ru-RU"]
            },
            "textNormalization": {
                "textNormalization": "TEXT_NORMALIZATION_DISABLED"
            }
        },
        "speakerLabeling": {
            "speakerLabeling": "SPEAKER_LABELING_DISABLED"
        }
    }

    headers = {
        "Authorization": f"Api-key {API_KEY}",
        "x-folder-id": FOLDER_ID
    }

    response = requests.post(
        "https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync",
        headers=headers,
        json=request_data,
        verify=False
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Recognition request failed: {response.status_code}\n{pretty_api_error(response)}"
        )

    operation_data = response.json()
    operation_id = operation_data.get("id")
    if not operation_id:
        raise RuntimeError("Operation ID not found in response")

    print(f"Operation ID: {operation_id}")
    print("Waiting for recognition to complete...", end="", flush=True)

    operation_url = f"https://operation.api.cloud.yandex.net/operations/{operation_id}"

    while True:
        op_response = requests.get(operation_url, headers=headers, verify=False)

        if op_response.status_code != 200:
            print(f"\nOperation check failed: {op_response.status_code}")
            print(pretty_api_error(op_response))
            time.sleep(10)
            continue

        op_data = op_response.json()

        if op_data.get("done"):
            if "error" in op_data:
                raise RuntimeError(f"Operation failed:\n{json.dumps(op_data['error'], ensure_ascii=False, indent=2)}")
            break

        print("Waiting for result...")
        time.sleep(10)

    speech_response = requests.get(
        f"https://stt.api.cloud.yandex.net/stt/v3/getRecognition?operation_id={operation_id}",
        headers=headers,
        verify=False
    )

    if speech_response.status_code != 200:
        raise RuntimeError(
            f"Result request failed: {speech_response.status_code}\n{pretty_api_error(speech_response)}"
        )
    return speech_response.text


if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Usage: python request.py <FILE_PATH>")
            sys.exit(1)

        FILE_PATH = sys.argv[1]
        result = main(FILE_PATH)

        # сохраняем в файл .json
        output_file = os.path.splitext(FILE_PATH)[0] + ".json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)

        print(f"Result saved to {output_file}")

    except Exception:
        traceback.print_exc()
