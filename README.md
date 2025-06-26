# How to use?
1. install python 3.12 or above (deadsnakes repositories recommended)
2. create virtualenv:
```
python -m venv .venv
```
3. activate virtualenv and install requirements:
```
source .venv/bin/activate
pip install -r requirements.txt
```
4. set `.env` values:
```
DEBUG=0
LISTEN_PORT=5000
EXTERNAL_HOST=192.168.1.100
PACKET_FILTER_CAMERA=net 192.168.12.0/24 and port 8554
PACKET_FILTER_AI=net 172.16.0.0/16 and port 8554
PACKET_FILTER_USER=(net 192.168.10.0/24 or net 192.168.11.0/24) and port 8555
```
* **DEBUG:** will print more verbose and write more verbose on `logs.log` and enable flask debug if equal to `1`.
* **LISTEN_PORT:** this is http_sd service port, exporters will be run on 5001, 5002, 5003, and so on. one exporter per PACKET_FILTER_* will be run.
* **EXTERNAL_HOST:** external ip which web services are available on.
* **PACKET_FILTER_*:** BPF filter that specifies number of exporter instances (one instance will be run per each PACKET_FILTER_*). this way you can set name for your instances by custom network filter you need.
5. run the code:
```
./run.sh
```
6. add this config to promethus config file:
```
scrape_configs:
- job_name: passive_network_exporter
  http_sd_configs:
  - url: http://172.16.1.145:5000/sd
```
7. finally restart promethues to take effect and enjoy the metrics 😁

# Example metrics
```
# HELP packets_sent_total number of packets sent from this machine per connection
# UNIT packets_sent_total bytes
# TYPE packets_sent_total counter
packets_sent_total{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 355
packets_sent_total{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 485
# HELP packets_received_total number of packets received in this machine per connection
# UNIT packets_received_total bytes
# TYPE packets_received_total counter
packets_received_total{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 452
packets_received_total{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 501
# HELP bytes_sent_total number of bytes sent from this machine per connection
# UNIT bytes_sent_total bytes
# TYPE bytes_sent_total counter
bytes_sent_total{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 24047
bytes_sent_total{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 32603
# HELP bytes_received_total number of packets received in this machine per connection
# UNIT bytes_received_total bytes
# TYPE bytes_received_total counter
bytes_received_total{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 909728
bytes_received_total{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 1184192
# HELP packet_sent_loss_total number of sendingt packets lost per connection
# TYPE packet_sent_loss_total counter
packet_sent_loss_total{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 3
packet_sent_loss_total{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 2
# HELP packet_received_loss_total number of receiving packets lost per connection
# TYPE packet_received_loss_total counter
packet_received_loss_total{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 3
packet_received_loss_total{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 1
# HELP jitter_time jitter time per connection
# UNIT jitter_time seconds
# TYPE jitter_time gauge
jitter_time{src_ip="172.22.228.245",src_port="57888",dst_ip="172.25.12.12",dst_port="8554"} 0.008193174997965494
jitter_time{src_ip="172.22.228.245",src_port="34630",dst_ip="172.25.12.12",dst_port="8554"} 0.0
```
