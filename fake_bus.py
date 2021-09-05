import trio
import logging
import os
import random
from sys import stderr
from functools import partial
from trio_websocket import open_websocket_url
import json
from itertools import cycle
from utils import (
    get_parser,
    relaunch_on_disconnect,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('test')


def parse_arguments():
    """Функция обработки аргументов командной строки."""
    parser = get_parser(
        'Async app for testing bus rout server application.',
        'config.conf',
    )
    parser.add_arg(
        '-s', 
        '--server', 
        help='Server address',
    )
    parser.add_arg(
        '-r',
        '--routes', 
        help='Number of routes',
        type=int,
    )
    parser.add_arg(
        '-bpr', 
        '--buses_per_route', 
        help='Buses per route',
        type=int,
    )
    parser.add_arg(
        '-wn', 
        '--websockets_number', 
        help='Maximum count of open socket',
        type=int,
    )
    parser.add_arg(
        '-eid', 
        '--emulator_id', 
        help='BusID prefix for multiply instance',
    )
    parser.add_arg(
        '-rt', 
        '--refresh_timeout', 
        help='Refresh buses points timeout',
        type=float,
    )
    parser.add_arg(
        '-v', 
        '--v', 
        help='Logging',
        action='store_true',
    )
    return parser.parse_args()


def generate_bus_id(route_id, bus_index, bus_prefix):
    return f'{bus_prefix}{route_id}-{bus_index}'


def shift(key, array):
    """Сдвиг массива."""
    return array[-key:] + array[:-key]


def load_routes(max_count, directory_path='routes'):
    """Генератор путей."""
    count = 0
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)
            count += 1

            if count >= max_count:
                break


async def run_bus(channel, route_id, bus_id, route, timeout=0.1):
    """Циклическая отправка координат пути в канал."""
    for coordinate in cycle(route):
        message_coordinate = {
            'busId': bus_id,
            'lat': coordinate[0],
            'lng': coordinate[1],
            'route': route_id,
        }
        await channel.send(
            json.dumps(
                message_coordinate,
                ensure_ascii=False,
            ),
        )
        await trio.sleep(timeout)


@relaunch_on_disconnect(logger)
async def send_updates(receive_channel, url, logger):
    """Чтение канала и отправка по сокету."""
    logger.info('Spawn memory channel')
    try:
        async with open_websocket_url(f'ws://{url}') as ws:
            async for value in receive_channel:
                await ws.send_message(value)
    except OSError:
        logger.info('Connection attempt failed')


async def run_app():
    args = parse_arguments()

    if not args.v:
        logger.propagate = False

    async with trio.open_nursery() as nursery:
        channels = []
        
        for index in range(args.websockets_number):
            channels.append(
                trio.open_memory_channel(index),
            )

        for route in load_routes(args.routes):
            channel = random.choice(channels)

            for bus_index in range(args.buses_per_route):
                route_shift = random.randint(5, len(route['coordinates']) - 5)

                nursery.start_soon(
                    partial(
                        run_bus,
                        timeout=args.refresh_timeout,
                    ),
                    channel[0],
                    route['name'],
                    generate_bus_id(
                        args.emulator_id,
                        route['name'],
                        bus_index,
                    ),
                    shift(
                        route_shift,
                        route['coordinates'],
                    ),
                )
        
        for channel in channels:
            nursery.start_soon(
                send_updates, 
                channel[1],
                args.server,
                logger,
            )


def main():
    try:
        trio.run(run_app)
    except KeyboardInterrupt:
        logger.info('Application closed.')


if __name__ == '__main__':
    main()
