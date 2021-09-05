import configargparse
import functools
import trio
import trio_websocket
from pathlib import Path


def get_parser(description: str, config_file: str):
    """Функция для генерации парсера аргументов командной строки."""
    return configargparse.ArgParser(
        default_config_files=[
            str(Path.cwd() / 'configs' / config_file),
        ],
        description=description,
    )


def relaunch_on_disconnect(logger):
    """Циклически перезапускает соединение при отлове ошибок."""
    def wrapper(async_function):
        @functools.wraps(async_function)
        async def wrapper(*args, **kwargs):
            while True:
                try:
                    await async_function(*args, **kwargs)
                except (
                    trio_websocket.ConnectionClosed,
                    trio_websocket.HandshakeError
                ):
                    logger.info('WS reconnect')
                    await trio.sleep(1)
        return wrapper
    return wrapper
