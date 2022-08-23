import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (ApiResponseError, HomeworkError, TelegramBotError,
                        TelegramNetworkError)

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(funcName)s, %(lineno)s, %(levelname)s, %(message)s',
    filemode='w',
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'my_logger.log',
    maxBytes=50000000,
    backupCount=5,
)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 1800
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.error.Unauthorized as error:
        error_message = f'Bot не имеет необходимых прав: {error}'
        raise TelegramBotError(error_message)
    except telegram.error.InvalidToken as error:
        error_message = f'Токен недействителен: {error}'
        raise TelegramBotError(error_message)
    except telegram.error.RetryAfter as error:
        error_message = (
            f'Превышено значение максимального количества запросов: {error}'
        )
        raise TelegramBotError(error_message)
    except telegram.error.TimedOut as error:
        error_message = (
            f'Выполнение запроса заняло слишком много времени: {error}'
        )
        raise TelegramNetworkError(error_message)
    except telegram.error.BadRequest as error:
        error_message = (
            f'Telegram не может корректно обработать запрос: {error}'
        )
        raise TelegramNetworkError(error_message)


def get_api_answer(current_timestamp):
    """Выполняет запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except requests.exceptions.HTTPError as error:
        error_message = f'Ошибка Http: {error}'
        raise ApiResponseError(error_message)
    except requests.exceptions.ConnectionError as error:
        error_message = f'Ошибка подключения: {error}'
        raise ApiResponseError(error_message)
    except requests.exceptions.Timeout as error:
        error_message = f'Время запроса вышло: {error}'
        raise ApiResponseError(error_message)
    except requests.exceptions.TooManyRedirects as error:
        error_message = (
            f'Превышено значение максимального количества редиректов: {error}'
        )
        raise ApiResponseError(error_message)
    except requests.exceptions.RequestException as error:
        error_message = f'Ошибка при запросе к API: {error}'
        raise SystemExit(error_message)

    if homework_statuses.status_code != HTTPStatus.OK:
        status_code = homework_statuses.status_code
        raise ApiResponseError(
            f'"{ENDPOINT}" - недоступен. Код ответа API: {status_code}'
        )
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ API не является списком')
    try:
        return response['homeworks'][0]
    except Exception as error:
        raise HomeworkError(f'Домашние задание отсутствует: {error}')


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    homework_name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступ к переменным окружения, необходимых для работы бота."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Отсутствуют одна или несколько переменных окружения'
        logger.critical(error_message)
        raise SystemExit(error_message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    last_massage = ''
    last_massage_error = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homework = check_response(response)
            message = parse_status(homework)
            if message != last_massage:
                send_message(bot, message)
                last_massage = message
            time.sleep(RETRY_TIME)
        except telegram.error.TelegramError as error:
            error_message = f'Ошибка отправки сообщения в Telegram: {error}'
            raise TelegramBotError(error_message)
        except Exception as error:
            error_message = f'Сбой в работе бота: {error}'
            logging.error(error_message)
            if error_message != last_massage_error:
                send_message(bot, error_message)
                last_massage_error = error_message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
