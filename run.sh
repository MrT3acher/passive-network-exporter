#!/bin/bash

set -a
source .env
set +a

python prometheus_http_sd.py