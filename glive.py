#Copyright (c) 2008, Media Modifications Ltd.

#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:

#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.

#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

import os
from gettext import gettext as _
import time

from gi.repository import GLib, GObject, Gst, GdkX11, GstVideo, GdkPixbuf

from sugar3.activity.activity import get_bundle_path
import logging

from instance import Instance
import constants
import utils

logger = logging.getLogger('glive')

class Glive:
    PHOTO_MODE_PHOTO = 0
    PHOTO_MODE_AUDIO = 1

    def __init__(self, activity_obj, model):
        self.activity = activity_obj
        self.model = model
        self._eos_cb = None

        self._has_camera = False
        self._playing = False
        self._pic_exposure_open = False
        self._thumb_exposure_open = False
        self._photo_mode = self.PHOTO_MODE_PHOTO

        self._audio_transcode_handler = None
        self._transcode_id = None
        self._video_transcode_handler = None
        self._thumb_handoff_handler = None

        self._audio_pixbuf = None

        self._detect_camera()

        self._create_photobin()
        self._create_audiobin()
        self._create_videobin()
        self._create_pipeline()

        self._thumb_pipes = []
        self._mux_pipes = []

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.enable_sync_message_emission()
        bus.connect('message', self._bus_message_handler)

        self._xid = None
        self._sink = None

        def on_sync_message_cb(bus, msg):
            if msg.get_structure().get_name() == 'prepare-window-handle':
                self.activity.set_glive_sink(msg.src)

        bus.connect('sync-message::element', on_sync_message_cb)

    def _detect_camera(self):
        self._has_camera = True

    def get_has_camera(self):
        return self._has_camera

    def _create_photobin(self):
        queue = Gst.ElementFactory.make("queue", "pbqueue")
        if queue is None:
            logger.error('no queue')

        queue.set_property("leaky", True)
        queue.set_property("max-size-buffers", 1)

        vc = Gst.ElementFactory.make("videoconvert", "videoconvert")
        if vc is None:
            logger.error('no videoconvert')

        jpeg = Gst.ElementFactory.make("jpegenc", "pbjpeg")
        if jpeg is None:
            logger.error('no jpegenc')

        sink = Gst.ElementFactory.make("fakesink", "pbsink")
        if sink is None:
            logger.error('no fakesink')

        sink.connect("handoff", self._photo_handoff)
        sink.set_property("signal-handoffs", True)

        self._photobin = Gst.Bin("photobin")
        self._photobin.add(queue)
        self._photobin.add(vc)
        self._photobin.add(jpeg)
        self._photobin.add(sink)

        queue.link(vc)
        vc.link(jpeg)
        jpeg.link(sink)

        pad = queue.get_static_pad("sink")
        self._photobin.add_pad(Gst.GhostPad("sink", pad))

    def _create_audiobin(self):
        src = Gst.ElementFactory.make("autoaudiosrc", "absrc")
        if src is None:
            logger.error('no autoaudiosrc')

        # guarantee perfect stream, important for A/V sync
        rate = Gst.ElementFactory.make("audiorate")
        if rate is None:
            logger.error('no audiorate')

        # without a buffer here, GStreamer struggles at the start of the
        # recording and then the A/V sync is bad for the whole video
        # (possibly a GStreamer/ALSA bug -- even if it gets caught up, it
        # should be able to resync without problem)
        queue = Gst.ElementFactory.make("queue", "abqueue")
        if queue is None:
            logger.error('no queue')

        queue.set_property("leaky", True) # prefer fresh data
        queue.set_property("max-size-time", 5000000000) # 5 seconds
        queue.set_property("max-size-buffers", 500)
        queue.connect("overrun", self._log_queue_overrun)

        enc = Gst.ElementFactory.make("wavenc", "abenc")
        if enc is None:
            logger.error('no wavenc')

        sink = Gst.ElementFactory.make("filesink", "absink")
        if sink is None:
            logger.error('no filesink')

        sink.set_property("location",
                          os.path.join(Instance.instancePath, "output.wav"))

        self._audiobin = Gst.Bin("audiobin")
        self._audiobin.add(src)
        self._audiobin.add(rate)
        self._audiobin.add(queue)
        self._audiobin.add(enc)
        self._audiobin.add(sink)

        if not src.link(rate):
            logger.error('src link to rate failed')
        if not rate.link(queue):
            logger.error('rate link to queue failed')
        if not queue.link(enc):
            logger.error('queue link to enc failed')
        if not enc.link(sink):
            logger.error('enc link to sink failed')

    def _create_videobin(self):
        queue = Gst.ElementFactory.make("queue", "videoqueue")
        if queue is None:
            logger.error('no queue')

        queue.set_property("max-size-time", 5000000000) # 5 seconds
        queue.set_property("max-size-bytes", 128 * 1024 * 1024)
        queue.connect("overrun", self._log_queue_overrun)

        vc = Gst.ElementFactory.make("videoconvert", "vc")
        if vc is None:
            logger.error('no videoconvert')

        enc = Gst.ElementFactory.make("theoraenc", "vbenc")
        if enc is None:
            logger.error('no theoraenc')

        enc.set_property("quality", 16)

        mux = Gst.ElementFactory.make("oggmux", "vbmux")
        if mux is None:
            logger.error('no oggmux')

        sink = Gst.ElementFactory.make("filesink", "vbfile")
        if sink is None:
            logger.error('no filesink')

        sink.set_property("location", os.path.join(Instance.instancePath, "output.ogg"))

        self._videobin = Gst.Bin("videobin")
        self._videobin.add(queue)
        self._videobin.add(vc)
        self._videobin.add(enc)
        self._videobin.add(mux)
        self._videobin.add(sink)

        if not queue.link(vc):
            logger.error('queue link to vc failed')
        if not vc.link(enc):
            logger.error('vc link to enc failed')
        if not enc.link(mux):
            logger.error('enc link to mux failed')
        if not mux.link(sink):
            logger.error('mux link to sink failed')

        pad = queue.get_static_pad("sink")
        self._videobin.add_pad(Gst.GhostPad("sink", pad))

    def _create_pipeline(self):
        cmd = 'autovideosrc name=src ' \
            '! tee name=tee ' \
            'tee.! queue ! videoconvert ! autovideosink '
        self._pipeline = Gst.parse_launch(cmd)

    def _log_queue_overrun(self, queue):
        cbuffers = queue.get_property("current-level-buffers")
        cbytes = queue.get_property("current-level-bytes")
        ctime = queue.get_property("current-level-time")
        logger.error("Buffer overrun in %s (%d buffers, %d bytes, %d time)"
            % (queue.get_name(), cbuffers, cbytes, ctime))
 
    def _thumb_element(self, name):
        return self._thumb_pipes[-1].get_by_name(name)

    def play(self):
        if self._get_state() == Gst.State.PLAYING:
            return

        self._pipeline.set_state(Gst.State.PLAYING)
        self._playing = True

    def pause(self):
        self._pipeline.set_state(Gst.State.PAUSED)
        self._playing = False

    def stop(self):
        self._pipeline.set_state(Gst.State.NULL)
        self._playing = False

    def is_playing(self):
        return self._playing

    def _get_state(self):
        return self._pipeline.get_state(Gst.CLOCK_TIME_NONE)[1]

    def stop_recording_audio(self):
        # We should be able to simply pause and remove the audiobin, but
        # this seems to cause a GStreamer segfault. So we stop the whole
        # pipeline while manipulating it.
        # http://dev.laptop.org/ticket/10183
        self._pipeline.set_state(Gst.State.NULL)
        self.model.shutter_sound(self._stop_recording_audio)

    def _stop_recording_audio(self):
        self._pipeline.remove(self._audiobin)

        audio_path = os.path.join(Instance.instancePath, "output.wav")
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 0:
            # FIXME: inform model of failure?
            return

        if self._audio_pixbuf:
            self.model.still_ready(self._audio_pixbuf)

        line = 'filesrc location=' + audio_path + ' name=audioFilesrc ! wavparse name=audioWavparse ! audioconvert name=audioAudioconvert ! vorbisenc name=audioVorbisenc ! oggmux name=audioOggmux ! filesink name=audioFilesink'
        audioline = Gst.parse_launch(line)

        taglist = self._get_tags(constants.TYPE_AUDIO)

        if self._audio_pixbuf:
            pixbuf_b64 = utils.getStringEncodedFromPixbuf(self._audio_pixbuf)
            taglist.add_value(Gst.TagMergeMode.APPEND, Gst.TAG_EXTENDED_COMMENT, "coverart=" + pixbuf_b64)

        vorbis_enc = audioline.get_by_name('audioVorbisenc')
        vorbis_enc.merge_tags(taglist, Gst.TagMergeMode.REPLACE_ALL)

        audioFilesink = audioline.get_by_name('audioFilesink')
        audioOggFilepath = os.path.join(Instance.instancePath, "output.ogg")
        audioFilesink.set_property("location", audioOggFilepath)

        audioBus = audioline.get_bus()
        audioBus.add_signal_watch()
        self._audio_transcode_handler = audioBus.connect('message', self._onMuxedAudioMessageCb, audioline)
        self._transcode_id = GObject.timeout_add(200, self._transcodeUpdateCb, audioline)
        audioline.set_state(Gst.State.PLAYING)

    def _get_tags(self, type):
        tl = Gst.TagList.new_empty()

        def _set(tag, value):
            tl.add_value(Gst.TagMergeMode.APPEND, tag, value)
        _set(Gst.TAG_ARTIST, self.model.get_nickname())
        _set(Gst.TAG_COMMENT, "olpc")
        #this is unfortunately, unreliable
        #record.Record.log.debug("self.ca.metadata['title']->" + str(self.ca.metadata['title']) )
        _set(Gst.TAG_ALBUM, "olpc") #self.ca.metadata['title']
        date = GLib.Date.new()
        date.set_time_t(time.time())
        _set(Gst.TAG_DATE, date)
        stringType = constants.MEDIA_INFO[type]['istr']

        # Translators: photo by photographer, e.g. "Photo by Mary"
        _set(Gst.TAG_TITLE, _('%(type)s by %(name)s') % {'type': stringType,
                'name': self.model.get_nickname()})
        return tl

    def _take_photo(self, photo_mode):
        if self._pic_exposure_open:
            return

        self._photo_mode = photo_mode
        self._pic_exposure_open = True
        pad = self._photobin.get_static_pad("sink")
        self._pipeline.add(self._photobin)
        self._photobin.set_state(Gst.State.PLAYING)
        self._pipeline.get_by_name("tee").link(self._photobin)

    def take_photo(self):
        if self._has_camera:
            self._take_photo(self.PHOTO_MODE_PHOTO)

    def _photo_handoff(self, fsink, buffer, pad, user_data=None):
        if not self._pic_exposure_open:
            return

        pad = self._photobin.get_static_pad("sink")
        self._pipeline.get_by_name("tee").unlink(self._photobin)
        self._pipeline.remove(self._photobin)

        self._pic_exposure_open = False
        pic = GdkPixbuf.PixbufLoader.new_with_mime_type("image/jpeg")
        pic.write(buffer.extract_dup(0, buffer.get_size()))
        pic.close()
        pixBuf = pic.get_pixbuf()
        del pic

        # FIXME: a double JPEG encoding occurs; photobin and pixbuf.savev

        self.save_photo(pixBuf)

    def save_photo(self, pixbuf):
        if self._photo_mode == self.PHOTO_MODE_AUDIO:
            self._audio_pixbuf = pixbuf
        else:
            self.model.save_photo(pixbuf)

    def record_video(self, quality):
        if not self._has_camera:
            return

        # If we use pad blocking and adjust the pipeline on-the-fly, the
        # resultant video has bad A/V sync :(
        # If we pause the pipeline while adjusting it, the A/V sync is better
        # but not perfect :(
        # so we stop the whole thing while reconfiguring to get the best results
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.add(self._videobin)
        self._pipeline.get_by_name("tee").link(self._videobin)
        self._pipeline.add(self._audiobin)
        self.play()

    def record_audio(self):
        if self._has_camera:
            self._audio_pixbuf = None
            self._take_photo(self.PHOTO_MODE_AUDIO)

        # we should be able to add the audiobin on the fly, but unfortunately
        # this results in several seconds of silence being added at the start
        # of the recording. So we stop the whole pipeline while adjusting it.
        # SL#2040
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.add(self._audiobin)
        self.play()

    def stop_recording_video(self):
        if not self._has_camera:
            return

        # We stop the pipeline while we are adjusting the pipeline to stop
        # recording because if we do it on-the-fly, the following video live
        # feed to the screen becomes several seconds delayed. Weird!
        # FIXME: retest on F11
        # FIXME: could this be the result of audio shortening problems?
        self._eos_cb = self._video_eos
        logger.error('stop recording video')
        self._pipeline.get_by_name('src').send_event(Gst.Event.new_eos())
        self._audiobin.get_by_name('absrc').send_event(Gst.Event.new_eos())

    def _video_eos(self):
        self._pipeline.set_state(Gst.State.NULL)
        self._pipeline.get_by_name("tee").unlink(self._videobin)
        self._pipeline.remove(self._videobin)
        self._pipeline.remove(self._audiobin)

        self.model.shutter_sound()

        if len(self._thumb_pipes) > 0:
            thumbline = self._thumb_pipes[-1]
            thumbline.get_by_name('thumb_fakesink').disconnect(self._thumb_handoff_handler)

        ogg_path = os.path.join(Instance.instancePath, "output.ogg") #ogv
        if not os.path.exists(ogg_path) or os.path.getsize(ogg_path) <= 0:
            # FIXME: inform model of failure?
            return

        line = 'filesrc location=' + ogg_path + ' name=thumbFilesrc ! oggdemux name=thumbOggdemux ! theoradec name=thumbTheoradec ! tee name=thumb_tee ! queue name=thumb_queue ! videoconvert name=thumbVideoconvert ! jpegenc name=thumbJPegenc ! fakesink name=thumb_fakesink'
        thumbline = Gst.parse_launch(line)
        thumb_queue = thumbline.get_by_name('thumb_queue')
        thumb_queue.set_property("leaky", True)
        thumb_queue.set_property("max-size-buffers", 1)
        thumb_tee = thumbline.get_by_name('thumb_tee')
        thumb_fakesink = thumbline.get_by_name('thumb_fakesink')
        self._thumb_handoff_handler = thumb_fakesink.connect("handoff", self.copyThumbPic)
        thumb_fakesink.set_property("signal-handoffs", True)
        self._thumb_pipes.append(thumbline)
        self._thumb_exposure_open = True
        thumbline.set_state(Gst.State.PLAYING)

    def copyThumbPic(self, fsink, buffer, pad, user_data=None):
        if not self._thumb_exposure_open:
            return

        self._thumb_exposure_open = False
        loader = GdkPixbuf.PixbufLoader.new_with_mime_type("image/jpeg")
        loader.write(buffer.extract_dup(0, buffer.get_size()))
        loader.close()
        self.thumbBuf = loader.get_pixbuf()
        self.model.still_ready(self.thumbBuf)

        self._thumb_element('thumb_tee').unlink(self._thumb_element('thumb_queue'))

        oggFilepath = os.path.join(Instance.instancePath, "output.ogg") #ogv
        wavFilepath = os.path.join(Instance.instancePath, "output.wav")
        muxFilepath = os.path.join(Instance.instancePath, "mux.ogg") #ogv

        muxline = Gst.parse_launch('filesrc location=' + str(oggFilepath) + ' name=muxVideoFilesrc ! oggdemux name=muxOggdemux ! theoraparse ! oggmux name=muxOggmux ! filesink location=' + str(muxFilepath) + ' name=muxFilesink filesrc location=' + str(wavFilepath) + ' name=muxAudioFilesrc ! wavparse name=muxWavparse ! audioconvert name=muxAudioconvert ! vorbisenc name=muxVorbisenc ! muxOggmux.')
        taglist = self._get_tags(constants.TYPE_VIDEO)
        vorbis_enc = muxline.get_by_name('muxVorbisenc')
        vorbis_enc.merge_tags(taglist, Gst.TagMergeMode.REPLACE_ALL)

        muxBus = muxline.get_bus()
        muxBus.add_signal_watch()
        self._video_transcode_handler = muxBus.connect('message', self._onMuxedVideoMessageCb, muxline)
        self._mux_pipes.append(muxline)
        #add a listener here to monitor % of transcoding...
        self._transcode_id = GObject.timeout_add(200, self._transcodeUpdateCb, muxline)
        muxline.set_state(Gst.State.PLAYING)

    def _transcodeUpdateCb( self, pipe ):
        position, duration = self._query_position( pipe )
        if position != Gst.CLOCK_TIME_NONE:
            value = position * 100.0 / duration
            value = value/100.0
            self.model.set_progress(value, _('Saving...'))
        return True

    def _query_position(self, pipe):
        try:
            _, position = pipe.query_position(Gst.Format.TIME)
        except:
            position = Gst.CLOCK_TIME_NONE

        try:
            _, duration = pipe.query_duration(Gst.Format.TIME)
        except:
            duration = Gst.CLOCK_TIME_NONE

        return (position, duration)

    def _onMuxedVideoMessageCb(self, bus, message, pipe):
        if message.type != Gst.MessageType.EOS:
            return True

        bus.disconnect(self._video_transcode_handler)
        self._video_transcode_handler = None
        GObject.source_remove(self._transcode_id)
        self._transcode_id = None
        pipe.set_state(Gst.State.NULL)
        pipe.get_bus().remove_signal_watch()

        wavFilepath = os.path.join(Instance.instancePath, "output.wav")
        oggFilepath = os.path.join(Instance.instancePath, "output.ogg") #ogv
        muxFilepath = os.path.join(Instance.instancePath, "mux.ogg") #ogv
        os.remove( wavFilepath )
        os.remove( oggFilepath )
        self.model.save_video(muxFilepath, self.thumbBuf)
        return False

    def _onMuxedAudioMessageCb(self, bus, message, pipe):
        if message.type != Gst.MessageType.EOS:
            return True

        bus.disconnect(self._audio_transcode_handler)
        self._audio_transcode_handler = None
        GObject.source_remove(self._transcode_id)
        self._transcode_id = None
        pipe.set_state(Gst.State.NULL)
        pipe.get_bus().remove_signal_watch()

        wavFilepath = os.path.join(Instance.instancePath, "output.wav")
        oggFilepath = os.path.join(Instance.instancePath, "output.ogg")
        os.remove( wavFilepath )
        self.model.save_audio(oggFilepath, self._audio_pixbuf)
        return False

    def _bus_message_handler(self, bus, message):
        t = message.type
        #logger.error('%r', t)
        if t == Gst.MessageType.EOS:
            if self._eos_cb:
                cb = self._eos_cb
                self._eos_cb = None
                cb()
        elif t == Gst.MessageType.STREAM_STATUS:
            #status_type, element = message.parse_stream_status()
            #logger.error('%r', status_type)
            #logger.error('%r', element)
            pass
        elif t == Gst.MessageType.ERROR:
            #todo: if we come out of suspend/resume with errors, then get us back up and running...
            #todo: handle "No space left on the resource.gstfilesink.c"
            err, debug = message.parse_error()
            logger.error('%r', err)
            logger.error('%r', debug)
            pass
