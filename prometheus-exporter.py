from flask import Flask, Response
import threading
import time
import random

from metrics import (
    MetricSniffer,
    TcpConnection,
    TcpConnectionMetrics,
    Metric,
)

app = Flask(__name__)


# Global variable to store metrics
metrics_data = {"requests_total": 0, "random_value": 0}


@app.route("/metrics")
def metrics():
    """Endpoint to serve metrics in Prometheus format."""
    classified_metrics = {}
    for tcp_connection in sniffer.metrics:
        tcp_connection: TcpConnection = tcp_connection
        metrics: TcpConnectionMetrics = sniffer.metrics[tcp_connection]

        metrics = metrics.get_metrics()
        for header in metrics:
            if header not in classified_metrics:
                classified_metrics[header] = []
            classified_metrics[header].append(
                Metric(
                    header.name,
                    metrics[header],
                    {
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
    # Start the background thread
    sniffer = MetricSniffer(filter="tcp")

    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=True)
