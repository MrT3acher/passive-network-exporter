from flask import Flask, Response
import dotenv
import waitress
import netifaces
import os
import json
import datetime

from prometheus_exporter import Exporter


class ExporterSet:
    def __init__(
        self, listen_host="0.0.0.0", listen_port=5000, debug=False, external_host=""
    ):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.next_exporter_listen_port = listen_port + 1
        self.debug = debug
        self.external_host = (
            external_host if external_host != "" else self._get_primary_ip()
        )

        self.exporters = []

        self._setup_flask()

    def _get_primary_ip(self):
        interfaces = netifaces.interfaces()
        for interface in interfaces:
            # Get the addresses associated with the interface
            addresses = netifaces.ifaddresses(interface)
            # Check if the interface has an IPv4 address
            if netifaces.AF_INET in addresses:
                ip_address = addresses[netifaces.AF_INET][0]["addr"]
                # Ignore loopback addresses
                if not ip_address.startswith("127."):
                    return ip_address
        return "127.0.0.1"  # No valid IP found

    def _setup_flask(self):
        self.app = Flask(__name__)

        # urls
        self.app.add_url_rule(rule="/sd", view_func=self.sd)

    def run(self):
        for exporter in self.exporters:
            exporter.run(thread=True)

        waitress.serve(self.app, host=self.listen_host, port=self.listen_port)

    def sd(self):
        response = []
        for exporter in self.exporters:
            response.append(
                {
                    "targets": [f"{self.external_host}:{exporter.listen_port}"],
                    "labels": {
                        "instance_name": exporter.name,
                        "start_time": datetime.datetime.now(),
                    },
                }
            )
        return Response(json.dumps(response), mimetype="application/json")

    def new_exporter(self, name, packet_filter):
        exporter = Exporter(
            name, self.next_exporter_listen_port, self.debug, packet_filter
        )
        self.exporters.append(exporter)
        self.next_exporter_listen_port += 1


if __name__ == "__main__":
    if "PACKET_FILTER_" not in str(os.environ.items()):
        dotenv.load_dotenv()
        
    LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
    LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "5000"))
    DEBUG = bool(os.environ.get("DEBUG", "0"))
    EXTERNAL_HOST = os.environ.get("EXTERNAL_HOST", "")

    exporter_set = ExporterSet(
        listen_host=LISTEN_HOST,
        listen_port=LISTEN_PORT,
        debug=DEBUG,
        external_host=EXTERNAL_HOST,
    )
    for name, value in os.environ.items():
        if name.startswith("PACKET_FILTER_"):
            name = name.removeprefix("PACKET_FILTER_")
            exporter_set.new_exporter(name, value)
    exporter_set.run()
