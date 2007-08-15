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

class Recorded:

	def __init__( self ):
		self.type = -1
		self.time = None
		self.photographer = None
		self.name = None
		self.colorStroke = None
		self.colorFill = None
		self.hashKey = None
		self.mediaMd5 = None
		self.thumbMd5 = None

		#when you are datastore-serialized, you get one of these ids...
		self.datastoreId = None

		#transient... when just taken or taken out of the datastore you get these guys
		self.media = None
		self.thumb = None
		self.mediaFilename = None
		self.thumbFilename = None
		self.thumbPixbuf = None

		#assume you took the picture
		self.buddy = False