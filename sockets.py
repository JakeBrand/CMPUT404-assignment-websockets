#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Copyright (c) 2015 Jake Brand
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True


class World:
    def __init__(self):
        self.clear()
        self.listeners = list()

    def add_set_listener(self, listener):
        self.listeners.append(listener)

    def update(self, entity, key, value):
        entry = self.space.get(entity, dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners(entity)

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners(entity)

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity, dict())

    def world(self):
        return self.space

myWorld = World()

# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
clients = list()


# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, value):
        self.queue.put_nowait(value)

    def get(self):
        return self.queue.get()


# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
def sendall(msg):
    for client in clients:
        client.put(msg)


# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
def sendall_json(jsonObj):
    sendall(json.dumps(jsonObj))


# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
def set_listener(entity, data):
    sendall_json({ entity : data });

myWorld.add_set_listener(set_listener)


# from last assignment
@app.route('/')
def hello():
    ''' Redirect to /static/index.html '''
    return redirect("/static/index.html")


# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
# altered to also update the world
def read_ws(ws, client):
    '''A greenlet function that reads from the websocket and updates world'''
    try:
        while True:
            msg = ws.receive()
            if(msg is not None):
                msg = json.loads(msg)
                for key in msg:
                    value = msg[key]
                    myWorld.set(key, value)
            else:
                break
    except Exception as e:
        print("exception in readws " + e.message)
    return None


# from github.com/abramhindle/WebSocketsExamples/blob/master/broadcaster.py
@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    client = Client()
    clients.append(client)
    g = gevent.spawn(read_ws, ws, client)
    try:
        while True:
            # block here
            msg = client.get()
            ws.send(msg)
    except Exception as e:
        print("WE Error %s" % e)
    finally:
        clients.remove(client)
        gevent.kill(g)

def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])


# from last assignment
@app.route("/entity/<entity>", methods=['POST', 'PUT'])
def update(entity):
    '''update the entities via this interface'''
    req = flask_post_json()
    if(myWorld.get(entity) == {}):
        myWorld.set(entity, req)
    else:
        for key in req:
            myWorld.update(entity, key, req[key])
    return json.dumps(myWorld.get(entity))


# from last assignment
@app.route("/world", methods=['POST', 'GET'])
def world():
    '''you should probably return the world here'''
    if (request.method == "GET"):
        return json.dumps(myWorld.world())
    else:  # POST assuming this should replace the current world
        req = flask_post_json()
        myWorld.clear()
        for entity in req:
            myWorld.set(entity, req[entity])
    return json.dumps(myWorld.world())


# from last assignment
@app.route("/entity/<entity>")
def get_entity(entity):
    '''This is the GET version of the entity interface,
       return a representation of the entity'''
    return json.dumps(myWorld.get(entity))


# from last assignment
@app.route("/clear", methods=['POST', 'GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    return json.dumps(myWorld.world())


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
