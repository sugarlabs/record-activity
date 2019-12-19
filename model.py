# Copyright (c) 2008, Media Modifications Ltd.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# -*- coding: utf-8 -*-

from gettext import gettext as _
from xml.dom.minidom import parse
import logging
import uuid
import os
import time
import json

from gi.repository import GLib, Gst

import sugar3.profile
import sugar3.env

import aplay
import constants
from instance import Instance
from recorded import Recorded
import utils
import serialize
from collab import RecordCollab
from glive import Glive
from gplay import Gplay

logger = logging.getLogger('model')


class Model:
    def __init__(self, activity_obj):
        self.activity = activity_obj

        self.collab = RecordCollab(self.activity, self)
        self.glive = Glive(self.activity, self)
        self.gplay = Gplay(self.activity)
        self.gplay.connect('playback-status-changed',
                           self._playback_status_changed)

        self._mode = None
        self._state = constants.STATE_INVISIBLE
        self._countdown_handle = None
        self._countdown_ends = None
        self._timer_value = 0
        self._timer_duration = 0
        self._timer_handle = None
        self._visible = False

        self.mediaHashs = {}
        for key, value in list(constants.MEDIA_INFO.items()):
            self.mediaHashs[key] = []

    def close(self):
        self.gplay.stop()
        self.glive.stop()

    def write_file(self, path):
        ui_serialized = self.activity.serialize()
        self.mediaHashs['ui'] = ui_serialized
        dom = serialize.saveMediaHash(self.mediaHashs, self.activity)
        ui_data = json.dumps(ui_serialized)
        ui_el = dom.createElement('ui')
        ui_el.appendChild(dom.createTextNode(ui_data))
        dom.documentElement.appendChild(ui_el)

        fd = open(path, "w")
        dom.writexml(fd)
        fd.close()

    def read_file(self, path):
        try:
            dom = parse(path)
        except Exception as e:
            logger.error('read_file: %s' % e)
            return

        serialize.fillMediaHash(dom, self.mediaHashs)
        for i in dom.documentElement.getElementsByTagName('ui'):
            for ui_el in i.childNodes:
                self.activity.deserialize(json.loads(ui_el.data))

        for key, value in list(constants.MEDIA_INFO.items()):
            for recd in self.mediaHashs[key]:
                self.activity.add_thumbnail(recd)
        # FIXME: side-effect thumbnails sorted by type on resume

    def get_cameras(self):
        return self.glive.get_cameras()

    def switch_camera(self):
        self.glive.switch_camera()

    def set_mirror(self, mirror):
        self.glive.set_mirror(mirror)

    def get_nickname(self):
        return sugar3.profile.get_nick_name()

    def get_mode(self):
        return self._mode

    def change_mode(self, mode):
        if mode == self._mode:
            return

        self._mode = mode

        self.activity.set_mode(mode)
        self.set_state(constants.STATE_READY)

    def ui_frozen(self):
        return not self._state == constants.STATE_READY

    def set_visible(self, visible):
        if visible == self._visible:
            return

        self._visible = visible

        if visible:
            self.set_state(constants.STATE_READY)
            return

        self.abort_countdown()

        # Change from visible to invisible.
        if self._state == constants.STATE_RECORDING:
            # If recording, stop.
            self._stop_media_capture()
        else:
            self.set_state(constants.STATE_INVISIBLE)

    def set_state(self, state):
        self.abort_countdown()

        # Never go into READY mode if we aren't visible.
        if state == constants.STATE_READY and not self._visible:
            logging.debug("state: overriding READY to INVISIBLE")
            state = constants.STATE_INVISIBLE

        self._state = state

        if state == constants.STATE_READY:
            self.gplay.stop()
            self.glive.play()
        elif state == constants.STATE_INVISIBLE:
            self.gplay.stop()
            self.glive.stop()

        self.activity.set_state(state)

    def get_state(self):
        return self._state

    def set_progress(self, value, text):
        self.activity.set_progress(value, text)

    def _timer_tick(self):
        self._timer_value = self._timer_value - 1
        value = self._timer_value
        progress_value = 1 - (float(value) / float(self._timer_duration))

        mins = value / 60
        secs = value % 60
        text = _('%(mins)d:%(secs)02d remaining') % \
            {'mins': mins, 'secs': secs}

        self.set_progress(progress_value, text)

        if self._timer_value <= 0:
            self._timer_handle = None
            self._timer_value = 0
            self._stop_media_capture()
            return False

        return True

    def _start_media_capture(self):
        if self._mode == constants.MODE_PHOTO:
            self.activity.set_shutter_sensitive(False)
            self.glive.take_photo()
            return

        self.set_progress(0, '')
        self._timer_value = self.activity.get_selected_duration()
        self._timer_duration = self._timer_value
        self._timer_handle = GLib.timeout_add(1000, self._timer_tick)

        self.activity.set_shutter_sensitive(True)
        self.set_state(constants.STATE_RECORDING)

        if self._mode == constants.MODE_VIDEO:
            quality = self.activity.get_selected_quality()
            self.glive.record_video(quality)
        elif self._mode == constants.MODE_AUDIO:
            self.glive.record_audio()

    def _stop_media_capture(self):
        if self._timer_handle:
            GLib.source_remove(self._timer_handle)
            self._timer_handle = None
            self._timer_value = 0

        self.set_progress(0, '')

        if self._mode == constants.MODE_VIDEO:
            self.glive.stop_recording_video()
        elif self._mode == constants.MODE_AUDIO:
            self.glive.stop_recording_audio()

        self.set_state(constants.STATE_PROCESSING)

    def shutter_sound(self, done_cb=None):
        aplay.play('photoShutter.wav', done_cb)

    def _countdown_tick(self):
        remaining = self._countdown_ends - time.time()
        if remaining < 0:
            self.activity.set_countdown(0)
            self.shutter_sound(self._start_media_capture)
            self._countdown_handle = None
            return False

        self.activity.set_countdown(int(remaining + 1))
        return True

    def do_shutter(self):
        # if recording, stop
        if self._state == constants.STATE_RECORDING:
            self._stop_media_capture()
            return

        # if timer is selected, start countdown
        timer = self.activity.get_selected_timer()
        if timer > 0:
            self.activity.set_shutter_sensitive(False)
            value = self.activity.get_selected_timer()
            self.activity.set_countdown(value)
            self._countdown_ends = time.time() + value
            self._countdown_handle = GLib.timeout_add(
                100, self._countdown_tick)
            return

        # otherwise, capture normally
        self.shutter_sound(self._start_media_capture)

    def abort_countdown(self):
        if self._countdown_handle:
            GLib.source_remove(self._countdown_handle)
            self._countdown_handle = None
            self.activity.set_countdown(0)

    # called from GStreamer thread
    def still_ready(self, pixbuf):
        GLib.idle_add(self.activity.show_still, pixbuf)

    def add_recd(self, recd):
        self.mediaHashs[recd.type].append(recd)
        self.activity.add_thumbnail(recd)

        if not recd.buddy:
            self.collab.share_recd(recd)

    # called from GStreamer thread
    def save_photo(self, pixbuf):
        recd = self.createNewRecorded(constants.TYPE_PHOTO)

        imgpath = os.path.join(Instance.instancePath, recd.mediaFilename)
        pixbuf.savev(imgpath, "jpeg", [], [])

        pixbuf = utils.generate_thumbnail(pixbuf)
        pixbuf.savev(recd.make_thumb_path(), "png", [], [])

        # now that we've saved both the image and its pixbuf, we get their md5s
        self.createNewRecordedMd5Sums(recd)

        GLib.idle_add(self.add_recd, recd, priority=GLib.PRIORITY_HIGH)
        GLib.idle_add(self.activity.set_shutter_sensitive, True,
                      priority=GLib.PRIORITY_HIGH)

    # called from GStreamer thread
    def save_video(self, path, still):
        recd = self.createNewRecorded(constants.TYPE_VIDEO)
        os.rename(path, os.path.join(Instance.instancePath,
                                     recd.mediaFilename))

        image_path = os.path.join(Instance.instancePath, "videoPicture.png")
        image_path = utils.getUniqueFilepath(image_path, 0)
        still.savev(image_path, "png", [], [])
        recd.videoImageFilename = os.path.basename(image_path)

        still = utils.generate_thumbnail(still)
        still.savev(recd.make_thumb_path(), "png", [], [])

        self.createNewRecordedMd5Sums(recd)

        GLib.idle_add(self.add_recd, recd, priority=GLib.PRIORITY_HIGH)
        GLib.idle_add(self.set_state, constants.STATE_READY)

    def save_audio(self, path, still):
        recd = self.createNewRecorded(constants.TYPE_AUDIO)
        os.rename(path, os.path.join(Instance.instancePath,
                                     recd.mediaFilename))

        if still:
            image_path = os.path.join(Instance.instancePath,
                                      "audioPicture.png")
            image_path = utils.getUniqueFilepath(image_path, 0)
            still.savev(image_path, "png", [], [])
            recd.audioImageFilename = os.path.basename(image_path)

            still = utils.generate_thumbnail(still)
            still.savev(recd.make_thumb_path(), "png", [], [])

        self.createNewRecordedMd5Sums(recd)

        GLib.idle_add(self.add_recd, recd, priority=GLib.PRIORITY_HIGH)
        GLib.idle_add(self.set_state, constants.STATE_READY)

    def _playback_status_changed(self, widget, status, value):
        self.activity.set_playback_scale(value)
        if status == Gst.State.NULL:
            self.activity.set_paused(True)

    def play_audio(self, recd):
        self.gplay.set_location("file://" + recd.getMediaFilepath())
        self.gplay.play()
        self.activity.set_paused(False)

    def play_video(self, recd):
        self.gplay.set_location("file://" + recd.getMediaFilepath())
        self.gplay.play()
        self.activity.set_paused(False)

    def play_pause(self):
        if self.gplay.get_state() == Gst.State.PLAYING:
            self.gplay.pause()
            self.activity.set_paused(True)
        else:
            self.gplay.play()
            self.activity.set_paused(False)

    def seek_start(self):
        self.gplay.pause()

    def seek_do(self, position):
        self.gplay.seek(position)

    def seek_end(self):
        self.gplay.play()

    def get_recd_by_md5(self, md5):
        for mh in list(self.mediaHashs.values()):
            for recd in mh:
                if recd.thumbMd5 == md5 or recd.mediaMd5 == md5:
                    return recd

        return None

    def createNewRecorded(self, type):
        recd = Recorded()

        recd.recorderName = self.get_nickname()
        recd.recorderHash = Instance.keyHashPrintable

        # to create a file, use the hardware_id+time *and* check if
        # available or not
        nowtime = int(time.time())
        recd.time = nowtime
        recd.type = type

        mediaThumbFilename = str(recd.recorderHash) + "_" + str(recd.time)
        mediaFilename = mediaThumbFilename
        mediaFilename = mediaFilename + "." + constants.MEDIA_INFO[type]['ext']
        mediaFilepath = os.path.join(Instance.instancePath,
                                     mediaFilename)
        mediaFilepath = utils.getUniqueFilepath(mediaFilepath, 0)
        recd.mediaFilename = os.path.basename(mediaFilepath)

        stringType = constants.MEDIA_INFO[type]['istr']

        # Translators: photo by photographer, e.g. "Photo by Mary"
        recd.title = _('%(type)s by %(name)s') % \
            {'type': stringType, 'name': recd.recorderName}

        color = sugar3.profile.get_color()
        recd.colorStroke = color.get_stroke_color()
        recd.colorFill = color.get_fill_color()

        logger.debug('createNewRecorded: ' + str(recd))
        return recd

    def createNewRecordedMd5Sums(self, recd):
        recd.thumbMd5 = recd.mediaMd5 = str(uuid.uuid4())

        # load the thumbfile
        if recd.thumbFilename:
            thumbFile = os.path.join(Instance.instancePath, recd.thumbFilename)
            recd.thumbBytes = os.stat(thumbFile)[6]

        recd.tags = ""

        # load the mediafile
        mediaFile = os.path.join(Instance.instancePath, recd.mediaFilename)
        mBytes = os.stat(mediaFile)[6]
        recd.mediaBytes = mBytes

    def delete_recd(self, recd):
        recd.deleted = True
        self.mediaHashs[recd.type].remove(recd)

        if recd.meshUploading:
            return

        # remove files from the filesystem if not on the datastore
        if recd.datastoreId is None:
            mediaFile = recd.getMediaFilepath()
            if os.path.exists(mediaFile):
                os.remove(mediaFile)

            thumbFile = recd.getThumbFilepath()
            if thumbFile and os.path.exists(thumbFile):
                os.remove(thumbFile)
        else:
            # remove from the datastore here, since once gone, it is gone...
            serialize.removeMediaFromDatastore(recd)

    def request_download(self, recd):
        self.activity.show_still(recd.getThumbPixbuf())
        self.set_state(constants.STATE_DOWNLOADING)
        self.collab.request_download(recd)
        self.activity.update_download_progress(recd)
