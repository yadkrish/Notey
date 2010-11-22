#!/usr/bin/env python
import sys
import os
import sqlite3
from datetime import datetime

DATEFMT = "%Y-%m-%d %H:%M"

class NoteNotFoundException(Exception):
  def __init__(self, message):
    self.message = message
  
  def __repr__(self):
    return repr(self.message)

class Note(object):
  def __init__(self, title, content, last_modified):
    self.title = title
    self.content = content
    self.last_modfied = last_modified

class NoteMeta(object):
  def __init__(self, title, last_modified):
    self.title = title
    self.last_modified = last_modified
    
class NoteDBsqlite3(object):
  def __init__(self, path):
    self.db = path
    if not os.path.isfile(self.db):
      self.init_db()
  
  def init_db(self):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    c.execute("create table notes ( title text UNIQUE, mod_date text, content text )")
    conn.commit()
    c.close()
  
  def get_index(self, search_text=""):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    if search_text == "":
      c.execute("select title,mod_date from notes order by title")
      rows = c.fetchall()
    else:
      c.execute("select title,mod_date from notes where title like ? or content like ? order by title", 
                    ( "%" + search_text + "%","%" + search_text + "%", )
                
               )
      rows = c.fetchall()
    c.close()
    return [ NoteMeta(x[0], x[1]) for x in rows ]

  def get_note(self, title):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    c.execute("select title, content, mod_date from notes where title = ?", (title,))
    rows = c.fetchall()
    if rows != [] :
      note = Note(rows[0][0], rows[0][1], rows[0][2])
      c.close()
      return note
    else:
      c.close()
      raise NoteNotFoundException("Could not find note with title %s" % (title))
  
  def rename_note(self, title, new_title):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    mod_date = datetime.now().strftime(DATEFMT)
    c.execute(
              "update notes set title = ?, mod_date = ? where title = ?", 
                (new_title, mod_date, title)
             )
    conn.commit()
    c.close()    

  def create_note(self, title, content):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    mod_date = datetime.now().strftime(DATEFMT)
    c.execute(
              "insert into notes values (?, ?, ?)",
               (title,mod_date,content)
             )
    conn.commit()
    c.close()  
  
  def update_note(self, title, content):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    mod_date = datetime.now().strftime(DATEFMT)
    c.execute(
              "update notes set content = ?,mod_date = ? where title = ?",
                (content, mod_date, title)
             )
    conn.commit()
    c.close()

  def delete_note(self, title):
    conn = sqlite3.connect(self.db)
    c = conn.cursor()
    c.execute("delete from notes where title = ?", (title,))
    conn.commit()
    c.close()

