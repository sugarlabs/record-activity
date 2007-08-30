#Copyright (c) 2007, Media Modifications Ltd.

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

from sugar import network
from sugar.presence import presenceservice
from sugar import util

import urlparse
import urllib
import posixpath
import shutil
import os

from recorded import Recorded
from color import Color

class MeshXMLRPCServer:
	def __init__( self, pca ):
		self.ca = pca
		#this is ye olde xmlrpc server
		#listen to and talk through this port for xmlrpc, using this here info
		self.server = network.GlibXMLRPCServer(("", self.ca.xmlRpcPort))
		self.server.register_instance(self) #anything witout an _ is callable by all the hos and joes out there

	def newThumbNotice(	self,
						ip,
						mediaMd5, thumbMd5, time, photographer, title, colorStroke, colorFill, hashKey ):

		newRecd = Recorded( self.ca )
		newRecd.type = self.ca.m.TYPE_PHOTO
		newRecd.buddy = True


		newRecd.time = time
		newRecd.photographer = photographer
		newRecd.title = title
		newRecd.hashKey = hashKey
		newRecd.mediaMd5 = mediaMd5
		newRecd.thumbMd5 = thumbMd5

		colorStrokeHex = colorStroke
		colorStroke = Color()
		colorStroke.init_hex( colorStrokeHex )
		newRecd.colorStroke = colorStroke
		colorFillHex = colorFill
		colorFill = Color()
		colorFill.init_hex( colorFillHex )
		newRecd.colorFill =  colorFill

		self.ca.meshClient.requestThumbBits( ip, newRecd )
		print "requested new bits from that other buddy"
		return "successios"



class HttpServer(network.GlibTCPServer):

	def __init__(self, pca):
		self.ca = pca
		server_address = ("", self.ca.httpPort)
		network.GlibTCPServer.__init__(self, server_address, HttpReqHandler);



class HttpReqHandler(network.ChunkedGlibHTTPRequestHandler):

	def translate_path(self, path):
		#todo: what to return here if not returning a file or how to handle errors?
		urlp = urlparse.urlparse(path)
		urls = urlp[2]
		urls = posixpath.normpath(urllib.unquote(urls))
		urlPath = urls.split('/')
		urlPath = filter(None, urlPath)

		params = urlp[4]
		parama = []
		allParams = params.split('&')
		for i in range (0, len(allParams)):
			parama.append(allParams[i].split('='))

		#todo: narrow our search to media and thumbs.
		print( "http parama...", parama )

		#todo: test to make sure file still here and not deleted... and what to return if not there?
		#should be abs path... check it 1st
		reqParam = parama[0][0]
		valid = False
		thumb = False
		if (reqParam == "mediaMd5"):
			thumb = False
			valid = True
		elif (reqParam == "thumbMd5"):
			thumb = True
			valid = True

		if (not valid):
			#todo: better response here?
			return "not_available"

		md5 = parama[0][1]
		print("thumb", thumb, "md5", md5 )
		recd = self.server.ca.m.getByMd5(md5)
		if (recd == None):
			print( "could not find media returning md5" )
			return "not_available"
		else:
			print( "found the md5: ", recd )
			if (thumb):
				path = recd.getThumbFilepath()
			else:
				path = recd.getMediaFilepath()

			if (path == None):
				return "not_available"
			else:
				if (not os.path.exists(path)):
					return "not_available"
				else:
					return path

		return "not_available"

class MeshClient:

	def __init__( self, pca ):
		self.ca = pca

		#stay alert!  buddies might show up at any time!
		print("1 meshClient");
		print("1.1 meshClient: ", self.ca)
		self.my_acty = self.ca._shared_activity #_pservice.get_activity(self.c.activity_id)
		print("1.2 meshClient: ", self.my_acty)
		#self.my_acty_id = self.c._frame.activity_id
		#print( "uid:", self.my_acty_id )

		self.my_acty.connect('buddy-joined', self.buddyJoinedCb)
		print("1.3")
		self.my_acty.connect('buddy-left', self.buddyDepartedCb)
		print("1.4")

		print("1.5", len(self.my_acty.get_joined_buddies()) )
		#if you've just arrived at the playground, take a peruse around
		for buddy in self.my_acty.get_joined_buddies():
			print ("a", buddy.props.nick)
			print ("a", buddy.props.ip4_address)
			print ("a", buddy.props.owner) #me boolean
#			if (buddy.props.owner):
#				print ("a1", buddy.props.key)
#			else:
#				print ("a2", self.bytes_to_string(buddy.props.key))

		print("1.6")


	def buddyJoinedCb( self, activity, buddy ):
		print ("b", buddy.props.nick)
		print ("b", buddy.props.ip4_address)
		print ("b", buddy.props.owner) #me boolean
#		if (buddy.props.owner):
#			print ("b1", buddy.props.key)
#		else:
#			print ("b2", self.bytes_to_string(buddy.props.key))


	def buddyDepartedCb( self, activity, buddy ):
		print ("c", buddy.props.nick)
		print ("c", buddy.props.ip4_address)
		print ("c", buddy.props.owner) #me boolean
#		if (buddy.props.owner):
#			print ("c1", buddy.props.key)
#		else:
#			print ("c2", self.bytes_to_string(buddy.props.key))


	def bytes_to_string(self, bytes):
#		print("bytes_to_string 1")
#		import dbus
#		ret = ''
#		for item in bytes:
#			print( item, "<-->", str(item) )
#			ret = ret + str(item)
#		print("bytes_to_string 2")
#		return ret
		return bytes

	#herein we notify our buddies of some cool stuff we got going on they mights wants to knows abouts
	def notifyBudsOfNewPhoto( self, recd ):

		ps = presenceservice.get_instance()
		me = ps.get_owner()

		for buddy in self.my_acty.get_joined_buddies():
			if (not buddy.props.owner):
				bud = network.GlibServerProxy( "http://%s:%d" % (buddy.props.ip4_address, self.ca.xmlRpcPort))

				bud.newThumbNotice(	str(me.props.ip4_address),
									recd.mediaMd5, recd.thumbMd5,
									recd.time, recd.photographer,
									recd.title,
									recd.colorStroke.hex, recd.colorFill.hex,
									recd.hashKey,
									reply_handler=self.notifyBudsOfNewPhotoCb,
									error_handler=self.notifyBudsOfNewPhotoErrorCb,
									user_data=buddy)


	def notifyBudsOfNewPhotoCb(self, response, user_data):
		print "Response was %s, user_data was %s" % (response, user_data)


	def notifyBudsOfNewPhotoErrorCb(self, error, user_data):
		print "We've a no go erroro! ", user_data


	def requestThumbBits(self, ip, recd):
		ps = presenceservice.get_instance()
		me = ps.get_owner()

		uri = "http://" + str(ip) + ":" + str(self.ca.httpPort) + "/media?thumbMd5=" + str(recd.thumbMd5)
		getter = network.GlibURLDownloader( uri )
		getter.connect( "finished", self.thumbDownloadResultCb, recd )
		getter.connect( "error", self.thumbDownloadErrorCb, recd )
		getter.start()


	def thumbDownloadResultCb(self, getter, tempfile, suggested_name, recd):
		#todo: handle empty files here... or errors
		print( "thumb says: ", tempfile, suggested_name )

		dest = os.path.join( self.ca.journalPath, suggested_name )
		shutil.copyfile(tempfile, dest)
		os.remove(tempfile)

		recd.thumbFilename = suggested_name
		self.ca.m.addRecd( recd )


	def thumbDownloadErrorCb(self, getter, err, recd):
		print("thumbDownloadError", getter, err, recd )
		#todo: delete that thumb?



	def requestMediaBits(self, recd):
	#todo: don't request this if requesting this already (lock?)
		print("requestingPhotoBits...", len(self.my_acty.get_joined_buddies()))

		photoTakingBuddy = None
		for buddy in self.my_acty.get_joined_buddies():
			if (not buddy.props.owner):

				#todo: this is buggy presenceservice stuff, dcbw is on it.
				#todo: revert this once the bug is fixed
				hashKey = util._sha_data( self.bytes_to_string(buddy.props.key) )
				hashKey = util.printable_hash(hashKey)
				#if (hashKey == recd.hashKey):
				if (buddy.props.nick == recd.photographer):
					photoTakingBuddy = buddy

		print("photoTakingBuddy...", photoTakingBuddy)
		if (photoTakingBuddy != None):
			uri = "http://" + str(photoTakingBuddy.props.ip4_address) + ":" + str(self.ca.httpPort) + "/media?mediaMd5=" + str(recd.mediaMd5)
			getter = network.GlibURLDownloader( uri )
			getter.connect( "finished", self.mediaDownloadResultCb, recd )
			getter.connect( "error", self.mediaDownloadErrorCb, recd )

			#todo: destfile=fullpath
			getter.start()


	def mediaDownloadResultCb(self, getter, tempfile, suggested_name, recd):
		#can this temp file be the same as that temp file?
		dest = os.path.join( self.ca.journalPath, suggested_name )
		shutil.copyfile( tempfile, dest )
		os.remove( tempfile )

		recd.mediaFilename = suggested_name
		recd.downloadedFromBuddy = True

		print( "downloaded media and here it is: " + str(dest) )
		print( "and media filename is: " + recd.mediaFilename )

		self.ca.ui.updateShownMedia( recd )


	def mediaDownloadErrorCb(self, getter, err, recd):
		print("mediaDownloadError", getter, err, recd)