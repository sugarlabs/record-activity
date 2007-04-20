import os
import gtk
from gtk import gdk
import gobject
import math
import cairo
import pygtk
pygtk.require('2.0')
import rsvg
import pango

from button import Button
from p5_button import P5Button
from polygon import Polygon
from color import Color


class Thumbnails(P5Button):

	def __init__(self, pc, type):
		P5Button.__init__(self)

		self.c = pc
		self.TYPE = type
		if (self.TYPE == self.c.THUMB_PHOTO):
			self.c._thuPho = self
		elif (self.TYPE == self.c.THUMB_VIDEO):
			self.c._thuVid = self

		self.noloop()

		self.bw = 155
		self.tw = 107
		self.th = 80
		self.tscale = float(0.1671875)
		self.numButts = 7
		self.buttXOffset = 0
		self.tpoly = None
		self.dpoly = None
		self.buttLeft = None
		self.buttRight = None

		self.thumbs = []
		self.deletes = []


	def addThumb(self, thumbImg, mpath):
		if (self.buttLeft == None):
			self.buttXOffset = (self.c._w - (self.bw*self.numButts))/2

			d = 15 + 8
			xs = []
			ys = []
			xs.append(d)
			ys.append(d)
			xs.append(d+self.tw)
			ys.append(d)
			xs.append(d+self.tw)
			ys.append(d+self.th)
			xs.append(d)
			ys.append(self.th)
			self.tpoly = Polygon( xs, ys )

			dxs = []
			dys = []
			dxs.append( (d + self.tw)-25 )
			dys.append( 5 + d + self.th )
			dxs.append( d + self.tw )
			dys.append( 5 + d + self.th )
			dxs.append( d + self.tw )
			dys.append( 5 + d + self.tw + 25 )
			dxs.append( (d + self.tw)-25 )
			dys.append( 5 + d + self.tw + 25 )
			self.dpoly = Polygon( dxs, dys )

			backW = 40
			ltxs = []
			ltys = []
			ltxs.append(0)
			ltxs.append(backW)
			ltxs.append(backW)
			ltys.append(75)
			ltys.append(25)
			ltys.append(125)
			ltpoly = Polygon( ltxs, ltys )
			self.buttLeft = Button( ltpoly, 0, 0 )
			self.buttLeft.setActionCommand("go-left")
			self.buttLeft.addActionListener(self)
			rtxs = []
			rtys = []
			rtxs.append(0)
			rtxs.append(backW)
			rtxs.append(0)
			rtys.append(25)
			rtys.append(75)
			rtys.append(125)
			rtpoly = Polygon( rtxs, rtys )
			self.buttRight = Button( rtpoly, self._w-backW, 0 )
			self.buttRight.setActionCommand("go-right")
			self.buttRight.addActionListener(self)
			self._butts.append(self.buttLeft)
			self._butts.append(self.buttRight)

		#only keep 7 buttons around
		if ( len(self.thumbs)>=self.numButts):
			byeButt = self.thumbs.pop(0)
			byeButt.removeActionListener(self)
			self._butts.remove(byeButt)
			byeDel = self.deletes.pop(0)
			byeDel.removeActionListener(self)
			self._butts.remove(byeDel)

		#make the new button
		button = Button( self.tpoly, 0, 0 )

		button.setImage(thumbImg)
		button.setActionCommand(mpath)
		button.addActionListener(self)
		self._butts.append(button)
		self.thumbs.append(button)

		delButton = Button(self.dpoly, 0, 0)
		delButton.setActionCommand("delete-"+mpath)
		delButton.addActionListener(self)
		self._butts.append(delButton)
		self.deletes.append(delButton)

		self.updateThumbs()

	def delThumb(self, path):
		del_index = -1
		for i in range( 0, len(self.thumbs) ):
			butt = self.thumbs[i]
			if (butt.getActionCommand() == path):
				del_index = i

		if (del_index != -1):
			thmb = self.thumbs.pop( del_index )
			thmb.removeActionListener(self)
			delt = self.deletes.pop( del_index )
			delt.removeActionListener(self)
			self._butts.remove( thmb )
			self._butts.remove( delt )

		if (self.TYPE == self.c.THUMB_PHOTO):
			self.c.thumbDeleted( path, self.c.photoHash, self )
		elif (self.TYPE == self.c.THUMB_VIDEO):
			self.c.thumbDeleted( path, self.c.movieHash, self )

	def updateThumbs(self):
		#update all buttons' positions here
		for i in range ( 0, len(self.thumbs) ):
			self.thumbs[i]._offX = self.buttXOffset+(i*self.bw)
			self.deletes[i]._offX = self.buttXOffset+(i*self.bw)

		#repaint
		self.redraw()

	def draw(self, ctx, w, h):
		P5Button.draw(self, ctx, w, h )
		self.background( ctx, self.c._colThumbTray, w, h )

		#draw buttons
		ctx.set_antialias( cairo.ANTIALIAS_SUBPIXEL )
		for i in range ( 0, len(self.thumbs) ):
			butt = self.thumbs[i]
			ctx.identity_matrix( )
			ctx.translate( butt._offX, 0 )
			ctx.translate( 15, 15 )
			if (self.TYPE == self.c.THUMB_PHOTO):
				self.c.thumbPhotoSvg.render_cairo(ctx)
				ctx.translate( 8, 8 )
			elif (self.TYPE == self.c.THUMB_VIDEO):
				self.c.thumbVideoSvg.render_cairo(ctx)
				ctx.translate( 9, 21 )

			ctx.set_source_surface(butt._img, 0, 0)
			ctx.paint()
			ctx.identity_matrix( )
			ctx.translate( butt._offX, 0 )
			ctx.translate( 15, 15 )
			ctx.translate( 8, 8 )
			ctx.translate( (self.tw-25), (5+self.th) )
			self.c.closeSvg.render_cairo(ctx)

		if (self.buttLeft != None):
			if (self.isDrawLeftButton()):
				ctx.identity_matrix()
				ctx.translate( self.buttLeft._offX, self.buttLeft._offY )
				self.fillShape( ctx, self.buttLeft._poly, self.c._colBlack )
			if (self.isDrawRightButton()):
				ctx.identity_matrix()
				ctx.translate( self.buttRight._offX, self.buttRight._offY )
				self.fillShape( ctx, self.buttRight._poly, self.c._colBlack )

		ctx.set_antialias( cairo.ANTIALIAS_NONE )

	def removeButtons(self):
		for each in self.thumbs:
			each.removeActionListener(self)
			self._butts.remove(each)
		for each in self.deletes:
			each.removeActionListener(self)
			self._butts.remove(each)
		del self.thumbs[:]
		del self.deletes[:]

	def goLeft(self):
		if (not self.isDrawLeftButton() ):
			return

		self.removeButtons()

		nextStart = self.start() - self.numButts
		if (nextStart < 0):
			nextStart = 0
		last = min( len(self.thmbs()), (nextStart+self.numButts) )
		self.setUpThumbs(nextStart, last)

	def goRight(self):
		if (not self.isDrawRightButton() ):
			return

		self.removeButtons()
		
		nextStart = self.start() + self.numButts
		nextStart = min( nextStart, len(self.thmbs())-self.numButts )
		nextStart = max( 0, nextStart )
		last = min( len(self.thmbs()), (nextStart+self.numButts) )
		self.setUpThumbs(nextStart, last)

	def setUpThumbs(self, nextStart, last):
		if (self.TYPE == self.c.THUMB_PHOTO):
			self.c.setupThumbs(self.c.photoHash, self, nextStart, last)
		elif (self.TYPE == self.c.THUMB_VIDEO):
			self.c.setupThumbs(self.c.movieHash, self, nextStart, last)

	def isDrawLeftButton(self):
		if ( self.start() > 0 ):
			return True
		else:
			return False

	def isDrawRightButton(self):
		showin = (self.start() + self.numButts);
		length = len(self.thmbs())
		if ( showin < length ):
			return True
		else:
			return False

	def thmbs(self):
		if (self.TYPE == self.c.THUMB_PHOTO):
			return self.c.photoHash
		if (self.TYPE == self.c.THUMB_VIDEO):
			return self.c.movieHash

	def start(self):
		if (self.TYPE == self.c.THUMB_PHOTO):
			return self.c.thuPhoStart
		if (self.TYPE == self.c.THUMB_VIDEO):
			return self.c.thuVidStart

	def fireButton(self, actionCommand):
		if (self.c.UPDATING):
			return

		if (actionCommand.startswith("go-")):
			if (actionCommand.startswith("go-left")):
				self.goLeft()
			else:
				self.goRight()
			return

		if (actionCommand.startswith("delete-")):
			self.delThumb(actionCommand[7:])
			return

		if ( (self.c.SHOW == self.c.SHOW_RECORD) or (self.c.SHOW == self.c.SHOW_PROCESSING) ):
			return

		if (self.TYPE == self.c.THUMB_VIDEO):
			self.c.showVid(actionCommand)
		elif (self.TYPE == self.c.THUMB_PHOTO):
			self.c.showImg(actionCommand)
