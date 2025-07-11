from scapy.all import AsyncSniffer, TCP, UDP, IP, raw
from cachetools import TTLCache
import logging
import time
import itertools


class MetricHeader:
    def __init__(self, name, unit="", type="", help=""):
        self.name = name
        self.unit = unit
        self.type = type
        self.help = help

    def __str__(self):
        string = ""
        if self.help != "":
            string += f"# HELP {self.name} {self.help}\n"
        if self.unit != "":
            string += f"# UNIT {self.name} {self.unit}\n"
        if self.type != "":
            string += f"# TYPE {self.name} {self.type}\n"
        return string

    def __repr__(self):
        return f"<MetricHeader name={self.name}>"

    def __eq__(self, value):
        return value.name == self.name

    def __ne__(self, value):
        return not self.__eq__(value)

    def __hash__(self):
        return self.name.__hash__()


class Metric:
    PACKETS_SENT_TOTAL = MetricHeader(
        "packets_sent_total",
        unit="bytes",
        type="counter",
        help="number of packets sent from this machine per connection",
    )
    PACKETS_RECEIVED_TOTAL = MetricHeader(
        "packets_received_total",
        unit="bytes",
        type="counter",
        help="number of packets received in this machine per connection",
    )
    BYTES_SENT_TOTAL = MetricHeader(
        "bytes_sent_total",
        unit="bytes",
        type="counter",
        help="number of bytes sent from this machine per connection",
    )
    BYTES_RECEIVED_TOTAL = MetricHeader(
        "bytes_received_total",
        unit="bytes",
        type="counter",
        help="number of packets received in this machine per connection",
    )
    PACKET_SENT_LOSS_TOTAL = MetricHeader(
        "packet_sent_loss_total",
        unit="",
        type="counter",
        help="number of sendingt packets lost per connection",
    )
    PACKET_RECEIVED_LOSS_TOTAL = MetricHeader(
        "packet_received_loss_total",
        unit="",
        type="counter",
        help="number of receiving packets lost per connection",
    )
    JITTER_TIME = MetricHeader(
        "jitter_time",
        unit="seconds",
        type="gauge",
        help="jitter time per connection",
    )

    def __init__(self, name, value, labels: dict = {}):
        self.name = name
        self.value = value
        self.labels: dict = labels

    def __str__(self):
        string = ""
        string += self.name
        if len(self.labels) > 0:
            string += "{"
            string += ",".join(f'{key}="{value}"' for key, value in self.labels.items())
            string += "} "
            string += str(self.value) + "\n"
        return string


class Connection:
    def __init__(self, src_ip, src_port, dst_ip, dst_port):
        self.src_ip = src_ip
        self.src_port = src_port
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.party1 = (src_ip, src_port)
        self.party2 = (dst_ip, dst_port)

    def __eq__(self, value):
        return (value.party1 == self.party1 and value.party2 == self.party2) or (
            value.party1 == self.party2 and value.party2 == self.party1
        )

    def __ne__(self, value):
        return not self.__eq__(value)

    def __hash__(self):
        return self.party1.__hash__() ^ self.party2.__hash__()

    def __str__(self):
        return (
            f"{self.party1[0]}:{self.party1[1]} <=> {self.party2[0]}:{self.party2[1]}"
        )

    __repr__ = __str__


class TcpConnectionMetrics:
    SEQS_ACKS_HISTORY_SIZE = 1000
    SEQS_ACKS_HISTORY_TTL = 60

    def __init__(self):
        self.packets_sent_total = 0
        self.packets_received_total = 0
        self.bytes_sent_total = 0
        self.bytes_received_total = 0
        self.packet_sent_loss_total = 0
        self.packet_received_loss_total = 0
        self.jitter_time = 0.0
        self._last_rtt = None  # Last RTT for jitter calculation
        self._rtt_samples = []  # Store RTT samples for jitter calculation
        self._sent_timestamps = {}  # Store timestamps of sent packets
        self._last_seq_number = 0
        self._last_win_size = 0
        self._sent_acks = TTLCache(
            maxsize=TcpConnectionMetrics.SEQS_ACKS_HISTORY_SIZE,
            ttl=TcpConnectionMetrics.SEQS_ACKS_HISTORY_TTL,
        )
        self._sent_seqs = TTLCache(
            maxsize=TcpConnectionMetrics.SEQS_ACKS_HISTORY_SIZE,
            ttl=TcpConnectionMetrics.SEQS_ACKS_HISTORY_TTL,
        )
        self._recieved_acks = TTLCache(
            maxsize=TcpConnectionMetrics.SEQS_ACKS_HISTORY_SIZE,
            ttl=TcpConnectionMetrics.SEQS_ACKS_HISTORY_TTL,
        )
        self._recieved_seqs = TTLCache(
            maxsize=TcpConnectionMetrics.SEQS_ACKS_HISTORY_SIZE,
            ttl=TcpConnectionMetrics.SEQS_ACKS_HISTORY_TTL,
        )

    def update_sent(self, packet_size, seq_number, win_size, ack):
        self.packets_sent_total += 1
        self.bytes_sent_total += packet_size
        self._sent_timestamps[seq_number] = (
            time.time()
        )  # Store the timestamp of the sent packet
        if seq_number in self._sent_seqs and ack in self._sent_acks:
            self.packet_sent_loss_total += 1
        self._sent_acks[ack] = 1
        self._sent_seqs[seq_number] = 1

    def update_received(self, packet_size, seq_number, win_size, ack):
        self.packets_received_total += 1
        self.bytes_received_total += packet_size
        rtt = self.calculate_rtt(seq_number)
        self.calculate_jitter(rtt)
        if seq_number in self._recieved_seqs and ack in self._recieved_acks:
            self.packet_received_loss_total += 1
        self._recieved_acks[ack] = 1
        self._recieved_seqs[seq_number] = 1

    def calculate_rtt(self, seq_number):
        if seq_number in self._sent_timestamps:
            sent_time = self._sent_timestamps.pop(
                seq_number
            )  # Remove the timestamp after using it
            rtt = time.time() - sent_time  # Calculate RTT
            self._last_rtt = rtt
            return rtt
        self._sent_timestamps[seq_number] = time.time()
        return None  # If no corresponding sent packet is found

    def calculate_jitter(self, rtt):
        if rtt is not None:
            self._rtt_samples.append(rtt)
            if len(self._rtt_samples) > 1:
                # Calculate jitter as the average deviation from the mean RTT
                mean_rtt = sum(self._rtt_samples) / len(self._rtt_samples)
                self.jitter_time = sum(
                    abs(rtt - mean_rtt) for rtt in self._rtt_samples
                ) / len(self._rtt_samples)

    def get_metrics(self):
        return {
            Metric.PACKETS_SENT_TOTAL: self.packets_sent_total,
            Metric.PACKETS_RECEIVED_TOTAL: self.packets_received_total,
            Metric.BYTES_SENT_TOTAL: self.bytes_sent_total,
            Metric.BYTES_RECEIVED_TOTAL: self.bytes_received_total,
            Metric.PACKET_SENT_LOSS_TOTAL: self.packet_sent_loss_total,
            Metric.PACKET_RECEIVED_LOSS_TOTAL: self.packet_received_loss_total,
            Metric.JITTER_TIME: self.jitter_time,
        }


class UdpConnectionMetrics:
    def __init__(self):
        self.packets_sent_total = 0
        self.packets_received_total = 0
        self.bytes_sent_total = 0
        self.bytes_received_total = 0

    def update_sent(self, packet_size):
        self.packets_sent_total += 1
        self.bytes_sent_total += packet_size

    def update_received(self, packet_size):
        self.packets_received_total += 1
        self.bytes_received_total += packet_size

    def get_metrics(self):
        return {
            Metric.PACKETS_SENT_TOTAL: self.packets_sent_total,
            Metric.PACKETS_RECEIVED_TOTAL: self.packets_received_total,
            Metric.BYTES_SENT_TOTAL: self.bytes_sent_total,
            Metric.BYTES_RECEIVED_TOTAL: self.bytes_received_total,
        }


class MetricSniffer:
    def __init__(self, src_ips=[], filter="", packet_callback: callable = None):
        if len(src_ips) != 0:
            self.src_ips = src_ips
        else:
            self.src_ips = self._get_all_ip_addresses()
        self.custom_packet_callback = packet_callback
        self.is_tcp = "tcp" in filter
        self.sniffer = AsyncSniffer(
            filter=filter, prn=self.packet_callback, store=False
        )
        logging.debug("start sniffing")
        self.sniffer.start()
        logging.debug(self.sniffer.running)
        logging.debug(self.sniffer)

        def print_thread_info():
            import threading

            # Get the list of all current threads
            threads = threading.enumerate()

            print("Active Threads:")
            for thread in threads:
                logging.debug(
                    f"Name: {thread.name}, ID: {thread.ident}, Daemon: {thread.daemon}, Alive: {thread.is_alive()}"
                )

        print_thread_info()

        # self.packets = []
        self.metrics = {}

    def _get_all_ip_addresses(self):
        import netifaces

        ip_addresses = {}
        interfaces = netifaces.interfaces()

        for interface in interfaces:
            addresses = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addresses:
                ip_addresses[interface] = [
                    addr["addr"] for addr in addresses[netifaces.AF_INET]
                ]

        return [
            self._ipv4tobytes(i) for i in list(itertools.chain(*ip_addresses.values()))
        ]

    def _ipv4tobytes(self, ip: str) -> bytes:
        return bytes(map(int, ip.split(".")))

    def join(self):
        self.sniffer.join()

    def stop(self):
        self.sniffer.stop()

    def packet_callback(self, packet):
        if self.custom_packet_callback is not None:
            self.custom_packet_callback(packet)

        if TCP in packet:
            src_ip = packet[IP].src
            src_port = packet[TCP].sport
            dst_ip = packet[IP].dst
            dst_port = packet[TCP].dport
            key = Connection(src_ip, src_port, dst_ip, dst_port)

            seq_number = packet[TCP].seq
            win_size = packet[TCP].window
            ack = packet[TCP].ack

            if key not in self.metrics:
                self.metrics[key] = TcpConnectionMetrics()

            # Update metrics based on whether the packet is sent or received
            if (
                self._ipv4tobytes(src_ip) in self.src_ips
            ):  # SYN flag indicates a sent packet
                self.metrics[key].update_sent(len(packet), seq_number, win_size, ack)
            else:  # Assume all other TCP packets are received
                self.metrics[key].update_received(
                    len(packet), seq_number, win_size, ack
                )
        elif UDP in packet:
            src_ip = packet[IP].src
            src_port = packet[UDP].sport
            dst_ip = packet[IP].dst
            dst_port = packet[UDP].dport
            key = Connection(src_ip, src_port, dst_ip, dst_port)

            logging.info("UDP")
            if key not in self.metrics:
                self.metrics[key] = UdpConnectionMetrics()

            # Update metrics based on whether the packet is sent or received
            if (
                self._ipv4tobytes(src_ip) in self.src_ips
            ):  # SYN flag indicates a sent packet
                self.metrics[key].update_sent(len(packet))
            else:  # Assume all other TCP packets are received
                self.metrics[key].update_received(len(packet))


if __name__ == "__main__":
    try:
        sniffer = MetricSniffer()
        sniffer.join()
    except KeyboardInterrupt:
        sniffer.stop()
    finally:
        pass
        # print(sniffer.packets)
