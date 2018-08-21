# Copyright (C) 2011, One Laptop per Child (3bc80c7)

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

import logging
import xml.dom.minidom
import os

import gi
gi.require_version('TelepathyGLib', '0.12')
from gi.repository import GLib
from gi.repository import TelepathyGLib

from sugar3.presence.tubeconn import TubeConnection
from sugar3 import util

import utils
import serialize
import constants
from instance import Instance
from recordtube import RecordTube
from recorded import Recorded

logger = logging.getLogger('collab')


class RecordCollab(object):
    def __init__(self, activity_obj, model):
        self.activity = activity_obj
        self.model = model
        self._tube = None
        self._collab_timeout = 10000

    def set_activity_shared(self):
        self._setup()
        self._tubes_channel.OfferDBusTube(constants.DBUS_SERVICE, {})

    def share_recd(self, recd):
        if not self._tube:
            return
        xmlstr = serialize.getRecdXmlMeshString(recd)
        self._tube.notifyBudsOfNewRecd(Instance.keyHashPrintable, xmlstr)

    def joined(self):
        if not self.activity.get_shared_activity():
            return
        self._setup()
        self._tubes_channel.ListTubes(reply_handler=self._list_tubes_reply_cb,
                                      error_handler=self._list_tubes_error_cb)

    def request_download(self, recd):
        if recd.meshDownloading:
            logger.debug('meshInitRoundRobin: we are in midst of '
                         'downloading this file...')
            return

        # start with who took the photo
        recd.triedMeshBuddies = []
        recd.triedMeshBuddies.append(Instance.keyHashPrintable)
        self._req_recd_from_buddy(recd, recd.recorderHash, recd.recorderName)

    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    @staticmethod
    def _list_tubes_error_cb(e):
        logger.error('ListTubes() failed: %s', e)

    def _setup(self):
        # sets up the tubes...
        shared_activity = self.activity.shared_activity
        if not shared_activity:
            logger.error('_setup: Failed to share or join activity')
            return

        self._connection = shared_activity.telepathy_conn
        tubes_chan = shared_activity.telepathy_tubes_chan
        text_chan = shared_activity.telepathy_text_chan

        self._tubes_channel = \
            tubes_chan[TelepathyGLib.IFACE_CHANNEL_TYPE_TUBES]
        self._text_channel = \
            text_chan[TelepathyGLib.IFACE_CHANNEL_INTERFACE_GROUP]

        self._tubes_channel.connect_to_signal('NewTube', self._new_tube_cb)

    def _new_tube_cb(self, id, initiator, type, service, params, state):
        logger.debug('New tube: ID=%d initator=%d type=%d service=%s '
                     'params=%r state=%d', id, initiator, type, service,
                     params, state)
        if type != TelepathyGLib.TubeType.DBUS or \
           service != constants.DBUS_SERVICE:

            return

        if state == TelepathyGLib.TubeState.LOCAL_PENDING:
            self._tubes_channel.AcceptDBusTube(id)
        tube_connection = TubeConnection(self._connection, self._tubes_channel,
                                         id, group_iface=self._text_channel)
        self._tube = RecordTube(tube_connection)
        self._tube.connect("new-recd", self._new_recd_cb)
        self._tube.connect("recd-request", self._recd_request_cb)
        self._tube.connect("recd-bits-arrived", self._recd_bits_arrived_cb)
        self._tube.connect("recd-unavailable", self._recd_unavailable_cb)

    def _new_recd_cb(self, remote_object, recorder, xmlstr):
        logger.debug('new_recd_cb')
        dom = None
        try:
            dom = xml.dom.minidom.parseString(xmlstr)
        except:
            logger.error('Unable to parse mesh xml')
        if not dom:
            return

        recd = Recorded()
        recd = serialize.fillRecdFromNode(recd, dom.documentElement)
        if not recd:
            logger.debug('_newRecdCb: recd is None. Unable to parse XML')
            return

        logger.debug('_newRecdCb: adding new recd thumb')
        recd.buddy = True
        recd.downloadedFromBuddy = False
        self.model.add_recd(recd)

    def _req_recd_from_buddy(self, recd, sender, nick):
        recd.triedMeshBuddies.append(sender)
        recd.meshDownloadingFrom = sender
        recd.meshDownloadingFromNick = nick
        recd.meshDownloadingProgress = False
        recd.meshDownloading = True
        recd.meshDownlodingPercent = 0.0
        self.activity.update_download_progress(recd)
        recd.meshReqCallbackId = GLib.timeout_add(self._collab_timeout,
                                                  self._check_recd_request,
                                                  recd)
        self._tube.requestRecdBits(Instance.keyHashPrintable, sender,
                                   recd.mediaMd5)

    def _next_round_robin_buddy(self, recd):
        logger.debug('meshNextRoundRobinBuddy')
        if recd.meshReqCallbackId:
            GLib.source_remove(recd.meshReqCallbackId)
            recd.meshReqCallbackId = 0

        # delete any stub of a partially downloaded file
        path = recd.getMediaFilepath()
        if path and os.path.exists(path):
            os.remove(path)

        good_buddy_obj = None
        buds = self.activity.get_shared_activity().get_joined_buddies()
        for buddy_obj in buds:
            buddy = util.sha_data(buddy_obj.props.key)
            buddy = util.printable_hash(buddy)
            if recd.triedMeshBuddies.count(buddy) > 0:
                logger.debug('mnrrb: weve already tried bud ' +
                             buddy_obj.props.nick)
            else:
                logger.debug('mnrrb: ask next buddy: ' + buddy_obj.props.nick)
                good_buddy_obj = buddy_obj
                break

        if good_buddy_obj:
            buddy = util.sha_data(good_buddy_obj.props.key)
            buddy = util.printable_hash(buddy)
            self._req_recd_from_buddy(recd, buddy, good_buddy_obj.props.nick)
        else:
            logger.debug('we\'ve tried all buddies here, '
                         'and no one has this recd')
            recd.meshDownloading = False
            recd.triedMeshBuddies = []
            recd.triedMeshBuddies.append(Instance.keyHashPrintable)
            self.activity.update_download_progress(recd)

        return False

    def _recd_request_cb(self, remote_object, remote_person, md5sum):
        # if we are here, it is because someone has been told we have
        # what they want.  we need to send them that thing, whatever
        # that thing is
        recd = self.model.get_recd_by_md5(md5sum)
        if not recd:
            logger.debug('_recdRequestCb: we dont have the recd '
                         'they asked for')
            self._tube.unavailableRecd(md5sum, Instance.keyHashPrintable,
                                       remote_person)
            return

        if recd.deleted:
            logger.debug('_recdRequestCb: we have the recd, '
                         'but it has been deleted, so we won\'t share')
            self._tube.unavailableRecd(md5sum, Instance.keyHashPrintable,
                                       remote_person)
            return

        if recd.buddy and not recd.downloadedFromBuddy:
            logger.debug('_recdRequestCb: we have an incomplete recd, '
                         'so we won\'t share')
            self._tube.unavailableRecd(md5sum, Instance.keyHashPrintable,
                                       remote_person)
            return

        recd.meshUploading = True
        path = recd.getMediaFilepath()

        if recd.type == constants.TYPE_AUDIO:
            audioImgFilepath = recd.getAudioImageFilepath()

            dest_path = os.path.join(Instance.instancePath, "audioBundle")
            dest_path = utils.getUniqueFilepath(dest_path, 0)
            cmd = "cat " + path + " " + audioImgFilepath + " > " + dest_path
            logger.debug(cmd)
            os.system(cmd)
            path = dest_path
        # TODO: add videoBundle from recd.getVideoImageFilepath() but
        # requires transmitting audioBundle size

        self._tube.broadcastRecd(recd.mediaMd5, path, remote_person)
        recd.meshUploading = False
        # if you were deleted while uploading, now throw away those bits now
        if recd.deleted:
            recd.doDeleteRecorded(recd)

    def _check_recd_request(self, recd):
        # todo: add category for "not active activity, so go ahead and delete"

        if recd.downloadedFromBuddy:
            logger.debug('_meshCheckOnRecdRequest: '
                         'recdRequesting.downloadedFromBuddy')
            if recd.meshReqCallbackId:
                GLib.source_remove(recd.meshReqCallbackId)
                recd.meshReqCallbackId = 0
            return False
        if recd.deleted:
            logger.debug('_meshCheckOnRecdRequest: '
                         'recdRequesting.deleted')
            if recd.meshReqCallbackId:
                GLib.source_remove(recd.meshReqCallbackId)
                recd.meshReqCallbackId = 0
            return False
        if recd.meshDownloadingProgress:
            logger.debug('_meshCheckOnRecdRequest: '
                         'recdRequesting.meshDownloadingProgress')
            # we've received some bits since last we checked, so keep
            # waiting...  they'll all get here eventually!
            recd.meshDownloadingProgress = False
            return True
        else:
            logger.debug('_meshCheckOnRecdRequest: '
                         '! recdRequesting.meshDownloadingProgress')
            # that buddy we asked info from isn't responding; next buddy!
            # self.meshNextRoundRobinBuddy( recdRequesting )
            GLib.idle_add(self._next_round_robin_buddy, recd)
            return False

    def _recd_bits_arrived_cb(self, remote_object, md5sum, part, num_parts,
                              bytes, sender):
        recd = self.model.get_recd_by_md5(md5sum)
        if not recd:
            logger.debug('_recdBitsArrivedCb: thx 4 yr bits, '
                         'but we dont even have that photo')
            return
        if recd.deleted:
            logger.debug('_recdBitsArrivedCb: thx 4 yr bits, '
                         'but we deleted that photo')
            return
        if recd.downloadedFromBuddy:
            logger.debug('_recdBitsArrivedCb: we\'ve already '
                         'downloadedFromBuddy')
            return
        if not recd.buddy:
            logger.debug('_recdBitsArrivedCb: uh, we took this photo, '
                         'so dont need your bits')
            return
        if recd.meshDownloadingFrom != sender:
            logger.debug('_recdBitsArrivedCb: wrong bits ' + str(sender) +
                         ', exp:' + str(recd.meshDownloadingFrom))
            return

        # update that we've heard back about this, reset the timeout
        if recd.meshReqCallbackId:
            GLib.source_remove(recd.meshReqCallbackId)
        recd.meshReqCallbackId = GLib.timeout_add(self._collab_timeout,
                                                  self._check_recd_request,
                                                  recd)

        # update the progress bar
        recd.meshDownlodingPercent = (part + 0.0) / (num_parts + 0.0)
        recd.meshDownloadingProgress = True
        self.activity.update_download_progress(recd)
        open(recd.getMediaFilepath(), 'a+').write(bytes)

        if part > num_parts:
            logger.error('More parts than required have arrived')
            return
        if part != num_parts:
            return

        logger.debug('Finished receiving %s' % recd.title)
        GLib.source_remove(recd.meshReqCallbackId)
        recd.meshReqCallbackId = 0
        recd.meshDownloading = False
        recd.meshDownlodingPercent = 1.0
        recd.downloadedFromBuddy = True
        if recd.type == constants.TYPE_AUDIO:
            path = recd.getMediaFilepath()
            bundle_path = os.path.join(Instance.instancePath, "audioBundle")
            bundle_path = utils.getUniqueFilepath(bundle_path, 0)
            # TODO: get videoBundle for recd.videoImageFilename
            # requires transmitting audioBundle size

            cmd = "split -a 1 -b " + str(recd.mediaBytes) + " " + path + \
                  " " + bundle_path
            logger.debug(cmd)
            os.system(cmd)

            bundle_name = os.path.basename(bundle_path)
            media_filename = bundle_name + "a"
            media_path = os.path.join(Instance.instancePath, media_filename)
            media_path_ext = os.path.join(Instance.instancePath,
                                          media_filename + ".ogg")
            os.rename(media_path, media_path_ext)
            audio_image_name = bundle_name + "b"
            audio_image_path = os.path.join(Instance.instancePath,
                                            audio_image_name)
            audio_image_path_ext = os.path.join(Instance.instancePath,
                                                audio_image_name + ".png")
            os.rename(audio_image_path, audio_image_path_ext)

            recd.mediaFilename = os.path.basename(media_path_ext)
            recd.audioImageFilename = os.path.basename(audio_image_path_ext)

        self.activity.remote_recd_available(recd)

    def _recd_unavailable_cb(self, remote_object, md5sum, sender):
        logger.debug('_recdUnavailableCb: sux, we want to see that photo')
        recd = self.model.get_recd_by_md5(md5sum)
        if not recd:
            logger.debug('_recdUnavailableCb: actually, we don\'t even know '
                         'about that one..')
            return
        if recd.deleted:
            logger.debug('_recdUnavailableCb: actually, since we asked, '
                         'we deleted.')
            return
        if not recd.buddy:
            logger.debug('_recdUnavailableCb: uh, odd, '
                         'we took that photo and have it already.')
            return
        if recd.downloadedFromBuddy:
            logger.debug('_recdUnavailableCb: we already downloaded it...  '
                         'you might have been slow responding.')
            return
        if recd.meshDownloadingFrom != sender:
            logger.debug('_recdUnavailableCb: we aren\'t asking you '
                         'for a copy now.  slow response, pbly.')
            return
