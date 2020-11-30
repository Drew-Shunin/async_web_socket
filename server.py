"""Async web socket server"""

import asyncio
import json
import functools
import logging

import aiohttp
from aiohttp import web

import stats_handler

logger = logging.getLogger(__name__)


def run_in_executor(func):
    """Execute blocking functions in async way"""
    @functools.wraps(func)
    def inner(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    return inner


@run_in_executor
def prepare_data(req):
    """Construct json response"""
    data = {}
    if req["cpu"]:
        data["cpu"] = stats_handler.get_cpu_stats()
    if req["mem"]:
        data["mem"] = stats_handler.get_mem_stats()
    if req["space"]:
        data["space"] = stats_handler.get_space_stats()

    return data


class Server:
    """Async server"""
    def __init__(self):
        """Init"""
        self.app = aiohttp.web.Application()
        self.app.add_routes([aiohttp.web.get('/ws', self.websocket_handler)])

    def run(self):
        """Run server"""
        aiohttp.web.run_app(self.app)

    async def send_data(self, web_socket, request_data):
        """Send data to client"""
        await web_socket.send_json(request_data)

    async def client_handler(self, web_socket, raw_req):
        """Async client handler"""
        # NOTE: json schema could be used as message
        # format validation mechanism
        try:
            req = json.loads(raw_req)
        except json.JSONDecodeError:
            logger.error("Doesn't looks like proper json. %s", raw_req)
            await web_socket.close()
            return
        logger.debug(req)
        timeout = float(req["timeout"])
        while not web_socket.closed:
            rsp_data = await prepare_data(req)
            logger.debug(
                "Send msg to client with %s timeout: %s", timeout, rsp_data
            )
            try:
                await self.send_data(web_socket, rsp_data)
            except ConnectionResetError:
                logger.warning("Connection to client lost")
                await web_socket.close()
                break
            await asyncio.sleep(timeout)

    async def websocket_handler(self, request):
        """Async socket handler for incoming client connection"""
        web_socket = web.WebSocketResponse()
        await web_socket.prepare(request)
        # NOTE: Don't know how to differentiate connected client. It would be
        # good to have some client info (address, port)
        logger.info("Client connected.")
        async for msg in web_socket:
            logger.debug(msg)
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == "close":
                    await web_socket.close()
                    break
                # NOTE: There is got to be a better way to differentiate incoming
                # 'text' messages
                loop = asyncio.get_event_loop()
                loop.create_task(self.client_handler(web_socket, msg.data))

            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(
                    'Connection closed with exception %s', web_socket.exception()
                )

            elif msg.type == aiohttp.WSMsgType.CLOSE:
                logger.info("Connection closed")
                await web_socket.close()
                break

        logger.info('websocket closed')
        return web_socket


def main():
    """main"""
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    log_format = '%(asctime)s: %(message)s'
    time_format = '%Y-%m-%d %H:%M:%S'
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG, format=log_format, datefmt=time_format
        )
    else:
        logging.basicConfig(
            level=logging.INFO, format=log_format, datefmt=time_format
        )

    srv = Server()
    srv.run()


if __name__ == '__main__':
    main()
