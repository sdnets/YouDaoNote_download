#!/usr/bin/python
# -*- coding: utf-8 -*- 


import os
import sys
import json
import requests
import time
import hashlib
from collections import namedtuple
reload(sys)
sys.setdefaultencoding( "utf-8" )

index = 0
DItem = namedtuple('DItem', 'id name path')
FSMItem = namedtuple('FSMItem', 'state event next_state function')
State = type('State', (), {'start': 0, 'initial': 1, 'authentic': 2, 'root': 3, 'dir': 4, 'file': 5, 'end': 6})
Event = type('Event', (), {'init': 0, 'login': 1, 'excep': 2, 'get_root': 3, 'pd_wrong': 4, 'get_dir': 5, 'get_file': 6, 'complete': 7, 'except_exceed': 8})

class FSM(object):
    
    def __init__(self):
        self.state = State.start
        self.fsm_funcs = {}
        self.fsm_events = {}
        
    def reg_func(self, state, function):
        self.fsm_funcs[state] = function
            
    def reg_event(self, state, event, next_state):
        if state not in self.fsm_events:
            self.fsm_events[state] = {}
        self.fsm_events[state][event] = next_state
        
    def run(self, first_event):
        self.event = first_event
        while self.state != State.end:
            func = self.fsm_funcs.get(self.state, None)
            if not func:
                print("There is no function for state {0}\n".format(self.state))
                return False
            self.event = func()
            all_next = self.fsm_events.get(self.state, {})
            next_state = all_next.get(self.event, None)
            if not next_state:
                print("There is no event {0} for state {1}\n".format(self.event, self.state))
                return False
            self.state = next_state

def timestamp():
    return str(int(time.time() * 1000))

class YDNoteSession(requests.Session):
    
    def __init__(self):
        requests.Session.__init__(self)
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/63.0.3239.84 Safari/537.36',
            'Accept': '*/*',
            'Accept-Encoding':'gzip, deflate, br',
            'Accept-Language':'zh-CN,zh;q=0.9,en;q=0.8'
        }

    def login(self, username, password):
        self.get('https://note.youdao.com/web/')
        self.headers['Referer'] = 'https://note.youdao.com/web/'
        self.get('https://note.youdao.com/signIn/index.html?&callback=https%3A%2F%2Fnote.youdao.com%2Fweb%2F&from=web')
        self.headers['Referer'] = 'https://note.youdao.com/signIn/index.html?&callback=https%3A%2F%2Fnote.youdao.com%2Fweb%2F&from=web'
        self.get('https://note.youdao.com/login/acc/pe/getsess?product=YNOTE&_=' + timestamp())
        self.get('https://note.youdao.com/auth/cq.json?app=web&_=' + timestamp())
        self.get('https://note.youdao.com/auth/urs/login.json?app=web&_=' + timestamp())
        data = {
            "username": username,
            "password": hashlib.md5(password).hexdigest()
        }
        self.post('https://note.youdao.com/login/acc/urs/verify/check?app=web&product=YNOTE&tp=urstoken&cf=6&fr=1&systemName=&deviceType=&ru=https%3A%2F%2Fnote.youdao.com%2FsignIn%2F%2FloginCallback.html&er=https%3A%2F%2Fnote.youdao.com%2FsignIn%2F%2FloginCallback.html&vcode=&systemName=&deviceType=&timestamp=' + timestamp(), data=data, allow_redirects=True)
        self.get('https://note.youdao.com/yws/mapi/user?method=get&multilevelEnable=true&_=' + timestamp())
        self.cstk = self.cookies.get('YNOTE_CSTK')
        return self.cstk!=None
    
    def get_root(self, path):
        data = {
            'path': '/',
            'entire': 'true',
            'purge': 'false',
            'cstk': self.cstk
        }
        response = self.post('https://note.youdao.com/yws/api/personal/file?method=getByPath&keyfrom=web&cstk=%s' % self.cstk, data = data)
        if response.status_code!=200:
            print response.content
            return False, None
        json_content = json.loads(response.content)
        return True, DItem(json_content['fileEntry']['id'], "Data", path)
        
    def get_dir(self, id, dir):
        dirs = []
        files = []
        data = {
            'path': '/',
            'dirOnly': 'false',
            'f': 'false',
            'cstk': self.cstk
        }
        url = 'https://note.youdao.com/yws/api/personal/file/%s?all=true&f=true&len=30&sort=1&isReverse=false&method=listPageByParentId&keyfrom=web&cstk=%s' % (id, self.cstk)
        response = self.get(url)
        if response.status_code!=200:
            return False, None, None
        json_content = json.loads(response.content)
        for entry in json_content['entries']:
            fileEntry = entry['fileEntry']
            id = fileEntry['id']
            name = fileEntry['name']
            if fileEntry['dir']:
                dirs.append(DItem(id, name, dir))
            else:
                files.append(DItem(id, name, dir))
        print("dir: {0}/{1}".format(dir, id))
        return True, dirs, files
                
    def get_file(self, id, dir, name, fail_dir):
        data = {
            'fileId': id,
            'version': -1,
            'convert': 'true',
            'editorType': 1,
            'cstk': self.cstk
        }
        url = 'https://note.youdao.com/ydoc/api/personal/doc?method=download-docx&keyfrom=web&cstk=%s&fileId=%s' % (self.cstk,id)
        response = self.get(url, data = data)
        if response.status_code!=200:
            return False
        try:
            if not os.path.exists(dir):
                os.makedirs(dir)
            with open('%s/%s.doc' % (dir, name), 'w') as fp:
                fp.write(response.content)
        except IOError,e:
            global index
            with open('{0}/{1}.doc'.format(fail_dir, index),'w') as fp:
                fp.write(response.content)
            with open("{0}/failure.log".format(fail_dir),"a") as log:
                log.write("{0} : {1}/{2}.doc\n".format(index, dir, name))
            ++index
        print("file: {0}/{1} size: {2}".format(dir, name,len(response.content)))
        return True
        
class DownloadManage(object):
    
    def __init__(self, username, password, store_dir):
        self.last_except_time = time.time()
        self.rootid = None
        self.dirs = []
        self.files = []
        self.username = username
        self.password = password
        self.store_dir = store_dir
        self.delay = 120
        self.fsm = FSM()
        self.except_num = 0
        self.except_max = 16
        self.fail_items={}
        self._init_fsm()
        
    def _init_fsm(self):
        self.fsm.reg_func(State.start, self.start)
        self.fsm.reg_func(State.initial, self.init)
        self.fsm.reg_func(State.authentic, self.login)
        self.fsm.reg_func(State.root, self.get_root)
        self.fsm.reg_func(State.dir, self.get_dir)
        self.fsm.reg_func(State.file, self.get_file)
        self.fsm.reg_event(State.start, Event.init, State.initial)
        self.fsm.reg_event(State.initial, Event.except_exceed, State.end)
        self.fsm.reg_event(State.initial, Event.login, State.authentic)
        self.fsm.reg_event(State.authentic, Event.get_root, State.root)
        self.fsm.reg_event(State.authentic, Event.excep, State.initial)
        self.fsm.reg_event(State.authentic, Event.pd_wrong, State.end)
        self.fsm.reg_event(State.root, Event.get_dir, State.dir)
        self.fsm.reg_event(State.root, Event.excep, State.initial)
        self.fsm.reg_event(State.dir, Event.get_dir, State.dir)
        self.fsm.reg_event(State.dir, Event.get_file, State.file)
        self.fsm.reg_event(State.dir, Event.excep, State.initial)
        self.fsm.reg_event(State.file, Event.complete, State.end)
        self.fsm.reg_event(State.file, Event.get_file, State.file)
        self.fsm.reg_event(State.file, Event.excep, State.initial)
      
    def _update_delay(self):
        now = time.time()
        if now - self.last_except_time > 120:
            self.delay = max(self.delay*0.5, 120)
        else:
            self.delay = min(self.delay*2, 1200)
        
    def start(self):
        return Event.init
        
    def init(self):
        if self.except_num > 0:
            self._update_delay()
            print("Error occur, sleep {0} s".format(self.delay))
            time.sleep(self.delay)
        if self.except_num > self.except_max:
            return Event.except_exceed
        self.yd_session = YDNoteSession()
        return Event.login
        
    def login(self):
        try:
            code = self.yd_session.login(self.username, self.password)
            if code:
                return Event.get_root
                with open("{0}/failure.log".format(self.store_dir), "a") as log:
                        log.write("password error\n")
                return Event.pd_wrong
        except Exception, e:
            pass
        self.except_num += 1
        return Event.excep
            
    def get_root(self):
        if self.rootid:
            return Event.get_dir
        try:
            code, result = self.yd_session.get_root(self.store_dir)
            if code:
                self.rootid = result.id
                self.dirs.append(result)
                return Event.get_dir
        except Exception, e:
            print e
        self.except_num += 1
        return Event.excep
            
    def get_dir(self):
        if not len(self.dirs):
            return Event.get_file
        item = self.dirs[-1]
        try:
            code, dirs, files = self.yd_session.get_dir(item.id, item.path + "/" + item.name)
            if code:
                self.dirs.pop()
                self.dirs.extend(dirs)
                self.files.extend(files)
                return Event.get_dir
        except Exception, e:
            print e
        self.fail_items[item.id] = 1 + self.fail_items.get(item.id, 0)
        if self.fail_items[item.id] >= 3:
            self.dirs.pop()
            with open("{0}/failure.log".format(self.store_dir), "a") as log:
                log.write("get dir {0}/{1} error\n".format(item.path, item.name))
        self.except_num += 1
        return Event.excep
        
    def get_file(self):
        if not len(self.files):
            return Event.complete
        item = self.files[-1]
        try:
            code = self.yd_session.get_file(item.id, item.path, item.name, self.store_dir)
            if code:
                self.files.pop()
                return Event.get_file
        except Exception, e:
            print e
        self.fail_items[item.id] = 1 + self.fail_items.get(item.id, 0)
        if self.fail_items[item.id] >= 3:
            self.files.pop()
            with open("{0}/failure.log".format(self.store_dir), "a") as log:
                log.write("get file {0}/{1} error\n".format(item.path, item.name))
        self.except_num += 1
        return Event.excep
    
    def run(self):
        self.fsm.run(Event.init)
    
if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('args: <username> <password> [save_dir]')
        sys.exit(1)
    username = sys.argv[1]
    password = sys.argv[2]
    if len(sys.argv) >= 4:
        save_dir = sys.argv[3]
    else:
        save_dir = '.'
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    dm = DownloadManage(username, password, save_dir)
    dm.run()
