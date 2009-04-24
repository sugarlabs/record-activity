# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import gst

import logging
logger = logging.getLogger('record:aplay.py')

def play(file):
    player.set_state(gst.STATE_NULL)
    player.props.uri = 'file://' + file
    player.set_state(gst.STATE_PLAYING)

def _gstmessage_cb(bus, message):
    if message.type == gst.MESSAGE_EOS:
        player.set_state(gst.STATE_NULL)
    elif message.type == gst.MESSAGE_ERROR:
        err, debug = message.parse_error()
        logger.error('play_pipe: %s %s' % (err, debug))
        player.set_state(gst.STATE_NULL)

player = gst.element_factory_make('playbin')
fakesink = gst.element_factory_make('fakesink')
player.set_property("video-sink", fakesink)

bus = player.get_bus()
bus.add_signal_watch()
bus.connect('message', _gstmessage_cb)
