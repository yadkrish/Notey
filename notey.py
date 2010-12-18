#!/usr/bin/env python
import sys
import os
import pygtk
import gtk
import gobject
import urllib
import webbrowser
import datetime
from datetime import datetime as dt
from ConfigParser import SafeConfigParser
from base64 import b64encode
import threading
import tempfile
import win32api


try:
  import win32print
  disable_print = False
except:
  disable_print = True

to_email = ""  

from NoteDB import *
from SimpleNote import *

DEFAULT_TITLE = "Notey"
DATEFMT = "%Y-%m-%d %H:%M:%S"

gobject.threads_init()

class SimpleNoteDeleter(threading.Thread):
  def __init__(self, notey, title):
    super(SimpleNoteDeleter, self).__init__()
    self.notey = notey
    self.snDB  = notey.snDB
    self.title = title
  
  def run(self):
    try:
      gobject.idle_add(self.notey.eventProgressBar.pulse)
      gobject.idle_add(self.notey.eventProgressBar.set_text, 'Deleting...')
      note = self.snDB.find_note(self.title)
      note.deleted = 1
      self.snDB.update_note(note)
      gobject.idle_add(self.notey.eventProgressBar.set_text, 'Deleted in simple-note')
    except KeyError:
      pass
    except Exception as e:
      print "In SimpleNoteDeleter with title = ", self.title
      print e
    

class SimpleNoteSyncer(threading.Thread):
  def __init__(self, notey):
    super(SimpleNoteSyncer, self).__init__()
    self.notey = notey
    self.snDB  = notey.snDB
    self.notedb = notey.notedb
  
  def run(self):
    self.sync_simplenote()

  def sync_simplenote(self):
    if self.notey.snDB:
      gobject.idle_add(self.notey.eventProgressBar.pulse)
      gobject.idle_add(self.notey.eventProgressBar.set_text, 'Syncing...')
      snNotes = [ note for note in self.snDB.index() if note.deleted == 0 ]
      gobject.idle_add(self.notey.eventProgressBar.pulse)
      localNotes = self.notedb.get_index()
      for note in localNotes:
        try:
          snote = self.snDB.find_note(note.title)
          for n in snNotes:
            if n.key == snote.key:
              snNotes.remove(n)
              break
          if float(snote.modifydate) >= note.last_modified:
            self.notedb.update_note(note.title, snote.content, float(snote.modifydate))
          else:
            snote.content = (self.notedb.get_note(note.title)).content
            self.snDB.update_note(snote)
            gobject.idle_add(self.notey.eventProgressBar.pulse)
        except KeyError:
          content = (self.notedb.get_note(note.title)).content
          self.snDB.new_note(note.title, content)
          gobject.idle_add(self.notey.eventProgressBar.pulse)
        except Exception as e:
          print e
      
      for note in snNotes:
        print "'%s'" % (note.title)
        self.notedb.create_note(note.title, note.content, float(note.modifydate))
      
      gobject.idle_add(self.notey.tocList_populate)
      gobject.idle_add(self.notey.eventProgressBar.set_fraction, 0)
      gobject.idle_add(self.notey.eventProgressBar.set_text, 'Signed into simple-note')


class Preferences(object):
  def __init__(self, notey):
    self.config_file = os.path.expanduser('~/.notey.cfg')
    self.config = SafeConfigParser()
    self.config.read([self.config_file])
    self.email = ''
    self.credentials = ''
    self.notey = notey
    try:
      self.email = self.config.get('SimpleNote', 'email')
      self.credentials = self.config.get('SimpleNote', 'credentials')
    except Exception as e:
      print e
      self.config.add_section('SimpleNote')
      self.config.set('SimpleNote', 'email', '')
      self.config.set('SimpleNote', 'credentials', '')
      with open(self.config_file, 'wb') as configfile:
        self.config.write(configfile)
    self.build_ui()
    self.emailEntry.set_text(self.email)
    self.preferencesWindow.show()
  
  def build_ui(self):
    ui_elements = [ 
                    "preferencesWindow",
                    "emailEntry",
                    "passwordEntry",
                    "saveButton",
                    "cancelButton"
                  ]
    builder = gtk.Builder()
    builder.add_from_file( os.path.join( sys.path[0], "preferences.glade" ) )
    
    for elem in ui_elements:
      setattr(self, elem, builder.get_object(elem))
    
    builder.connect_signals(self)

  def on_saveButton_clicked(self, widget, data=None):
    self.email = self.emailEntry.get_text()
    password = self.passwordEntry.get_text()  
    self.config.set('SimpleNote', 'email', self.email)
    self.credentials = b64encode('email=%s&password=%s' % (self.email, password))
    self.config.set('SimpleNote', 'credentials', self.credentials)
    with open(self.config_file, 'wb') as configfile:
      self.config.write(configfile)
    self.notey.simplenote_login()
    self.preferencesWindow.destroy()
  
  def on_cancelButton_clicked(self, widget, data=None):
    self.preferencesWindow.destroy()


     
class Notey(object):
  def __init__(self):
    self.notedb = NoteDBsqlite3(os.path.join( sys.path[0], 'notey.sqlite3' ))
    
    self.title = ""
    self.config = None
    self._build_ui()
    self.tocList_populate()
    self.mainWindow.show()
    self.titleEntry.grab_focus()
    self.simplenote_login()
    
  def read_config(self):
    cfg_file = os.path.expanduser('~/.notey.cfg')
    self.config =  SafeConfigParser()
    self.config.read([cfg_file])       
            
  def simplenote_login(self):
    self.read_config()
    try:
      email = self.config.get('SimpleNote', 'email')
      creds = self.config.get('SimpleNote', 'credentials')
      self.snDB = SimpleNoteDB(email, credentials=creds)
      self.snDB.login()
      self.snDB.index()
      self.eventProgressBar.set_property('visible', True)
      self.eventProgressBar.set_fraction(0)
      self.eventProgressBar.set_text('Signed into simple-note')
      snSyncer = SimpleNoteSyncer(self)
      snSyncer.start()
    except Exception as e:
      self.eventProgressBar.set_property('visible', False)
      print e
    
  def _build_ui(self):
    ui_elements = [ 
                    "mainWindow",
                    "titleEntry",
                    "oneNoteSyncButton",
                    "tocList",
                    "tocListView",
                    "noteText",
                    "noteTextView",
                    "eventProgressBar",
                    "keypressLabel",
                    "cursorPositionLabel",
                    "printButton"
                  ]
    builder = gtk.Builder()
    builder.add_from_file( os.path.join( sys.path[0], "notey.glade" ) )
    
    for elem in ui_elements:
      setattr(self, elem, builder.get_object(elem))
    
    if disable_print:
      self.printButton.set_property('visible', False)
    #
    # glade cannot handle Cells and CellRenders
    # create them here
    #
    self.titleCellRenderer = gtk.CellRendererText()
    self.titleCell = gtk.TreeViewColumn(
                                        "Title", 
                                        self.titleCellRenderer, 
                                        text=0
                                       )
    self.titleCell.set_sort_column_id(0)
    
    self.titleCellRenderer.connect(
                                  'edited', 
                                  self.on_titleCell_edited, 
                                  self.tocList
                                  )
    self.titleCellRenderer.connect(
                                  'editing-canceled',
                                   self.on_titleCell_editing_cancelled, 
                                   self.tocList
                                  )
    self.modifiedDateCellRenderer = gtk.CellRendererText()
    self.modifiedDateCell = gtk.TreeViewColumn(
                                        "Modified Date",
                                        self.modifiedDateCellRenderer, 
                                        text=1
                                       )
    
    self.tocListView.append_column(self.titleCell)
    self.tocListView.append_column(self.modifiedDateCell)
    self.tocListView.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

    self.tocList.set_sort_func(0, self.compare_data, 0)
    
    #make a status icon
    self.statusicon = gtk.status_icon_new_from_stock(gtk.STOCK_GOTO_TOP)
    self.statusicon.connect('activate', self.status_clicked )
    self.statusicon.set_tooltip("Notey is not hidden")
   
    builder.connect_signals(self)

   
    #
    # for some strange reasons destroy-event is not useful
    # unfortunately that is the event that glade on fedora14 knows about
    # connect the mainWindow destroy event to the handler
    #
    self.mainWindow.connect("destroy", self.on_mainWindow_destroy)

  def compare_data(self, model, iter1, iter2, column):
        data1 = model.get_value(iter1, column)
        data2 = model.get_value(iter2, column)
        return cmp(data1, data2)
    
  def tocList_populate(self,title=""):
    self.tocList.clear()
    if title == "":
      for note in self.notedb.get_index():
        date_now=dt.fromtimestamp(note.last_modified).strftime(DATEFMT)
        mod_date=dt.strptime(date_now,DATEFMT)
        ago = self.mod_date_ago(mod_date)
        self.tocList.append((note.title, ago))
    else:
      for note in self.notedb.get_index(title):
        date_now=dt.fromtimestamp(note.last_modified).strftime(DATEFMT)
        mod_date=dt.strptime(date_now,DATEFMT)
        ago = self.mod_date_ago(mod_date)
        self.tocList.append((note.title, ago))
   
  def tocListView_select_title(self, title):
    model = self.tocListView.get_model()
    i = 0
    for x in model:
      if x[0] == title:
        break
      else:
        i += 1
    if i <= len(model):
      self.tocListView.set_cursor((i,))
    else:
      pass


  def save_note(self):
    if not self.title == "":
      content = self.noteText.get_text(
                      self.noteText.get_start_iter(),
                      self.noteText.get_end_iter()
                    )
      try:
        old_content = self.notedb.get_note(self.title).content
      except NoteNotFoundException as e:
        old_content = ""
      if not content == old_content:
        self.notedb.update_note(self.title, content)
        self.tocList_populate()
        self.tocListView_select_title(self.title)
        snSyncer = SimpleNoteSyncer(self)
        snSyncer.start()
    
  def clear_state(self):
    self.titleEntry.set_text("")
    self.noteText.set_text("")
    self.title = ""
    self.mainWindow.set_title(DEFAULT_TITLE)
    self.tocListView_select_title(self.title)
    
  def open_note(self, title):
    try:
      note = self.notedb.get_note(title)
      self.noteText.set_text(note.content)
      self.noteTextView.grab_focus()
      self.title = note.title
      self.mainWindow.set_title(note.title + " : " + DEFAULT_TITLE)
      self.tocListView_select_title(self.title)      
      line_count = self.noteText.get_line_count()
      char_count = self.noteText.get_char_count()
      count = "Line count = %d , Char count = %d" % (line_count,char_count)
      self.keypressLabel.set_text(count)
    except NoteNotFoundException as e:
      self.new_note(title)
      self.tocList_populate()
      self.open_note(title)
  
  def new_note(self, title):
    self.notedb.create_note(title, "")
  
  def rename_note(self, old_title, new_title):
    self.notedb.rename_note(old_title, new_title)
    self.tocList_populate()
    if self.title == old_title:
      self.open_note(new_title)
  
  def delete_note(self, title):
    self.notedb.delete_note(title)
    snDeleter = SimpleNoteDeleter(self, title)
    snDeleter.start()
    self.tocList_populate()
    self.clear_state()

  def print_note(self,text):
    filename = "C:\NotesData.txt"
    #tempfile.mktemp (prefix="NotesData",suffix=".txt",dir=None)
    open (filename, "w").write (text)
    win32api.ShellExecute (  0,  "print",  filename,  None,  ".",  0)
  
  def mail_note(self,text):
    url = self.mailto_url("","Notey Notes",text,"")
    webbrowser.open(url,new=1)

  def get_note_line_count(self):
    line_count = self.noteText.get_line_count()
    return line_count
  
  def get_selected_note_contents(self):
    treeselection = self.tocListView.get_selection()
    model, rows = treeselection.get_selected_rows()
    titles = []
    text=""
    for j in rows:
      titles.append(model[j][0])
    for title in titles:
       text+= title + ":\n"
       text+= self.notedb.get_note(title).content
       text+="\n\n"
    return text
    
  
  def mailto_url(self,to=None,subject=None,body=None,cc=None):
    url = "mailto: " + urllib.quote(to.strip(),"@,")
    sep = "?"
    if cc:
      url+= sep + "cc=" + urllib.quote(cc,"@,")
      sep = "&"
    if subject:
      url+= sep + "subject=" + urllib.quote(subject,"")
      sep = "&"
    if body:
      body="\r\n".join(body.splitlines())
      url+= sep + "body=" + urllib.quote(body,"")
      sep = "&"
    return url

  def hide_window(self,window,event):
    self.mainWindow.hide()
    self.statusicon.set_tooltip("Notey is hidden, click to restore")
    return True
  
  def status_clicked(self,status):
    #unhide the window
    self.mainWindow.deiconify()
    self.mainWindow.show()
    self.mainWindow.present()
    self.statusicon.set_tooltip("Notey is not hidden")    

  def mod_date_ago(self,mod_date):
    date_now = dt.now().strftime(DATEFMT)
    curr_date=dt.strptime(date_now,DATEFMT)
    diff=curr_date-mod_date

    weeks, days = divmod(diff.days, 7)
    minutes, seconds = divmod(diff.seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if weeks > 0:
      ago="about %d week(s) ago" % weeks
    elif days > 0:
      ago="about %d day(s) ago" % days
    elif ( hours > 0 ):
      mod_time = mod_date.strftime("%I:%M %p")
      ago="Yesterday at %s" % mod_time
    elif ( minutes > 0 ):
      ago="about %d minute(s) ago" % minutes
    elif ( seconds > 0 ):
      ago="about %d second(s) ago" % seconds
    else:
      return ""
    return ago

                      
  def search(self, str): 
    found_text_tag = self.noteText.create_tag(background="grey")
    start = self.noteText.get_start_iter()
    end = self.noteText.get_end_iter()
    
    i = 0
    if str:      
      while 1:
        res = start.forward_search(str, gtk.TEXT_SEARCH_TEXT_ONLY)
        if not res:
         break
        match_start, match_end = res
        i += 1
        self.noteText.apply_tag(found_text_tag, match_start, match_end)
        start = match_end
    
  def markdown(self):
    self.save_note()
    content = self.get_selected_note_contents()
    htmlData=self.text2html(content)

    filename = "test.html"
    FILE = open(filename,"w")
    FILE.writelines(htmlData)
    FILE.close()

    webbrowser.open("test.html",new=1)

  def replace_specialEntities(self,content):
    output=content.replace("&","&amp;")
    output=output.replace("\"","&quot;")
    output=output.replace("<","&lt;")
    
    lines=len(output.splitlines())
    i=0
    final_output=""
    while i < lines:
      line_content=output.splitlines()[i]
      if output.splitlines()[i][0:1] != ">":
        line_content=line_content.replace(">","&gt;",999999999)
      final_output+=line_content
      final_output+="\n"
      i+=1
    return final_output
    
  def text2html(self,content):
    lines=len(content.splitlines())
    b_flag=0
    l_flag=0
    i=0
    content=self.replace_specialEntities(content)
    output="<html>\n<body>"
    while i < lines:
      none=0
      line_content=content.splitlines()[i]
      if line_content[0:2] == "**":
        line_content=line_content.replace("**","\n<b>",1)
        line_content+="</b>"
      elif line_content[0:3] == "###":
        line_content=line_content.replace("###","\n<h3>",1)
        line_content+="</h3>"
      elif line_content[0:2] == "##":
        line_content=line_content.replace("##","\n<h2>",1)
        line_content+="</h2>"
      elif line_content[0:1] == "#":
        line_content=line_content.replace("#","\n<h1>",1)
        line_content+="</h1>"
      elif line_content[0:1] == "-":
        l_flag+=1
        if l_flag ==1:
          line_content=line_content.replace("-","\n<ul>\n<li>",1)
          line_content+="</li>"
        else:
          line_content=line_content.replace("-","\n<li>",1)
          line_content+="</li>"
      elif l_flag>0 and line_content[0:1] != "-":
        l_flag=0
        line_content="\n</ul>"
        i-=1
      elif line_content[0:1] == ">":
        b_flag+=1
        if b_flag ==1:
          line_content=line_content.replace(">","\n<blockquote>\n",1)
        else:
          line_content=line_content.replace(">","\n",1)
        if content.splitlines()[i+1][0:1] != ">":
          b_flag=0
          line_content+="\n</blockquote>\n"
      else:
        none=1
      i+=1
      if none==1:
        output+="\n<p>"
        output+=line_content
        output+="</p>"
      else:
        output+=line_content
      
    output+="\n</body>\n</html>" 
    return output
    
  #
  # event handlers 
  #
  def on_mainWindow_delete_event(self, widget, data=None):
    self.save_note()
    #return gtk.FALSE
    return False
    
  def on_mainWindow_destroy(self, widget, data=None):
    gtk.main_quit()

  def on_mainWindow_key_release_event(self, widget,event=None):
    modifier_mask = event.state & gtk.accelerator_get_default_mod_mask()
    #Cntrl-E to focus title entry  
    if (event.keyval == 101 and modifier_mask == gtk.gdk.CONTROL_MASK):
      self.on_emailButton_clicked()
    #Cntrl-K to focus title entry  
    elif (event.keyval == 107 and modifier_mask == gtk.gdk.CONTROL_MASK):
      self.titleEntry.grab_focus()
    #Cntrl-L to focus list view
    elif (event.keyval == 108 and modifier_mask == gtk.gdk.CONTROL_MASK):
      self.tocListView.grab_focus()
    #Cntrl-P to print selected note      
    elif (event.keyval == 112 and modifier_mask == gtk.gdk.CONTROL_MASK):
      self.on_printButton_clicked()
    
     
  def on_titleEntry_activate(self, widget, data=None):
    title = widget.get_text()
    if title:
      self.open_note(title)
    else:
      widget.grab_focus()
            
  def on_noteTextView_focus_out_event(self, widget, data=None):
    self.save_note()
    self.tocList_populate()

 
  def on_tocListView_row_activated(self, widget, row, col):
    model = widget.get_model()
    title = model[row][0]
    self.open_note(title)
    text = self.titleEntry.get_text()
    self.search(text)
      
  def on_emailButton_clicked(self,data=None):
    contents = self.get_selected_note_contents()
    if contents != "":
      self.mail_note(contents)
    else:
      print "No note selected"

  def on_printButton_clicked(self,data=None):
    if not disable_print:
      contents = self.get_selected_note_contents()
      if contents != "":
        self.print_note(contents)
      else:
        print "No note selected"
        
  def on_preferencesButton_clicked(self, data=None):
    p = Preferences(self)

  def on_markdownButton_clicked(self, data=None):
   self.markdown()
      
  def on_tocListView_key_release_event(self, widget, data=None):
    treeselection = widget.get_selection()
    model, rows = treeselection.get_selected_rows()
    titles = []
    for j in rows:
      titles.append(model[j][0])
    if data.keyval == 65535:
      for title in titles:
        self.delete_note(title)
    if len(titles) == 1 and len(rows) == 1:
      title = titles[0]
      row   = rows[0]
      keyname = gtk.gdk.keyval_name(data.keyval)
      if data.keyval == 65471:
        self.titleCellRenderer.set_property('editable', True)        
        self.tocListView.set_cursor( row, 
                                     focus_column=self.titleCell, 
                                     start_editing=True 
                                   )
      else:
        pass
    else:
      pass

  def on_titleEntry_key_release_event(self, widget, data=None):
    title = widget.get_text()
    self.tocList_populate(title)
    gobject.idle_add(self.eventProgressBar.set_text, '')
    pass
  
  def on_titleEntry_focus_out_event(self,widget,data=None):
    gobject.idle_add(self.eventProgressBar.set_text, '')

  def on_titleEntry_focus_in_event(self,widget,data=None):
    self.noteText.set_text("")
    
  def on_titleCell_edited(self, renderer, path, new_title, model):
    self.titleCellRenderer.set_property('editable', False)
    old_title = model[path][0]
    self.rename_note(old_title, new_title) 
    
  def on_titleCell_editing_cancelled(self, renderer, data=None):
    self.titleCellRenderer.set_property('editable', False)
    print "Cancelled"

  def on_mainWindow_window_state_event(self,window,event):
    if event.changed_mask & gtk.gdk.WINDOW_STATE_ICONIFIED:
      if event.new_window_state & gtk.gdk.WINDOW_STATE_ICONIFIED:
        self.hide_window(window,event)

if __name__ == "__main__":
  app = Notey()
  gtk.main()
