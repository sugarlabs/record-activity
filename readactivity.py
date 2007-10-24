# Copyright (C) 2007, Red Hat, Inc.
#
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

import logging
from gettext import gettext as _

import gtk
import gobject
import evince
import hippo
import os
import tempfile
import time
import dbus
import logging
import telepathy
import telepathy.client
import shutil

from sugar.activity import activity
from sugar import network
from sugar import util
from sugar.presence import presenceservice
from sugar import profile

from readtoolbar import EditToolbar, ReadToolbar, ViewToolbar

_HARDWARE_MANAGER_INTERFACE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_SERVICE = 'org.laptop.HardwareManager'
_HARDWARE_MANAGER_OBJECT_PATH = '/org/laptop/HardwareManager'

_TOOLBAR_READ = 2

# will eventually be imported from sugar
from sugar.presence.tubeconn import TubeConnection
SERVICE = "org.laptop.HelloMesh"
IFACE = SERVICE
PATH = "/org/laptop/HelloMesh"
from dbus import Interface
from dbus.service import method, signal
from dbus.gobject_service import ExportedGObject

class ReadActivity(activity.Activity):
    def __init__(self, handle):
        activity.Activity.__init__(self, handle)
        self._document = None
        self._filepath = None
        self._fileserver = None

        self._logger = logging.getLogger('read-activity')

        self.connect('key-press-event', self._key_press_event_cb)

        logging.debug('starting read...')

        evince.job_queue_init()
        self._view = evince.View()
        self._view.connect('notify::has-selection', self._view_notify_has_selection_cb)

        toolbox = activity.ActivityToolbox(self)

        self._edit_toolbar = EditToolbar(self._view)
        self._edit_toolbar.undo.props.visible = False
        self._edit_toolbar.redo.props.visible = False
        self._edit_toolbar.separator.props.visible = False
        self._edit_toolbar.copy.set_sensitive(False)
        self._edit_toolbar.copy.connect('clicked', self._edit_toolbar_copy_cb)
        self._edit_toolbar.paste.props.visible = False
        toolbox.add_toolbar(_('Edit'), self._edit_toolbar)
        self._edit_toolbar.show()

        self._read_toolbar = ReadToolbar(self._view)
        toolbox.add_toolbar(_('Read'), self._read_toolbar)
        self._read_toolbar.show()

        self._view_toolbar = ViewToolbar(self._view)
        toolbox.add_toolbar(_('View'), self._view_toolbar)
        self._view_toolbar.show()
        self.set_toolbox(toolbox)
        toolbox.show()

        self.vbox = gtk.VBox()
        self.set_canvas(self.vbox)
        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        scrolled.props.shadow_type = gtk.SHADOW_NONE
        scrolled.add(self._view)
        self.progress = gtk.ProgressBar()
        self.progress.set_size_request(-1, 50)
        self.vbox.pack_start( scrolled )

        # Set up for idle suspend
        self._idle_timer = 0
        self._service = None

        # start with sleep off
        self._sleep_inhibit = True

        if os.path.exists(os.path.expanduser("~/ebook-enable-sleep")):
            try:
                bus = dbus.SystemBus()
                proxy = bus.get_object(_HARDWARE_MANAGER_SERVICE, _HARDWARE_MANAGER_OBJECT_PATH)
                self._service = dbus.Interface(proxy, _HARDWARE_MANAGER_INTERFACE)
                scrolled.props.vadjustment.connect("value-changed", self._user_action_cb)
                scrolled.props.hadjustment.connect("value-changed", self._user_action_cb)
                self.connect("focus-in-event", self._focus_in_event_cb)
                self.connect("focus-out-event", self._focus_out_event_cb)
                self.connect("notify::active", self._now_active_cb)
            except dbus.DBusException, e:
                logging.info('Hardware manager service not found, no idle suspend.')

        self.hellotube = None  # Shared session

        # get the Presence Service
        self.pservice = presenceservice.get_instance()
        name, path = self.pservice.get_preferred_connection()
        self.tp_conn_name = name
        self.tp_conn_path = path
        self.conn = telepathy.client.Connection(name, path)

        # Buddy object for you
        self.whoIAskedToBorrowFrom = None
        owner = self.pservice.get_owner()
        self.owner = owner
        #whoami?
        key = profile.get_pubkey()
        keyHash = util._sha_data(key)
        self.hashedKey = util.printable_hash(keyHash)
        self.instanceId = self._activity_id
        self.nickName = profile.get_nick_name()

        self.whoIAskedToBorrowFrom = None
        self.DOWNLOADED_FROM_BUDDY = False
        self.buddyTimeOutTime = 30000

#        for testing...
#        handle.uri = "file:///root/fw9.pdf"
#        self._load_document(handle.uri)

        #listen for sharing events...
        self.connect('shared', self._shared_cb)

        # start on the read toolbar
        self.toolbox.set_current_toolbar(_TOOLBAR_READ)

        if self._shared_activity:
            self.vbox.pack_end(self.progress, expand=False)
            self._tried_buddies = []
            if self.get_shared():
                # we've already joined
                self._joined_cb()
            else:
                self.connect('joined', self._joined_cb)

        self.show_all()

    def read_file(self, file_path):
        #we have our file
        self.vbox.remove(self.progress)

        #the path from the datastore is only reliable at the time this call is made, so make our own copy of the bits
        #the filename is nonsense, and rainbow should ensure we can name it whatever we like anyway.
        self._filepath = "/tmp/" + self.hashedKey
        shutil.copyfile(file_path, self._filepath)
        logging.debug('read_file: ' + file_path)
        self._load_document('file://' + file_path)

    def _now_active_cb(self, widget, pspec):
        if self.props.active:
            # Now active, start initial suspend timeout
            if self._idle_timer > 0:
                gobject.source_remove(self._idle_timer)
            self._idle_timer = gobject.timeout_add(15000, self._suspend_cb)
            self._sleep_inhibit = False
        else:
            # Now inactive
            self._sleep_inhibit = True

    def _focus_in_event_cb(self, widget, event):
        self._sleep_inhibit = False
        self._user_action_cb(self)

    def _focus_out_event_cb(self, widget, event):
        self._sleep_inhibit = True

    def _user_action_cb(self, widget):
        if self._idle_timer > 0:
            gobject.source_remove(self._idle_timer)
        self._idle_timer = gobject.timeout_add(5000, self._suspend_cb)

    def _suspend_cb(self):
        # If the machine has been idle for 5 seconds, suspend
        self._idle_timer = 0
        if not self._sleep_inhibit:
            self._service.set_kernel_suspend()
        return False


    def write_file(self, file_path):
        # Don't do anything here, file has already been saved
        pass

    def _get_document(self):
        if (self._document != None):
            logging.debug("Why get the document when we've already got it?")
            return

        next_buddy = None
        # Find the next untried buddy with an IP4 address we can try to
        # download the document from
        for buddy in self._shared_activity.get_joined_buddies():
            if buddy.props.owner:
                continue

            buddyKeyHash = util._sha_data( buddy.props.key )
            buddyHashedKey = util.printable_hash( buddyKeyHash )
            if not buddyHashedKey in self._tried_buddies:
                if buddy.props.ip4_address:
                    next_buddy = buddy
                    break

        if not next_buddy:
            self.progress.set_text(_("Couldn't find a buddy to get the document from."))
            return False

        gobject.idle_add(self._download_document, buddy)
        return False

    def _download_document(self, buddy):
        logging.debug("about to tube download the document")
        self.progress.set_fraction( 0 )
        self.progress.set_text( _("Getting the document from") + " " + buddy.props.nick )
        buddyKeyHash = util._sha_data( buddy.props.key )
        buddyHashedKey = util.printable_hash( buddyKeyHash )
        self.whoIAskedToBorrowFrom = buddyHashedKey
        self.ASKING_ANOTHER_XO_FOR_PDF_TIMEOUT = gobject.timeout_add(self.buddyTimeOutTime, self._haveWeDownloadedYetCb)
        self.hellotube.Hello( self.hashedKey, buddyHashedKey )

    def _haveWeDownloadedYetCb(self):
        if (self._document):
            gobject.source_remove(self.ASKING_ANOTHER_XO_FOR_PDF_TIMEOUT)
        else:
            logging.debug("We never got the doc we asked for; this sux.  let's ask someone else, not " + str(self.whoIAskedToBorrowFrom))
            if (self.whoIAskedToBorrowFrom != None):
                self._tried_buddies.append( self.whoIAskedToBorrowFrom )

            self._get_document()
        return False

    def _load_document(self, filepath):
        if self._document:
            del self._document

        self._document = evince.factory_get_document(filepath)
        self._view.set_document(self._document)
        self._edit_toolbar.set_document(self._document)
        self._read_toolbar.set_document(self._document)

        #todo: should this information be set too when it comes over the mesh?
        if not self._jobject.metadata['title_set_by_user'] == '1':
            info = self._document.get_info()
            if info and info.title:
                self.metadata['title'] = info.title

        self.whoIAskedToBorrowFrom = None  #i have the pdf, i do not want another copy, no siree!

    def _view_notify_has_selection_cb(self, view, pspec):
        self._edit_toolbar.copy.set_sensitive(self._view.props.has_selection)

    def _edit_toolbar_copy_cb(self, button):
        self._view.copy()

    def _key_press_event_cb(self, widget, event):
        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname == 'c' and event.state & gtk.gdk.CONTROL_MASK:
            self._view.copy()

    def _shared_cb(self, activity):
        self._logger.debug('My activity was shared')
        self._setup()

        self._logger.debug('This is my activity: making a tube...')
        id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube( SERVICE, {})

    def _setup(self):
        #sets up the tubes...
        if self._shared_activity is None:
            self._logger.error('Failed to share or join activity')
            return

        bus_name, conn_path, channel_paths = self._shared_activity.get_channels()

        # Work out what our room is called and whether we have Tubes already
        room = None
        tubes_chan = None
        text_chan = None
        for channel_path in channel_paths:
            channel = telepathy.client.Channel(bus_name, channel_path)
            htype, handle = channel.GetHandle()
            if htype == telepathy.HANDLE_TYPE_ROOM:
                self._logger.debug('Found our room: it has handle#%d "%s"', handle, self.conn.InspectHandles(htype, [handle])[0])
                room = handle
                ctype = channel.GetChannelType()
                if ctype == telepathy.CHANNEL_TYPE_TUBES:
                    self._logger.debug('Found our Tubes channel at %s', channel_path)
                    tubes_chan = channel
                elif ctype == telepathy.CHANNEL_TYPE_TEXT:
                    self._logger.debug('Found our Text channel at %s', channel_path)
                    text_chan = channel

        if room is None:
            self._logger.error("Presence service didn't create a room")
            return
        if text_chan is None:
            self._logger.error("Presence service didn't create a text channel")
            return

        # Make sure we have a Tubes channel - PS doesn't yet provide one
        if tubes_chan is None:
            self._logger.debug("Didn't find our Tubes channel, requesting one...")
            tubes_chan = self.conn.request_channel(telepathy.CHANNEL_TYPE_TUBES, telepathy.HANDLE_TYPE_ROOM, room, True)

        self.tubes_chan = tubes_chan
        self.text_chan = text_chan

        tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal('NewTube', self._new_tube_cb)

    def _joined_cb(self, activity):
        if not self._shared_activity:
            return

        self._logger.debug('Joined an existing shared activity')
        self._setup()

        self._logger.debug('This is not my activity: waiting for a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes( reply_handler=self._list_tubes_reply_cb, error_handler=self._list_tubes_error_cb)

    def _list_tubes_reply_cb(self, tubes):
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        self._logger.error('ListTubes() failed: %s', e)

    def _new_tube_cb(self, id, initiator, type, service, params, state):
        self._logger.debug('New tube: ID=%d initator=%d type=%d service=%s params=%r state=%d', id, initiator, type, service, params, state)
        if (type == telepathy.TUBE_TYPE_DBUS and service == SERVICE):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)
            tube_conn = TubeConnection(self.conn, self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], id, group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])
            self.hellotube = HelloTube(tube_conn, self._get_buddy, self._filepath, self.hashedKey, self._logger)

            if (self._document == None):
                self._logger.debug("i am new to this book club.  i will go get the book now")
                self.hellotube.connect("filepart", self._filepartCb)
                self._get_document()

    def _get_buddy(self, cs_handle):
        """Get a Buddy from a channel specific handle."""
        self._logger.debug('Trying to find owner of handle %u...', cs_handle)
        group = self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP]
        my_csh = group.GetSelfHandle()
        self._logger.debug('My handle in that group is %u', my_csh)
        if my_csh == cs_handle:
            handle = self.conn.GetSelfHandle()
            self._logger.debug('CS handle %u belongs to me, %u', cs_handle, handle)
        elif group.GetGroupFlags() & telepathy.CHANNEL_GROUP_FLAG_CHANNEL_SPECIFIC_HANDLES:
            handle = group.GetHandleOwners([cs_handle])[0]
            self._logger.debug('CS handle %u belongs to %u', cs_handle, handle)
        else:
            handle = cs_handle
            logger.debug('non-CS handle %u belongs to itself', handle)
            # XXX: deal with failure to get the handle owner
            assert handle != 0
        return self.pservice.get_buddy_by_telepathy_handle(self.tp_conn_name, self.tp_conn_path, handle)

    def _filepartCb( self, objectThatSentTheSignal, part, numparts, filename, bytes, borrower, lender, sender):
        self._logger.debug( str(part) + " of " + str(numparts) + " from " + str(borrower) + " for " + str(lender) )
        if (self._document != None):
            self._logger.debug("_filepartCb: we already have the document, so disregard these messages " + str(part) + "/" + str(numparts))
            return
        elif (lender != self.whoIAskedToBorrowFrom):
            self._logger.debug("_filepartCb: i didn't ask for the book from this guy " + str(lender) + ", but from this guy: " + str(borrower) )
            return
        elif (borrower != self.hashedKey):
            self._logger.debug("_filepartCb: i am not the borrower asking for this book, but this guy is: " + str(borrower) )
            return

        self._logger.debug("cool, this part is for me!  appending...")
        gobject.source_remove(self.ASKING_ANOTHER_XO_FOR_PDF_TIMEOUT)
        self.ASKING_ANOTHER_XO_FOR_PDF_TIMEOUT = gobject.timeout_add(self.buddyTimeOutTime, self._haveWeDownloadedYetCb)

        #update the progress bar
        frac = (part+0.0)/(numparts+0.0)
        self.progress.set_fraction(frac)

        #so, this is who you asked from and they are talking to you
        #we presume here that we will use rainbow and have our own place to save without other files in the way
        filename = os.path.basename(filename)
        filepath = os.path.join("/tmp", filename)

        f = open(filepath, 'a+').write(bytes)
        if part == numparts:
            self._logger.debug('Finished receiving file %s' % filename)
            self._load_document( "file://" + filepath )
            self.vbox.remove(self.progress)

            #save to our own datastore object
            if not self._jobject.file_path:
                self.DOWNLOADED_FROM_BUDDY = True
                self._jobject.file_path = filepath
                self._filepath = filepath

            self.hellotube.setThePdfPath( self._filepath )
            #all done listening for that noise, we got our pdf and we're going to read it, not ask for it in pieces any more
            self.hellotube.remove_filepart_handler()


class HelloTube(ExportedGObject):
    """The bit that talks over the TUBES!!!"""

    __gsignals__ = {
        'filepart':
            (gobject.SIGNAL_RUN_FIRST, None, [object,object,object,object,object,object,object])
    }

    def __init__(self, tube, get_buddy, thePdfPath, myHashKey, logger ):
        super(HelloTube, self).__init__(tube, PATH)
        self._logger = logger
        self.tube = tube
        self._get_buddy = get_buddy  # Converts handle to Buddy object
        self.myHashKey = myHashKey
        self.thePdfPath = thePdfPath
        if (self.thePdfPath != None):
            self.tube.add_signal_receiver(self.hello_cb, 'Hello', IFACE, path=PATH, sender_keyword='sender')
        else:
            self.add_filepart_handler()

    def setThePdfPath( self, pdfPath ):
        self.thePdfPath = pdfPath
        if (self.thePdfPath != None):
            self.tube.add_signal_receiver(self.hello_cb, 'Hello', IFACE, path=PATH, sender_keyword='sender')
        else:
            self._logger.debug("Damn! We didn't really get the pdf when we asked for it!")

    @signal(dbus_interface=IFACE, signature='ss') #dual s for 2x strings
    def Hello(self, borrower, lender):
        """Say Hello to whoever else is in the tube."""
        self._logger.debug('I said Hello.  Anyone got a pdf for me to read?')

    def hello_cb(self, borrower, lender, sender=None):
        """Somebody Hello'd me. I should share with them my pdf.  i hope they like to read bookz!"""
        self._logger.debug("hello_cb from " + borrower + " for " + sender )
        if sender == self.tube.get_unique_name():
            self._logger.debug("sender is my bus name, so ignore my own signal")
            return
        elif (borrower == self.myHashKey):
            self._logger.debug('excuse me?  you are asking me to share this with myself?')
            return
        elif (self.thePdfPath == None):
            self._logger.debug('i dont have the pdf.  there has been a mistake')
            return
        elif (lender != self.myHashKey):
            self._logger.debug('i do indeed have this pdf, but ive only overheard you asking someone else for it')
            return

        #you should not be here if you don't have the pdf.
        self._logger.debug("ya, i have that pdf, thanks for asking!  here it is!")
        self.send_file( self.thePdfPath, borrower, lender )

    def add_filepart_handler(self):
        """Hook up signal receiver for SendFilePart."""
        self.SENDFILE_ID = self.tube.add_signal_receiver( self.filepart_cb, 'SendFilePart', IFACE, path=PATH, sender_keyword='sender', byte_arrays=True)

    def remove_filepart_handler(self):
        if (self.SENDFILE_ID == None):
            self._logger.debug("unable to remove signal because we were never listening for it!")
            return
        self.tube.remove_signal_receiver(self.SENDFILE_ID)

    @signal(dbus_interface=IFACE, signature='suuayss')
    def SendFilePart(self, filename, part, numparts, bytes, borrower, lender):
        """Signal which sends part of a file.

        filename -- string, filename to send
        part -- integer, number of this part.
        numparts -- integer, total number of parts.
        bytes -- the bytes making up this part of the file.

        example: self.SendFilePart(1, 1, '<html></html>')
        """
        pass

    def send_file(self, filename, borrower, lender ):
        """Send a file over the D-Bus Tube"""
        size = os.path.getsize(filename)
        f = open(filename)
        chunk_size = 1000
        chunks = size / chunk_size

        if (size%chunk_size != 0):
            chunks += 1

        for chunk in range(chunks):
            bytes = f.read(chunk_size)
            self._logger.debug("sending " + str(chunk+1) + " of " + str(chunks) + " from " + borrower + " to " + lender )
            self.SendFilePart(os.path.basename(filename), chunk+1, chunks, bytes, borrower, lender)

        f.close()

    def filepart_cb(self, filename, part, numparts, bytes, borrower, lender, sender=None):
        """Receive part of a file.

        filename -- filename sent
        part -- integer, number of this part.
        numparts -- expected number of parts.
        bytes -- the bytes making up this part of the file.
        """
        if sender == self.tube.get_unique_name():
            # sender is my bus name, so ignore my own signal
            return

        self.emit( "filepart", part, numparts, filename, bytes, borrower, lender, sender)