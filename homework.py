import os
from http import HTTPStatus
import logging
import sys
import time
import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# 600 секунд
RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}

SECONDS_IN_MINUTE = 60
MINUTES_IN_HOUR = 60
HOURS_IN_DAY = 24
ONE_DAY_IN_SEC = HOURS_IN_DAY * MINUTES_IN_HOUR * SECONDS_IN_MINUTE
MONTH = 30 * ONE_DAY_IN_SEC


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}
cache = {}


def is_status_of_last_work_change(homework_name, status):
    """Поменялся ли статус или последняя работа."""
    if homework_name not in cache:
        cache[homework_name] = status
        return True
    if cache[homework_name] != status:
        return True
    logging.debug("Статус {homework_name} не изменился")
    return False


def check_tokens():
    """Проверяем есть ли переменые окружения."""
    if not PRACTICUM_TOKEN:
        logging.critical("Нет переменной окружения: PRACTICUM_TOKEN")
        raise Exception("Нет PRACTICUM_TOKEN")

    if not TELEGRAM_TOKEN:
        logging.critical("Нет переменной окружения: TELEGRAM_TOKEN")
        raise Exception("Нет TELEGRAM_TOKEN")

    if not TELEGRAM_CHAT_ID:
        logging.critical("Нет переменной окружения: TELEGRAM_CHAT_ID")
        raise Exception("Нет TELEGRAM_CHAT_ID")
    return True


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug("Успешная работа send_message")
    except Exception as error:
        logging.error(f"Ошибка при отправке сообщения ТГ: {error}")
        raise ValueError(error) from error


def get_api_answer(timestamp):
    """Запрос к апи домашней работы."""
    try:
        if not isinstance(timestamp, int):
            raise ValueError("не  timestamp")
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={"from_date": timestamp - MONTH}
        )
        if response.status_code == HTTPStatus.OK:
            json = response.json()
            if not isinstance(json, dict):
                raise Exception("json не словарь")
            return json
        else:
            logging.error(
                f"Ошибка в get_api_answer : status {response.status_code}"
            )
            raise Exception(
                f"Не коректный статус ответа - {response.status_code}"
            )
    except Exception as error:
        raise ValueError(error) from error


def check_response(response):
    """Проверка корректности ответа апи."""
    if not isinstance(response, dict):
        raise TypeError(f"Тип ответа не dict, response=={response} ")
    if "homeworks" not in response:
        raise Exception("Нет поля homeworks в ответе")
    if not isinstance(response["homeworks"], list):
        item = response["homeworks"]
        raise TypeError(
            "Тип homeworks не list, response['homeworks'] == {item}"
        )
    if not isinstance(response["homeworks"][-1], dict):
        item = response["homeworks"][-1]
        raise TypeError(
            f"Тип ответа не dict, response['homeworks'][-1]=={item}"
        )
    return response["homeworks"][-1]


def parse_status(homework):
    """Достаем из ответа данные."""
    logging.debug(homework)
    if "homework_name" not in homework:
        logging.error("Нет поля homework_name в ответе")
        raise Exception("Нет поля homework_name в ответе")
    homework_name = homework["homework_name"]
    if "status" not in homework:
        logging.error("Нет поля status в ответе")
        raise Exception("Нет поля status в ответе")
    status = homework.get("status")
    if not status:
        logging.error("Пустое поле status")
        raise Exception("Пустое поле status")
    if status not in HOMEWORK_VERDICTS.keys():
        logging.error(f"Нет статуса {status} в словаре HOMEWORK_VERDICTS")
        raise Exception(f"Нет статуса {status} в словаре HOMEWORK_VERDICTS")
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            text = parse_status(homework)
            if is_status_of_last_work_change(
                homework_name=homework["homework_name"],
                status=homework["status"],
            ):
                send_message(bot, text)
        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        filemode="w",
        format="%(asctime)s, %(levelname)s, %(message)s",
    )
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)
    main()
