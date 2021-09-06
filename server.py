import trio
import json
import logging
from functools import partial
from dataclasses import dataclass, asdict
from trio_websocket import serve_websocket, ConnectionClosed
from utils import get_parser


BUSES = {}


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('server')


@dataclass
class Bus:
    busId: str
    lat: float
    lng: float
    route: float


@dataclass
class WindowBounds:
    south_lat: float
    north_lat: float
    west_lng: float
    east_lng: float

    def is_inside(self, bus) -> bool:
        """
            Проверка вхождения bus по координатам
            lat, lng в WindowBounds.
        """
        return self.south_lat < bus.lat < self.north_lat and \
            self.west_lng < bus.lng < self.east_lng

    def update(self, south_lat, north_lat, west_lng, east_lng):
        self.south_lat = south_lat
        self.north_lat = north_lat
        self.west_lng = west_lng
        self.east_lng = east_lng


def parse_arguments():
    """Функция обработки аргументов командной строки."""
    parser = get_parser(
        'Async server with bus routes.',
        'server_config.conf',
    )
    parser.add_arg(
        '-sa',
        '--server_addr',
        help='Server address',
    )
    parser.add_arg(
        '-ba',
        '--buses_addr',
        help='Server address',
    )
    parser.add_arg(
        '-bup',
        '--bus_port',
        help='Port to read buses data',
        type=int,
    )
    parser.add_arg(
        '-brp',
        '--browser_port',
        help='Port for client connection',
        type=int,
    )
    parser.add_arg(
        '-v',
        '--v',
        help='Logging',
        action='store_true',
    )
    return parser.parse_args()


def validate_bus_json(json_data):
    try:
        data = json.loads(json_data)

        if not isinstance(data, dict):
            return False, 'Incorrect type'

        if set(data.keys()) != {'busId', 'lat', 'lng', 'route'}:
            return (
                False,
                'Requires busId, lat, lng, route as keys in parent object',
            )

    except ValueError:
        return False, 'Requires valid JSON'
    return True, None


def validate_bounds_json(json_data):
    try:
        data = json.loads(json_data)

        if not isinstance(data, dict):
            return False, 'Incorrect type'

        if set(data.keys()) != {'msgType', 'data'}:
            return False, 'Requires msgType, data as keys in parent object'

        if data['msgType'] != 'newBounds':
            return False, 'Incorrect msgType'

        if set(data['data'].keys()) != {
            'east_lng',
            'north_lat',
            'south_lat',
            'west_lng',
        }:
            return False, 'Incorrect data keys'
    except ValueError:
        return False, 'Requires valid JSON'
    return True, None


async def listen_browser(ws, viewport):
    """Получение координат окна от клиента."""
    while True:
        try:
            message = await ws.get_message()
            status, validate_message = validate_bounds_json(message)

            if status:
                bounds = json.loads(message)['data']
                viewport.update(**bounds)
            else:
                await ws.send_message(
                    json.dumps(
                        {
                            'errors': [validate_message],
                            'msgType': 'Errors',
                        },
                    ),
                )
        except ConnectionClosed:
            break


async def send_to_browser(ws, viewport, buses={}):
    """Отправка данных одному фронту."""
    while True:
        try:
            buses_inside_viewport = [
                asdict(bus) for bus in buses.values()
                if viewport.is_inside(bus)
            ]
            await ws.send_message(
                json.dumps({
                    'msgType': 'Buses',
                    'buses': buses_inside_viewport,
                }),
            )
            await trio.sleep(0.5)
        except ConnectionClosed:
            break


async def talk_to_browser(request, logger=logger, buses={}):
    """Отправка данных нескольким фронтам."""
    async with trio.open_nursery() as nursery:
        ws = await request.accept()
        logger.info('Accept connection from browser')
        viewport = WindowBounds(0, 0, 0, 0)
        nursery.start_soon(
            send_to_browser,
            ws,
            viewport,
            buses,
        )
        nursery.start_soon(
            listen_browser,
            ws,
            viewport,
        )


async def read_buses(request, buses={}):
    """Чтение данных из подключения fake_bus.py"""
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            validate_status = validate_bus_json(message)

            if validate_status[0]:
                bus_data = json.loads(message)
                buses[bus_data['busId']] = Bus(**bus_data)
            else:
                await ws.send_message(
                    json.dumps(
                        {
                            'errors': [validate_status[1]],
                            'msgType': 'Errors',
                        },
                    ),
                )

        except ConnectionClosed:
            await ws.aclose()
            break


async def run_app():
    args = parse_arguments()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(
            partial(
                serve_websocket,
                ssl_context=None,
            ),
            partial(
                read_buses,
                buses=BUSES,
            ),
            args.buses_addr,
            args.bus_port,
        )
        nursery.start_soon(
            partial(
                serve_websocket,
                ssl_context=None,
            ),
            partial(
                talk_to_browser,
                logger=logger,
                buses=BUSES,
            ),
            args.server_addr,
            args.browser_port,
        )
        logger.info('Application started.')


def main():
    try:
        trio.run(run_app)
    except KeyboardInterrupt:
        logger.info('Application closed.')


if __name__ == '__main__':
    main()
