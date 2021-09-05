import trio
import json
import logging
from trio_websocket import open_websocket_url
from utils import get_parser


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test')


TEST_DATA_LIST = [
    '{"test", "bad json"}',
    json.dumps([1, 2, 3]),
    json.dumps(
        {
            "bad_key": "c790сс",
            "lat": 55.7500,
            "lng": 37.600,
            "route": "120",
        }),
]


def parse_arguments():
    """Функция обработки аргументов командной строки."""
    parser = get_parser(
        'Async bus server for testing.',
        'harmful_bus_config.conf',
    )
    parser.add_arg(
        '-a',
        '--addr',
        help='Server address',
    )
    parser.add_arg(
        '-p',
        '--port',
        help='Server port',
        type=int,
    )
    return parser.parse_args()


async def run_app():
    args = parse_arguments()
    try:
        async with open_websocket_url(f'ws://{args.addr}:{args.port}') as ws:
            while True:
                for data in TEST_DATA_LIST:
                    await ws.send_message(data)
                    message = await ws.get_message()
                    logging.info(message)
                    await trio.sleep(0.5)
    except OSError as ose:
        logging.error('Connection attempt failed: %s', ose)


def main():
    trio.run(run_app)


if __name__ == '__main__':
    main()
