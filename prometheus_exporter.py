from flask import Flask, Response
import waitress
import os
import threading

from metrics import (
    MetricSniffer,
    TcpConnection,
    TcpConnectionMetrics,
    Metric,
    MetricHeader,
)


class Exporter:
    def __init__(self, name, listen_port=5000, debug=False, packet_filter=""):
        self.name = name
        self.listen_port = listen_port
        self.debug = debug
        self.packet_filter = (
            "tcp" if packet_filter == "" else f"tcp and {packet_filter}"
        )

        self._setup_flask()

    def _setup_flask(self):
        self.app = Flask(self.name)
        
        # urls
        self.app.add_url_rule(rule="/metrics", view_func=self.metrics)

    def _thread_target(self, *args, **kwargs):
        waitress.serve(self.app, *args, **kwargs)

    def run(self, thread=False):
        self.sniffer = MetricSniffer(filter=self.packet_filter)
        kwargs = {"host": "0.0.0.0", "port": self.listen_port}
        if thread:
            self.thread = threading.Thread(name=self.name, target=self._thread_target, kwargs=kwargs)
            self.thread.start()
        else:
            self.app.run(debug=self.debug, **kwargs)
            
    def join(self):
        self.thread.join()
        
    def stop(self):
        self.thread._stop()

    def metrics(self):
        """Endpoint to serve metrics in Prometheus format."""
        classified_metrics = {}
        for tcp_connection in self.sniffer.metrics:
            tcp_connection: TcpConnection = tcp_connection
            metrics: TcpConnectionMetrics = self.sniffer.metrics[tcp_connection]

            metrics = metrics.get_metrics()
            for header in metrics:
                if header not in classified_metrics:
                    classified_metrics[header] = []
                classified_metrics[header].append(
                    Metric(
                        header.name,
                        metrics[header],
                        {
                            # "name": self.name,
                            "src_ip": tcp_connection.src_ip,
                            "src_port": tcp_connection.src_port,
                            "dst_ip": tcp_connection.dst_ip,
                            "dst_port": tcp_connection.dst_port,
                        },
                    )
                )
        response = ""
        for header in classified_metrics:
            response += str(header)
            for metric in classified_metrics[header]:
                response += str(metric)
        return Response(response, mimetype="text/plain")


if __name__ == "__main__":
    LISTEN_PORT = os.environ.get("LISTEN_PORT", "5000")
    DEBUG = bool(os.environ.get("DEBUG", "0"))
    PACKET_FILTER = os.environ.get("PACKET_FILTER", "tcp")

    exporter = Exporter(LISTEN_PORT, DEBUG, PACKET_FILTER)
    exporter.run()
