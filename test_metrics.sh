#!/bin/bash
set -e

echo "Testing API metrics endpoint..."
curl -s localhost:8727/metrics | grep "render_duration_seconds" > /dev/null
echo "✓ render_duration_seconds exists in API"

echo "Testing Worker metrics endpoint..."
curl -s localhost:8729/metrics | grep "render_duration_seconds_count" > /dev/null
echo "✓ render_duration_seconds_count exists in Worker"

echo "Testing Dispatcher metrics endpoint..."
curl -s localhost:8728/metrics | grep "listener_reconnects_total" > /dev/null
echo "✓ listener_reconnects_total exists in Dispatcher"

echo "All Phase 3 metrics endpoints verified!"
