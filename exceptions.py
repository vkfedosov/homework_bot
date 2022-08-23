class TelegramBotError(Exception):
    """Ошибка отправки сообщения в Telegram."""
    pass


class TelegramNetworkError(Exception):
    """Ошибка подключения к сети."""
    pass


class ApiResponseError(Exception):
    """Ошибка при запросе к API."""
    pass


class HomeworkError(Exception):
    """Ошибка при получении домашнего задания."""
    pass
