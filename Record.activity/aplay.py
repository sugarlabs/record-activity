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
import os
import logging
import constants

logger = logging.getLogger('record:aplay.py')

def play(file, done_cb=None):
    player.set_state(gst.STATE_NULL)

    def eos_cb(bus, message):
        bus.disconnect_by_func(eos_cb)
        player.set_state(gst.STATE_NULL)
        if done_cb is not None:
            done_cb()

    def error_cb(bus, message):
        err, debug = message.parse_error()
        logger.error('play_pipe: %s %s' % (err, debug))
        player.set_state(gst.STATE_NULL)
        if done_cb is not None:
            done_cb()

    bus = player.get_bus()
    bus.connect('message::eos', eos_cb)
    bus.connect('message::error', error_cb)

    player.props.uri = 'file://' + os.path.join(constants.GFX_PATH, file)
    player.set_state(gst.STATE_PLAYING)


player = gst.element_factory_make('playbin')
fakesink = gst.element_factory_make('fakesink')
player.set_property("video-sink", fakesink)
player.get_bus().add_signal_watch()
