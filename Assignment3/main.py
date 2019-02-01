import webapp2
import os
import logging
import jinja2
from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from models import * 
from __builtin__ import int


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)
     
def render_template(handler, template, template_values):
    template = JINJA_ENVIRONMENT.get_template(template +'.html')
    handler.response.write(template.render(template_values))
    return template

    
class Delete(webapp2.RedirectHandler):
    def get (self, cwd, type, id):
        
        user = users.get_current_user()
        myuser = ndb.Key('MyUser', user.user_id()).get()
        workDir = Directory.get_by_id(cwd, myuser.key) 
        
        if user and workDir:
            if type == 'file':  
                index = int(id)
                recycle = RecycleBin(
                    parent=myuser.key,
                    parent_id = workDir.key.id(),
                    file = workDir.files[index]
                )
                del workDir.files[index]
                recycle.put()
                workDir.put()
            
            elif type == 'dir':
                
                dirInWorkDir = Directory.get_by_id(id, myuser.key)
                
                if dirInWorkDir and dirInWorkDir.parent_id == workDir.key.id():
                     
                    if Directory.query(Directory.parent_id == dirInWorkDir.key.id()).count() == 0 and len(dirInWorkDir.files) == 0 :
                        
                        RecycleBin(
                            parent_id=dirInWorkDir.parent_id,
                            parent=myuser.key,
                            dir=dirInWorkDir,
                            id=dirInWorkDir.key.id()
                        ).put()
                        
                        dirInWorkDir.key.delete()  
        self.redirect('/cwd/' + cwd)
        
                   
class UploadHandler( blobstore_handlers.BlobstoreUploadHandler): 
    def post(self, cwd):
        user = users.get_current_user()
        upload = []
        
        if not user:
            self.redirect('/')
        else:
            myuser = ndb.Key('MyUser', user.user_id()).get()
            root = Directory.query(ancestor=myuser.key).filter(Directory.parent_id==None).get()   
            workDir = Directory.get_by_id(cwd, myuser.key) if cwd != root.key.id() else root
            upload = self.get_uploads()[0]  
            blobinfo = blobstore.BlobInfo(upload.key())
            new_file = File(filename=blobinfo.filename, blob=upload.key())
            
            if not workDir.file_exists(new_file.filename):
                workDir.files.append(new_file)
                workDir.put()
                
            self.redirect('/cwd/'+cwd)


class DownloadHandler( blobstore_handlers.BlobstoreDownloadHandler):
    def post(self):
        
        user = users.get_current_user()
        
        if not user:
            self.redirect('/')
        else:
            myuser = ndb.Key('MyUser', user.user_id()).get()
            cwd = self.request.get('cwd')
            workDir = Directory.get_by_id(cwd, myuser.key) 
            index = int(self.request.get('index')) 
            self.send_blob(workDir.files[index].blob)


class MainPage(webapp2.RequestHandler):
    def initAll(self): 
        self.user = users.get_current_user()
        if self.user:
            
            self.myuser = ndb.Key('MyUser', self.user.user_id()).get()
            
            if not self.myuser:
                self.myuser = MyUser(id=self.user.user_id(), email=self.user.email())
                self.myuser.put()
                
            self.root = Directory.query(ancestor=self.myuser.key).filter(Directory.parent_id==None).get()
                
            if not self.root:
                self.root = Directory(dirName="/", id=update_counter(), parent=self.myuser.key)
                self.root.put()
                
        self.response.headers['Content-Type'] = 'text/html'

    def main_render(self, cwd, workDir, error='', values=None):
        
        dirInWorkDir = Directory.query(Directory.parent_id == workDir.key.id()).fetch(projection=[Directory.dirName])
        if workDir.parent_id == None:
            parentDir = workDir.parent_id
        else:
            parentDir = Directory.get_by_id(workDir.parent_id, self.myuser.key)
        
        template_values = {
            'dirInWorkDir':dirInWorkDir, 
            'upload_url':blobstore.create_upload_url('/upload/' + cwd), 
            'strlogout':'logout', 
            'logout_url':users.create_logout_url(self.request.uri), 
            'user':self.user, 
            'workDir':workDir, 
            'myuser':self.myuser, 
            'root':self.root, 
            'parentDir':parentDir, 
            'cwd':cwd,
            'path':workDir.get_abs_path(),
            'error':error
        }
            
        if values:
            template_values.update(values)
        render_template(self, 'main', template_values)

    def get(self, cwd=''):
        self.initAll()
        
#         self.response.write(self.user.message)
        if not self.user:
            render_template(self, 'mainpage_guest', {
                'login_url' : users.create_login_url(self.request.uri),
                'user': None
            })
            return
        else:
            if not cwd:
                self.redirect('/cwd/' + self.root.key.id())
            else:
                workDir = Directory.get_by_id(cwd, parent=self.myuser.key) if cwd != self.root.key.id() else self.root
                if workDir and workDir.key.parent() == self.root.key.parent():
                    self.main_render(cwd, workDir)
                else:
                    self.redirect('/')
        
    def post(self, cwd):
        self.initAll()
        error = ''
        
        if self.user:
            workDir = Directory.get_by_id(cwd, self.myuser.key) if cwd != self.root.key.id() else self.root
            if self.request.get('button') == 'Add':
                directoryName = self.request.get('dirName').strip()
                directoryName = directoryName if directoryName else '' 
            
                if not directoryName:
                    error = 'Please Input A valid Name'
                elif Directory.query(Directory.parent_id == workDir.key.id()).filter(Directory.dirName == directoryName).count() > 0:
                    error = 'Directory name already exists'
                else:
                    Directory(
                        parent_id=workDir.key.id(),
                        dirName=directoryName,
                        id=update_counter(),
                        parent=self.myuser.key
                    ).put()
                    self.redirect('/cwd/'+ cwd)
                    
                if error:
                    self.main_render(cwd, workDir, error)
                    
            elif self.request.get('button') == 'Search':
                queryName = self.request.get('nametext').strip()
                
                if queryName:
                    
                    logging.info(queryName.lower())  
                    
                    files = workDir.find(queryName.lower())              
                    if len(files) == 0:
                        error = 'No files found'
                    
                    self.main_render(cwd, workDir, error, {'search':files})       
                else:
                    self.redirect('/cwd/'+ cwd)
            
            elif self.request.get('button') == 'Change Name':
    
                newDirName = self.request.get('newDirName').strip()
                id = self.request.get('dir_id')
                
                newFileName = self.request.get('newFileName').strip()
                index = self.request.get('index').strip()
                
                if newDirName and id:
                    if Directory.query(Directory.parent_id == workDir.key.id()).filter(Directory.dirName == newDirName).count() > 0:
                        self.main_render(cwd, workDir, 'A folder with the same name already exists in this folder')
                    else:
                        dir = Directory.get_by_id(id, self.myuser.key)
                        dir.dirName = newDirName
                        dir.put()
                        self.redirect('/cwd/'+cwd)
                        
                elif newFileName and index:     
                    if not workDir.file_exists(newFileName):
                        workDir.files[int(index)].filename = newFileName
                        workDir.put()
                        self.redirect('/cwd/'+ workDir.key.id())
                    else:
                        self.main_render(cwd, workDir, 'A file with the same name already exists in thisfolder')                      
                else:                
                    self.redirect('/cwd/'+cwd)                                
        else:                
            self.redirect('/cwd/'+cwd)


class Recycle(MainPage):
    def get(self, action='', type='', id=''):
        self.initAll()
        
        if type == 'file':
            id = long(id)
        
        error='' 
        
        if action == 'delete':
            recycle = RecycleBin.get_by_id(id, self.myuser.key)
            if recycle:
                recycle.key.delete()  
                logging.info(recycle)
                
        elif action == 'restore':   
            recycle = RecycleBin.get_by_id(id, self.myuser.key)
            if recycle: 
                if recycle.dir:    
                    if Directory.query(Directory.parent_id == recycle.parent_id).filter(Directory.dirName == recycle.dir.dirName).count() > 0:
                        error = 'A folder with the same name already exists in the parent folder'
                    else:
                        Directory(
                            id=recycle.key.id(),
                            parent=self.myuser.key,
                            dirName=recycle.dir.dirName,
                            TimeCreated=recycle.dir.TimeCreated,
                            parent_id=recycle.parent_id
                        ).put()
                        
                        recycle.key.delete()
                 
                elif recycle.file:
                    parent = Directory.get_by_id(recycle.parent_id, self.myuser.key)
                    if parent: 
                        if not parent.file_exists(recycle.file.filename):
                            parent.files.append(recycle.file)
                            parent.put()
                            recycle.key.delete()
                        else:
                            error = 'A file with the same name already exists in the parent folder'
                            
        bin = []
        for r in RecycleBin.query(ancestor=self.myuser.key).fetch():
            bin.append({'path':r.get_parent().get_abs_path(), 'file':r})
                   
        template_values = {
            'strlogout': 'logout',
            'logout_url' : users.create_logout_url(self.request.uri),
            'user': self.user,
            'bin': bin,
            'back': self.request.referer,
            'error': error
        }  
        render_template(self, 'recycle_bin', template_values)
                
app = webapp2.WSGIApplication([
       ('/', MainPage),
       (r'/cwd/(.*)', MainPage),
       (r'/upload/(.*)', UploadHandler),
       ('/download', DownloadHandler),
       (r'/cwddelete/(.*)/(.*)/(.*)', Delete),
       ('/recyclebin', Recycle),
       (r'/recyclebin/(.*)/(.*)/(.*)', Recycle)
])      
        