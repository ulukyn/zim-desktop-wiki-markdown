# -*- coding: utf-8 -*-

# Copyright 2015 Tobias Haupenthal <thaupenthal@xdn.de>

import gtk
import gtksourceview2
import pango
import logging

logger = logging.getLogger('zim.plugin.tableeditor')

from zim.plugins import PluginClass, WindowExtension, extends
from zim.actions import action
from zim.utils import WeakSet
from zim.objectmanager import ObjectManager, CustomObjectClass
from zim.config import String, Boolean
from zim.gui.widgets import Dialog, ScrolledWindow
from zim.gui.objectmanager import CustomObjectWidget, TextViewWidget
from zim.formats.html import html_encode
from zim.config.dicts import ConfigDict, String

OBJECT_TYPE = 'table'

if gtksourceview2:
	lm = gtksourceview2.LanguageManager()
	lang_ids = lm.get_language_ids()
	lang_names = [lm.get_language(i).get_name() for i in lang_ids]

	LANGUAGES = dict((lm.get_language(i).get_name(), i) for i in lang_ids)
else:
	LANGUAGES = {}


class TableEditorPlugin(PluginClass):

	plugin_info = {
		'name': _('Table Editor'), # T: plugin name
		'description': _('''\
**IN DEVELOPMENT**
This plugin allows inserting 'Tables' in the page. These will be shown as TreeView widgets.
Exporting them to various formats (i.e. HTML/LaTeX) completes the feature set.
'''), # T: plugin description
		'object_types': (OBJECT_TYPE, ),
		'help': 'Plugins:Table Editor',
		'author': 'Tobias Haupenthal',
	}

	plugin_preferences = (
		# key, type, label, default
		('auto_indent', 'bool', _('Auto indenting'), True),
			# T: preference option for sourceview plugin
		('smart_home_end', 'bool', _('Smart Home key'), True),
			# T: preference option for sourceview plugin
		('highlight_current_line', 'bool', _('Highlight current line'), False),
			# T: preference option for sourceview plugin
		('show_right_margin', 'bool', _('Show right margin'), False),
			# T: preference option for sourceview plugin
		('right_margin_position', 'int', _('Right margin position'), 72, (1, 1000)),
			# T: preference option for sourceview plugin
		('tab_width', 'int', _('Tab width'), 4, (1, 80)),
			# T: preference option for sourceview plugin
	)

	def __init__(self, config=None):
		PluginClass.__init__(self, config)
		self.connectto(self.preferences, 'changed', self.on_preferences_changed)

	def create_table(self, attrib, text):
		'''Factory method for Table objects'''
		obj = TableViewObject(attrib, text, self.preferences)
		return obj

	def on_preferences_changed(self, preferences):
		'''Update preferences on open objects'''
		for obj in ObjectManager.get_active_objects(OBJECT_TYPE):
			obj.preferences_changed()


@extends('MainWindow')
class MainWindowExtension(WindowExtension):

	uimanager_xml = '''
		<ui>
		<menubar name='menubar'>
			<menu action='insert_menu'>
				<placeholder name='plugin_items'>
					<menuitem action='insert_table'/>
				</placeholder>
			</menu>
		</menubar>
		</ui>
	'''

	def __init__(self, plugin, window):
		WindowExtension.__init__(self, plugin, window)
		ObjectManager.register_object(OBJECT_TYPE, self.plugin.create_table)
			# XXX use pageview attribute instead of singleton

	def teardown(self):
		ObjectManager.unregister_object(OBJECT_TYPE)

	@action(_('Code Block'), readonly=False) # T: menu item
	def insert_table(self):
		'''Inserts new SourceView'''
		logger.fatal("InsertCodeBlockDialog")
		#lang = InsertCodeBlockDialog(self.window.ui).run() # XXX
		lang = "php"
		if not lang:
			return # dialog cancelled
		else:
			obj = self.plugin.create_table({'type': OBJECT_TYPE, 'lang': lang, 'kkk':'kkk'}, '')
			pageview = self.window.pageview
			pageview.insert_table_at_cursor(obj)


class TableViewObject(CustomObjectClass):

	OBJECT_ATTR = {
		'type': String('table'),
		#'linenumbers': Boolean(True),
	}

	def __init__(self, attrib, data, preferences):
		data = "Hallo"
		self._attrib = ConfigDict(attrib)
		self._attrib.define(self.OBJECT_ATTR)
		self._data = data if data is not None else ''
		self.modified = False
		self.preferences = preferences
		self.buffer = None
		self._widgets = WeakSet()

	def get_widget(self):
		if not self.buffer:
			self.buffer = gtksourceview2.Buffer()
			self.buffer.set_text(self._data)
			self.buffer.connect('modified-changed', self.on_modified_changed)
			self.buffer.set_highlight_matching_brackets(True)
			self.buffer.set_modified(False)
			self._data = None


		widget = TableViewWidget(self.buffer)
		self._widgets.add(widget)

		widget.set_preferences(self.preferences)
		return widget



	def preferences_changed(self):
		for widget in self._widgets:
			widget.set_preferences(self.preferences)

	def on_modified_changed(self, buffer):
		# Table changed, set change on oject, reset state of
		# table buffer so we get a new signal with next change
		if buffer.get_modified():
			logger.fatal("buffer changed")
			logger.fatal(buffer)
			self.set_modified(True)
			buffer.set_modified(False)

	def get_data(self):
		'''Returns data as text.'''
		if self.buffer:
			bounds = self.buffer.get_bounds()
			text = self.buffer.get_text(bounds[0], bounds[1])
			text += '\n' # Make sure we always have a trailing \n
			return text
		else:
			return self._data

	def dump(self, format, dumper, linker=None):
		logger.fatal("DUMPING")
		if format == "html":
			logger.fatal("HTML")
			if self._attrib['lang']:
				# class="brush: language;" works with SyntaxHighlighter 2.0.278
				# by Alex Gorbatchev <http://alexgorbatchev.com/SyntaxHighlighter/>
				# TODO: not all GtkSourceView language ids match with SyntaxHighlighter
				# language ids.
				# TODO: some template instruction to be able to use other highlighters as well?
				output = ['<pre class="brush: %s;">\n' % html_encode(self._attrib['lang'])]
			else:
				output = ['<pre>\n']
			data = self.get_data()
			data = html_encode(data) # XXX currently dumper gives encoded lines - NOK
			if self._attrib['linenumbers']:
				for i, l in enumerate(data.splitlines(1)):
					output.append('%i&nbsp;' % (i+1) + l)
			else:
				output.append(data)
			output.append('</pre>\n')
			return output
		return CustomObjectClass.dump(self, format, dumper, linker)

	def set_language(self, lang):
		'''Set language in SourceView.'''
		self._attrib['lang'] = lang
		self.set_modified(True)

		if self.buffer:
			if lang is None:
				self.buffer.set_language(None)
			else:
				self.buffer.set_language(lm.get_language(lang))

	def show_line_numbers(self, show):
		'''Toggles line numbers in SourceView.'''
		self._attrib['linenumbers'] = show
		self.set_modified(True)

		for widget in self._widgets:
			widget.view.set_show_line_numbers(show)


class TableViewWidget(CustomObjectWidget):

	def __init__(self, data):
		self._data = data

		#tree = self.get_treeview()
		#logger.fatal(tree)
		#raise
		#logger.fatal(self._data.get('cols'))


		gtk.EventBox.__init__(self)
		self.set_border_width(5)
		self._has_cursor = False
		self._resize = True

		# Add vbox and wrap it to have a shadow around it
		self.vbox = gtk.VBox() #: C{gtk.VBox} to contain widget contents
		win = ScrolledWindow(self.vbox, gtk.POLICY_NEVER, gtk.POLICY_NEVER, gtk.SHADOW_IN)
		self.add(win)

		self.set_has_cursor(True)
		self.buffer = buffer
		#self.obj = obj

		logger.fatal( self.buffer)
		logger.fatal( "--")
		#logger.fatal(self.obj)



		self.liststore = gtk.ListStore(str, str)
		self.liststore.append(["Fedora", "http://fedoraproject.org/"])
		treeview = gtk.TreeView(model=self.liststore)
		self.view = treeview

		renderer_text = gtk.CellRendererText()
		column_text = gtk.TreeViewColumn("Text", renderer_text, text=0)
		treeview.append_column(column_text)
		#self.view = self.create_treeview()

		# simple toolbar
		#~ bar = gtk.HBox() # FIXME: use gtk.Toolbar stuff
		#~ lang_selector = gtk.combo_box_new_text()
		#~ lang_selector.append_text('(None)')
		#~ for l in lang_names: lang_selector.append_text(l)
		#~ try:
			#~ lang_selector.set_active(lang_ids.index(self._attrib['lang'])+1)
			#~ self.set_language(self._attrib['lang'] or None, False)
		#~ except (ValueError, KeyError):
			#~ lang_selector.set_active(0)
			#~ self.set_language(None, False)
		#~ lang_selector.connect('changed', self.on_lang_changed)
		#~ bar.pack_start(lang_selector, False, False)

		#~ line_numbers = gtk.ToggleButton('Line numbers')
		#~ try:
			#~ line_numbers.set_active(self._attrib['linenumbers']=='true')
			#~ self.show_line_numbers(self._attrib['linenumbers'], False)
		#~ except (ValueError, KeyError):
			#~ line_numbers.set_active(True)
			#~ self.show_line_numbers(True, False)
		#~ line_numbers.connect('toggled', self.on_line_numbers_toggled)
		#~ bar.pack_start(line_numbers, False, False)

		# TODO: other toolbar options
		# TODO: autohide toolbar if textbuffer is not active

		# Pack everything
		#~ self.vbox.pack_start(bar, False, False)
		win = ScrolledWindow(self.view, gtk.POLICY_AUTOMATIC, gtk.POLICY_NEVER, gtk.SHADOW_NONE)
			# only horizontal scroll
		self.vbox.pack_start(win)

		# Hook up signals
		#self.view.connect('populate-popup', self.on_populate_popup)
		self.view.connect('move-cursor', self.on_move_cursor)

	def create_treeview(self):
		table = self._data
		aligns = table.get('cols').split(',')
		nrcols = len(aligns)
		cols = [str]*nrcols
		liststore = gtk.ListStore(*cols)
		treeview = gtk.Treeview(liststore)

		for headcol in table.findall('thead/th'):
			renderer_editabletext = gtk.CellRendererText()
			renderer_editabletext.set_property("editable", True)
			column_editabletext = gtk.TreeViewColumn(headcol, renderer_editabletext, markup=1)
			treeview.append_column(column_editabletext)
			# renderer_editabletext.connect("edited", self.on_cell_changed)
			# renderer_editabletext.connect("editing-started", self.on_cell_editing_started)

		for row in table.findall('trow'):
			for i, cell in enumerate(row):
				pass



		return treeview



	def set_preferences(self, preferences):
		pass
		#self.view.set_auto_indent(preferences['auto_indent'])
		#self.view.set_smart_home_end(preferences['smart_home_end'])
		#self.view.set_highlight_current_line(preferences['highlight_current_line'])
		#self.view.set_right_margin_position(preferences['right_margin_position'])
		#self.view.set_show_right_margin(preferences['show_right_margin'])
		#self.view.set_tab_width(preferences['tab_width'])

	def on_move_cursor(self, view, step_size, count, extend_selection):
		# If you try to move the cursor out of the tableditor
		# release the cursor to the parent textview
		buffer = view.get_buffer()
		iter = buffer.get_iter_at_mark(buffer.get_insert())
		if (iter.is_start() or iter.is_end()) \
		and not extend_selection:
			if iter.is_start() and count < 0:
				self.release_cursor(POSITION_BEGIN)
				return None
			elif iter.is_end() and count > 0:
				self.release_cursor(POSITION_END)
				return None

		return None # let parent handle this signal

	#~ def on_lang_changed(self, selector):
		#~ '''Callback for language selector'''
		#~ lang = selector.get_active()
		#~ self.set_language(lang_ids[lang-1] if lang>0 else '')

	#~ def on_line_numbers_toggled(self, button):
		#~ '''Callback for toggling line numbers.'''
		#~ self.show_line_numbers(button.get_active())

	def on_populate_popup(self, view, menu):
		menu.prepend(gtk.SeparatorMenuItem())

		def activate_linenumbers(item):
			self.obj.show_line_numbers(item.get_active())

		item = gtk.CheckMenuItem(_('Show Line Numbers'))
			# T: preference option for tableeditor plugin
		item.set_active(self.obj._attrib['linenumbers'])
		item.connect_after('activate', activate_linenumbers)
		menu.prepend(item)


		item = gtk.MenuItem(_('Syntax'))
		submenu = gtk.Menu()
		item.set_submenu(submenu)
		menu.prepend(item)

		menu.show_all()

	# TODO: undo(), redo() stuff