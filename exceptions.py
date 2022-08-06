class SendMessageError(Exception):
    """Ошибка отправки сообщения."""
    pass


class InvalidApiError(Exception):
    """Ошибка при запросе к API."""
    pass


class InvalidResponseError(Exception):
    """Ошибка - status_code API != 200."""
    pass
