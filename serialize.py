# Copyright (C) 2008, Media Modifications Ltd.
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

from gi.repository import GdkPixbuf
from xml.dom.minidom import getDOMImplementation
import cStringIO
import os
import logging
import dbus

from sugar3.datastore import datastore

import constants
from instance import Instance
import recorded
import utils

logger = logging.getLogger('serialize')


def fillMediaHash(doc, mediaHashs):
    for key, value in constants.MEDIA_INFO.items():
        recdElements = doc.documentElement.getElementsByTagName(value['name'])
        for el in recdElements:
            _loadMediaIntoHash(el, mediaHashs[key])


def _loadMediaIntoHash(el, hash):
    addToHash = True
    recd = recorded.Recorded()
    recd = fillRecdFromNode(recd, el)
    if recd:
        if recd.datastoreId:
            # quickly check: if you have a datastoreId that the file
            # hasn't been deleted, cause if you do, we need to flag
            # your removal 2904 trac
            recd.datastoreOb = getMediaFromDatastore(recd)
            if not recd.datastoreOb:
                addToHash = False
            else:
                # name might have been changed in the journal, so
                # reflect that here
                if recd.title != recd.datastoreOb.metadata['title']:
                    recd.setTitle(recd.datastoreOb.metadata['title'])
                if recd.tags != recd.datastoreOb.metadata['tags']:
                    recd.setTags(recd.datastoreOb.metadata['tags'])
                if recd.buddy:
                    recd.downloadedFromBuddy = True

            recd.datastoreOb == None  # FIXME

    if addToHash:
        hash.append(recd)


def getMediaFromDatastore(recd):
    if not recd.datastoreId:
        return None

    if recd.datastoreOb:
        # already have the object
        return recd.datastoreOb

    mediaObject = None
    try:
        mediaObject = datastore.get(recd.datastoreId)
    finally:
        return mediaObject


def removeMediaFromDatastore(recd):
    # before this method is called, the media are removed from the file
    if not recd.datastoreId or not recd.datastoreOb:
        return

    try:
        recd.datastoreOb.destroy()
        datastore.delete(recd.datastoreId)

        recd.datastoreId = None
        recd.datastoreOb = None
    finally:
        # todo: add error message here
        pass


def fillRecdFromNode(recd, el):
    if el.getAttributeNode('type'):
        recd.type = int(el.getAttribute('type'))

    if el.getAttributeNode('title'):
        recd.title = el.getAttribute('title')

    if el.getAttributeNode('time'):
        recd.time = int(el.getAttribute('time'))

    if el.getAttributeNode('photographer'):
        recd.recorderName = el.getAttribute('photographer')

    if el.getAttributeNode('tags'):
        recd.tags = el.getAttribute('tags')
    else:
        recd.tags = ""

    if el.getAttributeNode('recorderHash'):
        recd.recorderHash = el.getAttribute('recorderHash')

    if el.getAttributeNode('colorStroke'):
        recd.colorStroke = el.getAttribute('colorStroke')

    if el.getAttributeNode('colorFill'):
        recd.colorFill = el.getAttribute('colorFill')

    if el.getAttributeNode('buddy'):
        recd.buddy = (el.getAttribute('buddy') == "True")

    if el.getAttributeNode('mediaMd5'):
        recd.mediaMd5 = el.getAttribute('mediaMd5')

    if el.getAttributeNode('thumbMd5'):
        recd.thumbMd5 = el.getAttribute('thumbMd5')

    if el.getAttributeNode('mediaBytes'):
        recd.mediaBytes = el.getAttribute('mediaBytes')

    if el.getAttributeNode('thumbBytes'):
        recd.thumbBytes = el.getAttribute('thumbBytes')

    bt = el.getAttributeNode('base64Thumb')
    if bt:
        thumbPath = os.path.join(Instance.instancePath, "datastoreThumb.jpg")
        thumbPath = utils.getUniqueFilepath(thumbPath, 0)
        thumbImg = utils.getPixbufFromString(bt.nodeValue)
        thumbImg.savev(thumbPath, 'png', [], [])
        recd.thumbFilename = os.path.basename(thumbPath)

    ai = el.getAttributeNode('audioImage')
    if (ai is not None):
        audioImagePath = os.path.join(Instance.instancePath, "audioImage.png")
        audioImagePath = utils.getUniqueFilepath(audioImagePath, 0)
        audioImage = utils.getPixbufFromString(ai.nodeValue)
        audioImage.savev(audioImagePath, "png", [], [])
        recd.audioImageFilename = os.path.basename(audioImagePath)

    vi = el.getAttributeNode('videoImage')
    if (vi is not None):
        videoImagePath = os.path.join(Instance.instancePath, "videoImage.png")
        videoImagePath = utils.getUniqueFilepath(videoImagePath, 0)
        videoImage = utils.getPixbufFromString(vi.nodeValue)
        videoImage.savev(videoImagePath, "png", [], [])
        recd.videoImageFilename = os.path.basename(videoImagePath)

    datastoreNode = el.getAttributeNode('datastoreId')
    if datastoreNode:
        recd.datastoreId = datastoreNode.nodeValue

    return recd


def getRecdXmlMeshString(recd):
    impl = getDOMImplementation()
    recdXml = impl.createDocument(None, 'recd', None)
    root = recdXml.documentElement
    _addRecdXmlAttrs(root, recd, True)

    writer = cStringIO.StringIO()
    recdXml.writexml(writer)
    return writer.getvalue()


def _addRecdXmlAttrs(el, recd, forMeshTransmit):
    el.setAttribute('type', str(recd.type))

    if (recd.type == constants.TYPE_AUDIO) and (not forMeshTransmit):
        aiPixbuf = recd.getAudioImagePixbuf()
        if aiPixbuf:
            aiPixbufString = str(utils.getStringEncodedFromPixbuf(aiPixbuf))
            el.setAttribute('audioImage', aiPixbufString)

    if (recd.type == constants.TYPE_VIDEO) and (not forMeshTransmit):
        viPixbuf = recd.getVideoImagePixbuf()
        if viPixbuf:
            viPixbufString = str(utils.getStringEncodedFromPixbuf(viPixbuf))
            el.setAttribute('videoImage', viPixbufString)

    if (recd.datastoreId is not None) and (not forMeshTransmit):
        el.setAttribute('datastoreId', str(recd.datastoreId))

    el.setAttribute('title', recd.title)
    el.setAttribute('time', str(recd.time))
    el.setAttribute('photographer', recd.recorderName)
    el.setAttribute('recorderHash', str(recd.recorderHash))
    el.setAttribute('colorStroke', str(recd.colorStroke))
    el.setAttribute('colorFill', str(recd.colorFill))
    el.setAttribute('buddy', str(recd.buddy))
    el.setAttribute('mediaMd5', str(recd.mediaMd5))
    el.setAttribute('thumbMd5', str(recd.thumbMd5))
    el.setAttribute('mediaBytes', str(recd.mediaBytes))

    if recd.thumbBytes:
        el.setAttribute('thumbBytes', str(recd.thumbBytes))

    # FIXME: can this be removed, or at least autodetected? has not been
    # changed for ages, should not be relevant
    el.setAttribute('version', '54')

    pixbuf = recd.getThumbPixbuf()
    if pixbuf:
        thumb64 = str(utils.getStringEncodedFromPixbuf(pixbuf))
        el.setAttribute('base64Thumb', thumb64)


def saveMediaHash(mediaHashs, activity):
    impl = getDOMImplementation()
    album = impl.createDocument(None, 'album', None)
    root = album.documentElement

    # flag everything for saving...
    atLeastOne = False
    for type, value in constants.MEDIA_INFO.items():
        typeName = value['name']
        for recd in mediaHashs[type]:
            recd.savedXml = False
            recd.savedMedia = False
            atLeastOne = True

    # and if there is anything to save, save it
    if atLeastOne:
        for type, value in constants.MEDIA_INFO.items():
            typeName = value['name']
            for recd in mediaHashs[type]:
                mediaEl = album.createElement(typeName)
                root.appendChild(mediaEl)
                _saveMedia(mediaEl, recd, activity)

    return album


def _saveMedia(el, recd, activity):
    if recd.buddy and recd.datastoreId is None and \
       not recd.downloadedFromBuddy:
        recd.savedMedia = True
        _saveXml(el, recd)
    else:
        recd.savedMedia = False
        _saveMediaToDatastore(el, recd, activity)


def _saveXml(el, recd):
    _addRecdXmlAttrs(el, recd, False)
    recd.savedXml = True


def _saveMediaToDatastore(el, recd, activity):
    # note that we update the recds that go through here to how they
    # would look on a fresh load from file since this won't just
    # happen on close()

    if recd.datastoreId:
        # already saved to the datastore, don't need to re-rewrite the
        # file since the mediums are immutable.  However, they might
        # have changed the name of the file
        if recd.metaChange:
            recd.datastoreOb = getMediaFromDatastore(recd)
            if recd.datastoreOb.metadata['title'] != recd.title:
                recd.datastoreOb.metadata['title'] = recd.title
                datastore.write(recd.datastoreOb)
            if recd.datastoreOb.metadata['tags'] != recd.tags:
                recd.datastoreOb.metadata['tags'] = recd.tags
                datastore.write(recd.datastoreOb)

            # reset for the next title change if not closing...
            recd.metaChange = False

        # save the title to the xml
        recd.savedMedia = True
        _saveXml(el, recd)

    else:
        # this will remove the media from being accessed on the local
        # disk since it puts it away into cold storage, therefore this
        # is only called when write_file is called by the activity
        # superclass
        mediaObject = datastore.create()
        mediaObject.metadata['title'] = recd.title
        mediaObject.metadata['tags'] = recd.tags

        datastorePreviewPixbuf = recd.getThumbPixbuf()
        if recd.type == constants.TYPE_AUDIO:
            datastorePreviewPixbuf = recd.getAudioImagePixbuf()
        elif recd.type == constants.TYPE_PHOTO:
            datastorePreviewFilepath = recd.getMediaFilepath()
            datastorePreviewPixbuf = GdkPixbuf.Pixbuf.new_from_file(
                datastorePreviewFilepath)

        if datastorePreviewPixbuf:
            # journal shows previews in a 4:3 aspect ratio
            datastorePreviewWidth = 300
            datastorePreviewHeight = 225

            # scale to match available height, retaining aspect ratio
            consequentWidth = datastorePreviewHeight * \
                datastorePreviewPixbuf.get_width() / \
                datastorePreviewPixbuf.get_height()
            datastorePreviewPixbuf = \
                datastorePreviewPixbuf.scale_simple(
                    consequentWidth,
                    datastorePreviewHeight,
                    GdkPixbuf.InterpType.BILINEAR)

            # where aspect ratio is unconventional, e.g. 16:9, trim sides
            if consequentWidth != datastorePreviewWidth:
                trimmedPixbuf = GdkPixbuf.Pixbuf.new(
                    datastorePreviewPixbuf.get_colorspace(),
                    datastorePreviewPixbuf.get_has_alpha(),
                    datastorePreviewPixbuf.get_bits_per_sample(),
                    datastorePreviewWidth,
                    datastorePreviewHeight)
                datastorePreviewPixbuf.copy_area(
                    (consequentWidth - datastorePreviewWidth) / 2,
                    0,
                    datastorePreviewWidth,
                    datastorePreviewHeight,
                    trimmedPixbuf,
                    0,
                    0)
                datastorePreviewPixbuf = trimmedPixbuf

            datastorePreview = utils.getStringFromPixbuf(
                datastorePreviewPixbuf)
            mediaObject.metadata['preview'] = dbus.ByteArray(datastorePreview)

        colors = str(recd.colorStroke) + "," + str(recd.colorFill)
        mediaObject.metadata['icon-color'] = colors

        mtype = constants.MEDIA_INFO[recd.type]
        mediaObject.metadata['mime_type'] = mtype['mime']

        mediaObject.metadata['activity_id'] = activity._activity_id

        mediaFile = recd.getMediaFilepath()
        mediaObject.file_path = mediaFile
        mediaObject.transfer_ownership = True

        datastore.write(mediaObject)

        recd.datastoreId = mediaObject.object_id
        recd.savedMedia = True

        _saveXml(el, recd)

        recd.mediaFilename = None
