import trio
import json
from functools import partial
from trio_websocket import serve_websocket, ConnectionClosed


SERVER_ADDR = '127.0.0.1'
BUSES = {}


async def send_to_browser(ws, buses={}):
    """Отправка данных одному фронту."""
    while True:
        try:
            await ws.send_message(
                json.dumps({
                    'msgType': 'Buses',
                    'buses': list(buses.values()),
                }),
            )
            await trio.sleep(0.5)
        except ConnectionClosed:
            break


async def talk_to_browser(request, buses={}):
    """Отправка данных нескольким фронтам."""
    async with trio.open_nursery() as nursery:
        ws = await request.accept()
        print('Accept')
        nursery.start_soon(
            send_to_browser,
            ws,
            buses,
        )

     
async def read_buses(request, buses={}):
    """Чтение данных из подключения fake_bus.py"""
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            bus_data = json.loads(message)
            buses[bus_data['busId']] = bus_data
        except ConnectionClosed:
            await ws.aclose()
            break


async def main():
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
            SERVER_ADDR,
            8080,
        )
        nursery.start_soon(
            partial(
                serve_websocket,
                ssl_context=None,
            ),
            partial(
                talk_to_browser,
                buses=BUSES,
            ),
            SERVER_ADDR,
            8000,
        )

trio.run(main)
