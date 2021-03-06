# -*- encoding: utf-8 -*-
import json

import sys
import asyncio
import asyncio.streams


def validate_package(data):
    try:
        result = True
        assert data and isinstance(data, dict)
        assert 'command' in data
        assert 'data' in data
    except AssertionError:
        result = False
    return result

class MyServer(object):
    """
    This is just an example of how a TCP server might be potentially
    structured.  This class has basically 3 methods: start the server,
    handle a client, and stop the server.

    Note that you don't have to follow this structure, it is really
    just an example or possible starting point.
    """

    def __init__(self):
        self.server = None  # encapsulates the server sockets

        # this keeps track of all the clients that connected to our
        # server.  It can be useful in some cases, for instance to
        # kill client connections or to broadcast some data to all
        # clients...
        self.clients = {} # task -> (reader, writer)

        self._commands = {}
        self._add_command_processing('SUM2', self._command_sum2)

    @asyncio.coroutine
    def _processing(self, data):
        try:
            assert data['command'] in self._commands, \
                "Not found command(%s) in list" % data['command']
            result = {
                'ok': True,
                'result': self._commands[data['command']](data['command'],
                                                          data['data'])
            }
        except Exception as e:
            result = {'error': str(e) if e else 'empty error', 'ok': False}

        return result

    def _command_sum2(self, command: str, data: dict):
        assert 'arg1' in data.keys(), "Not found argument arg1"
        assert 'arg2' in data.keys(), "Not found argument arg2"
        assert isinstance(data['arg1'], (int, float)), "arg1 is not number"
        assert isinstance(data['arg2'], (int, float)), 'arg2 is not number'
        return data['arg1'] + data['arg2']

    def _add_command_processing(self, command, func):
        self._commands[command] = func

    def _accept_client(self, client_reader, client_writer):
        """
        This method accepts a new client connection and creates a Task
        to handle this client.  self.clients is updated to keep track
        of the new client.
        """

        # start a new Task to handle this specific client connection
        task = asyncio.Task(self._handle_client(client_reader, client_writer))
        self.clients[task] = (client_reader, client_writer)

        def client_done(task):
            print("client task done:", task, file=sys.stderr)
            del self.clients[task]

        task.add_done_callback(client_done)

    @asyncio.coroutine
    def _handle_client(self, client_reader, client_writer):
        """
        This method actually does the work to handle the requests for
        a specific client.  The protocol is line oriented, so there is
        a main loop that reads a line with a request and then sends
        out one or more lines back to the client with the result.
        """
        while True:
            data = (yield from client_reader.readline()).decode("utf-8")
            if not data: # an empty string means the client disconnected
                break

            msg = data.rstrip()
            if msg and isinstance(msg, str):
                try:
                    msg_data = json.loads(msg)
                    self._log(msg_data)

                    assert validate_package(
                        msg_data), "Not valid package from client"

                    result = yield from self._processing(msg_data)
                except (AssertionError, ValueError) as e:
                    result = {
                        'ok': False,
                        'error': str(e),
                    }
                client_writer.write("{!r}\n".format(json.dumps(result)).encode("utf-8"))
            # This enables us to have flow control in our connection.
            yield from client_writer.drain()

    def _log(self, *args, **kwargs):
        print(*args, **kwargs)

    def start(self, loop):
        """
        Starts the TCP server, so that it listens on port 12345.

        For each client that connects, the accept_client method gets
        called.  This method runs the loop until the server sockets
        are ready to accept connections.
        """
        self._log("Server started...")
        self.server = loop.run_until_complete(
            asyncio.streams.start_server(self._accept_client,
                                         '127.0.0.1', 12345,
                                         loop=loop))

    def stop(self, loop):
        """
        Stops the TCP server, i.e. closes the listening socket(s).

        This method runs the loop until the server sockets are closed.
        """
        if self.server is not None:
            self.server.close()
            loop.run_until_complete(self.server.wait_closed())
            self.server = None

            self._log("Server stopped...")


def main():
    loop = asyncio.get_event_loop()

    # creates a server and starts listening to TCP connections
    server = MyServer()
    server.start(loop)
    # creates a client and connects to our server
    try:
        loop.run_forever()
        server.stop(loop)
    finally:
        loop.close()


if __name__ == '__main__':
    main()