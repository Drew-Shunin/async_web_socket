"""Async client example with web sockets"""

import asyncio
import json
import logging
import signal
import contextlib

import aiohttp


logger = logging.getLogger(__name__)


class Client:
    """Async client"""

    def __init__(self, host, port):
        """Init"""
        self.host = host
        self.port = port
        self.address = f"ws://{self.host}:{self.port}/ws"
        self.session_client = aiohttp.ClientSession()
        self.ws_connection = None

    @staticmethod
    def fmt_message(msg):
        """Format received message"""
        fmt = []
        if "cpu" in msg:
            fmt.append(f"CPU load: {msg['cpu']}%")
        if "mem" in msg:
            fmt.append(
                f"Mem: {msg['mem']['used']}{msg['mem']['dimension']} / "
                f"{msg['mem']['total']}{msg['mem']['dimension']}"
            )
        if "space" in msg:
            fmt.append(
                f"Space: {msg['space']['used']}{msg['space']['dimension']} / "
                f"{msg['space']['total']}{msg['space']['dimension']}"
            )

        return "   ".join(fmt)

    def process_message(self, message_data):
        """Process server message"""
        # NOTE: probably it's a good idea to move messages to separate python
        # module to be able to share message formats between server and client.
        # But it's not quite applicable for this toy server.
        # For message handling I would prefer some sort of data serialization
        # mechanism(google protocol buffers for example) rather than json.
        msg = json.loads(message_data)
        fmt_msg = self.fmt_message(msg)
        logger.info(fmt_msg)

    async def close(self):
        """Close client connection"""
        if self.ws_connection:
            await self.ws_connection.close()
        await self.session_client.close()

    async def send_request(self, msg):
        """async send data request to server"""
        await self.ws_connection.send_json(msg)

    async def receive_data(self, requests):
        """Process server received data"""
        run_forever = bool(requests == 0)
        request_counter = 0
        while not self.ws_connection.closed:
            if run_forever is False and request_counter >= requests:
                await self.close()
                break
            request_counter += 1

            msg = await self.ws_connection.receive()

            if msg.type == aiohttp.WSMsgType.TEXT:
                self.process_message(msg.data)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error(
                    'ws connection closed with exception %s',
                    await self.ws_connection.exception()
                )
                break
            elif msg.type == aiohttp.WSMsgType.CLOSE:
                await self.close()
                break
        logger.info("Connection closed")

    async def run(self, msg, requests):
        """Run client"""
        try:
            self.ws_connection = await self.session_client.ws_connect(
                self.address
            )
        except aiohttp.client_exceptions.ClientConnectorError as error:
            logger.error("Connection failed: %s", error)
            await self.close()
            return

        try:
            await self.send_request(msg)
            await self.receive_data(requests)
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()


async def shutdown(sig_no):
    """Shutdown active tasks"""
    logger.debug("Signal %s received", sig_no)
    pending = asyncio.Task.all_tasks()
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def main():
    """main"""
    import argparse
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "-a", "--addr", action="store", default="localhost", type=str
    )
    parser.add_argument(
        "-p", "--port", action="store", default=8080, type=int
    )
    parser.add_argument(
        "-t", "--timeout", action="store", default=1, type=float
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument('-n', "--requests", action="store", type=int, default=0)

    parser.add_argument("-c", "--cpu", action="store_true")
    parser.add_argument("-s", "--space", action="store_true")
    parser.add_argument("-m", "--mem", action="store_true")

    args = parser.parse_args()

    log_format = '%(message)s'
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format=log_format)
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)

    client = Client(args.addr, args.port)
    logger.info("Request info with %s seconds timeout", args.timeout)
    logger.info("Press Ctrl+C to stop")

    msg_format = vars(args)
    main_task = asyncio.gather(client.run(msg_format, args.requests))

    signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)

    loop = asyncio.get_event_loop()

    for sig_no in signals:
        loop.add_signal_handler(
            sig_no, lambda sig_no=sig_no: loop.create_task(shutdown(sig_no))
        )

    loop.run_until_complete(main_task)


if __name__ == '__main__':
    main()
