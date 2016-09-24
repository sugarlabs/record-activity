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

from gi.repository import GObject, Gst, GdkX11, GstVideo, GdkPixbuf

from sugar3.activity.activity import get_bundle_path
import logging

from instance import Instance
import constants
import utils

logger = logging.getLogger('glive')

OGG_TRAITS = {
        0: { 'width': 160, 'height': 120, 'quality': 16 },
        1: { 'width': 384, 'height': 288, 'quality': 16 } }

class Glive:
    PHOTO_MODE_PHOTO = 0
    PHOTO_MODE_AUDIO = 1

    def __init__(self, activity_obj, model):
        self.activity = activity_obj
        self.model = model
        self._eos_cb = None

        self._has_camera = False
        self._can_limit_framerate = False
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

        self._pipeline = Gst.Pipeline("Record")
        self._create_photobin()
        self._create_audiobin()
        self._create_videobin()
        self._create_xbin()
        self._create_pipeline()

        self._thumb_pipes = []
        self._mux_pipes = []

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._bus_message_handler)

    def _detect_camera(self):
        v4l2src = Gst.ElementFactory.make('v4l2src', 'detect-camera-src')
        if v4l2src is None:
            logger.error('no v4l2src')
        if v4l2src.props.device_name is None:
            return

        self._has_camera = True

        # Figure out if we can place a framerate limit on the v4l2 element,
        # which in theory will make it all the way down to the hardware.
        # ideally, we should be able to do this by checking caps. However, I
        # can't find a way to do this (at this time, XO-1 cafe camera driver
        # doesn't support framerate changes, but GStreamer caps suggest
        # otherwise)
        pipeline = Gst.Pipeline()
        caps = Gst.Caps('video/x-raw,format=(yuv),framerate=10/1')
        fsink = Gst.ElementFactory.make('fakesink', 'detect-camera-sink')
        if fsink is None:
            logger.error('no fakesink')
        pipeline.add(v4l2src)
        pipeline.add(fsink)
        v4l2src.link_filtered(fsink, caps)
        self._can_limit_framerate = pipeline.set_state(Gst.State.PAUSED) != Gst.StateChangeReturn.FAILURE
        pipeline.set_state(Gst.State.NULL)

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
        src = Gst.ElementFactory.make("alsasrc", "absrc")
        if src is None:
            logger.error('no alsasrc')

        # attempt to use direct access to the 0,0 device, solving some A/V
        # sync issues
        src.set_property("device", "plughw:0,0")
        hwdev_available = src.set_state(Gst.State.PAUSED) != Gst.StateChangeReturn.FAILURE
        src.set_state(Gst.State.NULL)
        if not hwdev_available:
            src.set_property("device", "default")

        capsfilter = Gst.ElementFactory.make('capsfilter', 'abcaps')
        if capsfilter is None:
            logger.error('no capsfilter')
        capsfilter.set_property('caps', Gst.caps_from_string("audio/x-raw,format=(int),rate=48000,channels=1,depth=16"))

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
        self._audiobin.add(src, capsfilter, rate, queue, enc, sink)

        #if not src.link(capsfilter):
        #    logger.error('src link to capsfilter failed')
        #if not capsfilter.link(rate):
        #    logger.error('capsfilter link to rate failed')
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
        queue.set_property("max-size-bytes", 33554432) # 32mb
        queue.connect("overrun", self._log_queue_overrun)

        scale = Gst.ElementFactory.make("videoscale", "vbscale")
        if scale is None:
            logger.error('no videoscale')

        scalecapsfilter = Gst.ElementFactory.make("capsfilter", "scalecaps")
        if scalecapsfilter is None:
            logger.error('no capsfilter')

        scalecaps = Gst.Caps('video/x-raw,format=(yuv),width=160,height=120')
        scalecapsfilter.set_property("caps", scalecaps)

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
        self._videobin.add(queue, scale, scalecapsfilter, vc, enc, mux, sink)

        if not queue.link(scale):
            logger.error('queue link to scale failed')
        if not scale.link_pads(None, scalecapsfilter, "sink"):
            logger.error('scale link pads to scalecapsfilter failed')
        if not scalecapsfilter.link_pads("src", vc, None):
            logger.error('scalecapsfilter link pads to vc failed')
        if not vc.link(enc):
            logger.error('vc link to enc failed')
        if not enc.link(mux):
            logger.error('enc link to mux failed')
        if not mux.link(sink):
            logger.error('mux link to sink failed')

        pad = queue.get_static_pad("sink")
        self._videobin.add_pad(Gst.GhostPad("sink", pad))

    def _create_xbin(self):
        scale = Gst.ElementFactory.make("videoscale")
        if scale is None:
            logger.error('no videoscale')

        vc = Gst.ElementFactory.make("videoconvert")
        if vc is None:
            logger.error('no videoconvert')

        xsink = Gst.ElementFactory.make("ximagesink", "xsink")
        if xsink is None:
            logger.error('no ximagesink')

        xsink.set_property("force-aspect-ratio", True)

        # http://thread.gmane.org/gmane.comp.video.gstreamer.devel/29644
        xsink.set_property("sync", False)

        self._xbin = Gst.Bin("xbin")
        self._xbin.add(scale, vc, xsink)
        scale.link(vc)
        vc.link(xsink)

        pad = scale.get_static_pad("sink")
        self._xbin.add_pad(Gst.GhostPad("sink", pad))

    def _config_videobin(self, quality, width, height):
        vbenc = self._videobin.get_by_name("vbenc")
        vbenc.set_property("quality", 16)
        scaps = self._videobin.get_by_name("scalecaps")
        scaps.set_property("caps", Gst.Caps("video/x-raw,format=(yuv),width=%d,height=%d" % (width, height)))

    def _create_pipeline(self):
        if not self._has_camera:
            return

        src = Gst.ElementFactory.make("v4l2src", "camsrc")
        if src is None:
            logger.error('no v4l2src')

        self._pipeline.add(src)

        tee = Gst.ElementFactory.make("tee", "tee")
        if tee is None:
            logger.error('no tee')

        self._pipeline.add(tee)
        if not src.link(tee):
            logger.debug('cannot link')

        queue = Gst.ElementFactory.make("queue", "dispqueue")
        if queue is None:
            logger.error('no queue')

        # prefer fresh frames
        queue.set_property("leaky", True)
        queue.set_property("max-size-buffers", 2)

        self._pipeline.add(queue)
        if not tee.link(queue):
            logger.debug('cannot link')

        self._xvsink = Gst.ElementFactory.make("xvimagesink", "xsink")
        if self._xvsink is None:
            logger.error('no xvimagesink')

        self._xv_available = self._xvsink.set_state(Gst.State.PAUSED) != Gst.StateChangeReturn.FAILURE
        self._xvsink.set_state(Gst.State.NULL)

        # http://thread.gmane.org/gmane.comp.video.gstreamer.devel/29644
        self._xvsink.set_property("sync", False)

        self._xvsink.set_property("force-aspect-ratio", True)

    def _log_queue_overrun(self, queue):
        cbuffers = queue.get_property("current-level-buffers")
        cbytes = queue.get_property("current-level-bytes")
        ctime = queue.get_property("current-level-time")
        logger.error("Buffer overrun in %s (%d buffers, %d bytes, %d time)"
            % (queue.get_name(), cbuffers, cbytes, ctime))
 
    def _thumb_element(self, name):
        return self._thumb_pipes[-1].get_by_name(name)

    def is_using_xv(self):
        return self._pipeline.get_by_name("xsink") == self._xvsink

    def _configure_xv(self):
        if self.is_using_xv():
            # nothing to do, Xv already configured
            return self._xvsink

        queue = self._pipeline.get_by_name("dispqueue")
        if self._pipeline.get_by_name("xbin"):
            # X sink is configured, so remove it
            queue.unlink(self._xbin)
            self._pipeline.remove(self._xbin)

        self._pipeline.add(self._xvsink)
        queue.link(self._xvsink)
        return self._xvsink

    def _configure_x(self):
        if self._pipeline.get_by_name("xbin") == self._xbin:
            # nothing to do, X already configured
            return self._xbin.get_by_name("xsink")

        queue = self._pipeline.get_by_name("dispqueue")
        xvsink = self._pipeline.get_by_name("xsink")

        if xvsink:
            # Xv sink is configured, so remove it
            queue.unlink(xvsink)
            self._pipeline.remove(xvsink)

        self._pipeline.add(self._xbin)
        queue.link(self._xbin)
        return self._xbin.get_by_name("xsink")

    def play(self, use_xv=True):
        if self._get_state() == Gst.State.PLAYING:
            return

        if self._has_camera:
            if use_xv and self._xv_available:
                xsink = self._configure_xv()
            else:
                xsink = self._configure_x()

            # X overlay must be set every time, it seems to forget when you stop
            # the pipeline.
            self.activity.set_glive_sink(xsink)

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
        tl = Gst.TagList()
        return tl

        def _set(tag, value):
            tl.add_value(Gst.TagMergeMode.APPEND, tag, value)
        _set(Gst.TAG_ARTIST, self.model.get_nickname())
        _set(Gst.TAG_COMMENT, "olpc")
        #this is unfortunately, unreliable
        #record.Record.log.debug("self.ca.metadata['title']->" + str(self.ca.metadata['title']) )
        _set(Gst.TAG_ALBUM, "olpc") #self.ca.metadata['title']
        _set(Gst.TAG_DATE, utils.getDateString(int(time.time())))
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

        self.save_photo(pixBuf)

    def save_photo(self, pixbuf):
        if self._photo_mode == self.PHOTO_MODE_AUDIO:
            self._audio_pixbuf = pixbuf
        else:
            self.model.save_photo(pixbuf)

    def record_video(self, quality):
        if not self._has_camera:
            return

        self._ogg_quality = quality
        self._config_videobin(OGG_TRAITS[quality]['quality'],
            OGG_TRAITS[quality]['width'],
            OGG_TRAITS[quality]['height'])

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
        self._pipeline.get_by_name('camsrc').send_event(Gst.Event.new_eos())
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

        GObject.source_remove(self._video_transcode_handler)
        self._video_transcode_handler = None
        GObject.source_remove(self._transcode_id)
        self._transcode_id = None
        pipe.set_state(Gst.State.NULL)
        pipe.get_bus().remove_signal_watch()
        pipe.get_bus().disable_sync_message_emission()

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

        GObject.source_remove(self._audio_transcode_handler)
        self._audio_transcode_handler = None
        GObject.source_remove(self._transcode_id)
        self._transcode_id = None
        pipe.set_state(Gst.State.NULL)
        pipe.get_bus().remove_signal_watch()
        pipe.get_bus().disable_sync_message_emission()

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
        elif t == Gst.MessageType.ERROR:
            #todo: if we come out of suspend/resume with errors, then get us back up and running...
            #todo: handle "No space left on the resource.gstfilesink.c"
            err, debug = message.parse_error()
            logger.error('%r', err)
            logger.error('%r', debug)
            pass

    def abandonMedia(self):
        self.stop()

        if self._audio_transcode_handler:
            GObject.source_remove(self._audio_transcode_handler)
            self._audio_transcode_handler = None
        if self._transcode_id:
            GObject.source_remove(self._transcode_id)
            self._transcode_id = None
        if self._video_transcode_handler:
            GObject.source_remove(self._video_transcode_handler)
            self._video_transcode_handler = None

        wav_path = os.path.join(Instance.instancePath, "output.wav")
        if os.path.exists(wav_path):
            os.remove(wav_path)
        ogg_path = os.path.join(Instance.instancePath, "output.ogg") #ogv
        if os.path.exists(ogg_path):
            os.remove(ogg_path)
        mux_path = os.path.join(Instance.instancePath, "mux.ogg") #ogv
        if os.path.exists(mux_path):
            os.remove(mux_path)

