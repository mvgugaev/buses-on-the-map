import trio
import os
import random
from sys import stderr
from trio_websocket import open_websocket_url
import json
from itertools import cycle


SERVER_URL = '127.0.0.1:8080'


def generate_bus_id(route_id, bus_index):
    return f'{route_id}-{bus_index}'


def shift(key, array):
    return array[-key:] + array[:-key]


def load_routes(directory_path='routes'):
    for filename in os.listdir(directory_path):
        if filename.endswith(".json"):
            filepath = os.path.join(directory_path, filename)
            with open(filepath, 'r', encoding='utf8') as file:
                yield json.load(file)


async def run_bus(url, route_id, bus_id, route):
    async with open_websocket_url(f'ws://{url}') as ws:
        for coordinate in cycle(route):
            message_coordinate = {
                'busId': bus_id,
                'lat': coordinate[0],
                'lng': coordinate[1],
                'route': route_id,
            }
            await ws.send_message(
                json.dumps(
                    message_coordinate,
                    ensure_ascii=False,
                ),
            )
            await trio.sleep(0.1)


async def main():
    try:
        async with trio.open_nursery() as nursery:
            connection_count = 0
            for route in load_routes():
                
                nursery.start_soon(
                    run_bus,
                    SERVER_URL,
                    route['name'],
                    generate_bus_id(route['name'], 1),
                    route['coordinates'],
                )

                route_shift = random.randint(5, len(route['coordinates']) - 5)

                nursery.start_soon(
                    run_bus,
                    SERVER_URL,
                    route['name'],
                    generate_bus_id(route['name'], 2),
                    shift(
                        route_shift,
                        route['coordinates'],
                    ),
                )
                connection_count += 1

                if connection_count > 100:
                    break

    except OSError as ose:
        print('Connection attempt failed: %s' % ose, file=stderr)

trio.run(main)