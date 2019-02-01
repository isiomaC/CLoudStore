from google.appengine.ext import ndb
  
class MyUser(ndb.Model):
    email = ndb.StringProperty()

class File(ndb.Model):
    filename = ndb.StringProperty()
    dateTimeCreated = ndb.DateTimeProperty(auto_now_add=True)
    blob = ndb.BlobKeyProperty()  
        
    
class Directory(ndb.Model):
    dirName = ndb.StringProperty()
    parent_id = ndb.StringProperty()
    files = ndb.StructuredProperty(File, repeated=True)
    TimeCreated = ndb.DateTimeProperty(auto_now_add=True)
    
    def get_children(self):
        return Directory.query(Directory.parent_id == self.key.id()).fetch()
    
    def find(self, name):
        
        files = []
        
        path = self.get_abs_path()
        
        for i, f in enumerate(self.files):
            if name in f.filename.lower():
                files.append({'file':f.filename, 'path':path + f.filename, 'id':self.key.id(), 'index':i})
                
        for dir in self.get_children():
            files.extend(dir.find(name))
                
        return files
    
    def file_exists(self, filename):
        for f in self.files:
            if f.filename == filename:
                return True
            
        return False
    
    def get_abs_path(self):
        
        path = ''
        
        parent = self
        while parent.parent_id:
            path = parent.dirName + '/' + path
            parent = Directory.get_by_id(parent.parent_id, self.key.parent())
        
        path = '/' + path
        
        return path
    
class RecycleBin(ndb.Model):
    parent_id = ndb.StringProperty()
    file = ndb.StructuredProperty(File)
    dir = ndb.StructuredProperty(Directory)
    TimeDeleted = ndb.DateTimeProperty(auto_now_add=True)
    
    def get_parent(self):
        return Directory.get_by_id(self.parent_id, self.key.parent())
   
class Counter(ndb.Model):
    count = ndb.IntegerProperty()

def update_counter():
    counter = Counter.get_by_id('counter')
    if counter is None:
        counter = Counter(id='counter', count=0)

    counter.count += 1
    counter.put()

    return str(counter.count)

# def checkUser(user, handler):
#     if user == 'None':
#         handler.redirect('/')
        



