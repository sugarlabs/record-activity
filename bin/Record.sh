#!/bin/sh
root=`cd $(dirname $0)/..; pwd`
export GST_PLUGIN_PATH="$GST_PLUGIN_PATH:$root/gst"
exec sugar-activity record.Record "$@"
