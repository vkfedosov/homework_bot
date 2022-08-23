import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import GetStatusException, TelegramBotSendError

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

last_check_timestamp = int(time.time())


def get_api_answer(timestamp):
    """Выполняет запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}

    try:
        homework_statuses = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
    except (requests.exceptions.ConnectionError,
            requests.exceptions.HTTPError,
            requests.exceptions.Timeout,
            requests.exceptions.TooManyRedirects,) as error:
        error_message = f'Ошибка при запросе к API: {error}'
        raise GetStatusException(error_message)

    status_code = homework_statuses.status_code
    if status_code != HTTPStatus.OK:
        raise GetStatusException(
            f'"{ENDPOINT}" - недоступен. Код ответа API: {status_code}'
        )

    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')

    homeworks = response['homeworks']

    if not isinstance(homeworks, list):
        raise TypeError('Ответ API не является списком')

    return homeworks


def parse_status(homework):
    """Извлекает статус работы из информации о конкретной домашней работе."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')

    if 'status' not in homework:
        raise KeyError('Отсутствует ключ "status" в ответе API')

    homework_name = homework['homework_name']
    homework_status = homework['status']

    verdict = HOMEWORK_STATUSES[homework_status]
    message = f'Изменился статус проверки работы "{homework_name}". {verdict}'
    return message


def check_tokens():
    """Проверяет доступ к переменным окружения, необходимых для работы бота."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except (telegram.error.BadRequest,
            telegram.error.InvalidToken,
            telegram.error.RetryAfter,
            telegram.error.TimedOut,
            telegram.error.Unauthorized,) as error:
        error_message = f'Ошибка при отправке сообщения в Telegram: {error}'
        raise TelegramBotSendError(error_message)


def get_status_message():
    """Получение статуса домашнего задания."""
    global last_check_timestamp
    response = get_api_answer(last_check_timestamp)
    last_check_timestamp = response.get('current_date')

    try:
        homeworks = check_response(response)
    except (TypeError, KeyError) as error:
        error_message = f'Получены неправильные данные: {error}'
        raise GetStatusException(error_message)

    if not homeworks:
        return ''

    last_homework = homeworks[0]

    try:
        message = parse_status(last_homework)
    except KeyError as error:
        error_message = f'Ошибка при получении данных по API: {error}'
        raise GetStatusException(error_message)

    return message


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        error_message = 'Отсутствуют одна или несколько переменных окружения'
        logger.critical(error_message)
        raise SystemExit(error_message)

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    last_sent_message = ''

    while True:

        try:
            message = get_status_message()
        except GetStatusException as error:
            message = f'Ошибка получения статуса домашней работы: {error}'
            logging.error(message)

        if message and message != last_sent_message:
            try:
                send_message(bot, message)
                last_sent_message = message
            except TelegramBotSendError as error:
                error_message = f'Ошибка отправки сообщения: {error}'
                logging.error(error_message)

        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
