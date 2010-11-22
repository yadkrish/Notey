from urllib import urlopen
from base64 import b64encode
from time import time
import json

loginURL = 'https://simple-note.appspot.com/api/login'
indexURL = 'https://simple-note.appspot.com/api2/index'
noteURL  = 'https://simple-note.appspot.com/api2/data'

class SimpleNote(object):
  def __init__(self, key='', deleted=0, modifydate=0, title='', content=''):
    self.key = key
    self.deleted = deleted
    self.modifydate = modifydate
    self.title = title
    self.content = content
  
  def as_json(self):
    return json.loads(json.dumps(self, cls=SimpleNoteEncoder))

def as_SimpleNote(dct):
  if (('key' in dct) and ('content' in dct)):
    ca = dct['content'].split('\n')
    title = ca[0]
    content = '\n'.join(ca[2:])
    return SimpleNote(dct['key'], 
                  dct['deleted'], 
                  dct['modifydate'],
                  title,
                  content)

class SimpleNoteEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, SimpleNote):
      return {  'key'       : obj.key,
                'deleted'   : obj.deleted,
                'modifydate': obj.modifydate,
                'content'   : obj.title + '\n\n' + obj.content
             }
    return json.JSONEncoder.default(self, obj)

class SimpleNoteDB(object):
  
  def __init__(self, email="", password="", credentials=""):
    if email == "":
      raise ValueError("email cannot be empty")  
    self.email = email
    self.credentials = ""
    
    if not password == "":
      self.credentials = b64encode('email=%s&password=%s' % (email, password))
    elif not credentials == "":
      self.credentials = credentials
    else:
      raise ValueError("Both password and credential cannot be empty")
    
  def login(self):
    login = urlopen(loginURL, self.credentials)
    self.token = (login.readline()).rstrip()
    self.login_time = time()
    login.close()

  def index(self):
    index = urlopen(indexURL + "?auth=%s&email=%s" % (self.token, self.email))
    noteJSON = json.load(index)
    self._noteJSON = noteJSON   # DO NOT USE: for debugging only
    index.close()
    self.notes = []
    for note in noteJSON['data']:
      data = urlopen( noteURL + "/%s?auth=%s&email=%s" % (note['key'], 
                                    self.token, self.email)).readlines()
      note = json.loads(data[0], object_hook=as_SimpleNote)
      self.notes.append(note)
    return self.notes
  
  def new_note(self, title, content):
    try:
      note = self.find_note(title)
      note.content = content
      return update_note(note)
    except KeyError:
      data = { 'content' : title + '\n\n' + content }
      newnote = urlopen(noteURL + "?auth=%s&email=%s" % (
                                  self.token, self.email), json.dumps(data)).readlines()
      self.index()
      return json.loads(newnote[0])['key']
  
  def find_note(self, title):
    for note in self.notes:
      if note.title == title and note.deleted == 0:
        return note
    raise KeyError("Could not find note with title %s" % (title))
    
  def update_note(self, note):
    data = note.as_json()
    key = data['key']
    updatednote = urlopen(noteURL + "/%s?auth=%s&email=%s" % (key,
                                        self.token, self.email), json.dumps(data)).readlines()
    self.index()
    return json.loads(updatednote[0])['key']
