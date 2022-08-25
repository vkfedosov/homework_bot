class SendMessageError(Exception):
    """Ошибка отправки сообщения в Telegram."""
    pass


class GetStatusException(Exception):
    """Ошибка при получении статуса домашнего задания."""
    pass
