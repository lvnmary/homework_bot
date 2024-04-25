import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from exceptions import EndpointError

load_dotenv()

logger = logging.getLogger(__name__)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение отправлено.')
    except telegram.TelegramError:
        logging.error('Не удалось отправить сообщение.')


def get_api_answer(timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    try:
        response = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    except Exception as error:
        raise EndpointError(error)
    if response.status_code != HTTPStatus.OK:
        raise requests.RequestException(f'Ошибка запроса к API'
                                        f'{response.status_code}')
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    if isinstance(response, dict) is False:
        raise TypeError('Получен неверный тип данных.')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа homeworks.')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа current_date.')
    if isinstance(response['homeworks'], list) is False:
        raise TypeError('Неверный тип данных homeworks.')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'homework_name' not in homework:
        raise KeyError('В ответе API нет ключа homework_name.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Ошибка в статусе домашней работы.')
    return (f'Изменился статус проверки работы "{homework_name}".'
            f'{HOMEWORK_VERDICTS[homework_status]}')


def main():
    """Основная логика работы бота."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s',
    )
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)

    if not check_tokens():
        logging.critical('Отсутствуют переменные окружения')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    prev_message = None
    prev_error = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                new_message = parse_status(homework[0])
                if new_message != prev_message:
                    send_message(bot, new_message)
                    prev_message = new_message
                else:
                    logging.debug('Нет домашек на проверку')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if error != prev_error:
                send_message(bot, message)
                prev_error = error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
