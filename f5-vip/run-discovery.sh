#!/bin/bash
source /config/failover/f5-vip/venv/bin/activate
python /config/failover/f5-vip/f5-vip-discovery.py "$@"