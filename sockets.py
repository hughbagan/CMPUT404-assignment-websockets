#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2021 Abram Hindle, Hugh Bagan
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
from flask import Flask, request, redirect, Response
from flask_sockets import Sockets
import gevent
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()
clients = []
updates = [] # contains tuples: (ws, {entities})
tasks = gevent.queue.Queue()

def set_listener( entity, data ):
    ''' do something with the update ! '''
    # Send here?
    pass

myWorld.add_set_listener( set_listener )


def read_ws(ws,client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME
    print("receiving")
    while True:
        message = ws.receive()
        if message:
            try:
                new_objs = json.loads(message)
                print(new_objs)
                for entity in new_objs:
                    if myWorld.get(entity) == {}:
                        # colour, radius might cause a problem
                        # We're going to ignore update and just use set instead
                        myWorld.set(entity, new_objs[entity])
                        updates.append( (ws, new_objs) )
            except Exception as e:
                print(message)
                print(e)
        gevent.sleep(0.1)


def write_ws(ws):
    """ Send updates to a websocket """    
    # Send here? Use gevent?
    while True:
        if (len(updates) > 0):
            i = 0
            while (i < len(updates)):
                if updates[i][0] != ws:
                    # These updates came from a different ws, so the current ws needs them!
                    print("Send updates")
                    ws.send(json.dumps(updates[i][1]))
                    del updates[i]
                    i -= 1
                i += 1
        gevent.sleep(0.1)


@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    # XXX: TODO IMPLEMENT ME
    ws.send("Flask says hello!")
    clients.append(ws)
    # Get the client up to speed with the current world state
    ws.send(json.dumps(myWorld.world()))
    #while not ws.closed:
    # Sorry; I don't know how to use gevent :(
    gevent.joinall([
        gevent.spawn(read_ws(ws, ws)),
        gevent.spawn(write_ws(ws))
    ])    


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])


@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    data = request.get_json(force=True)
    create_mode = myWorld.get(entity) == dict()
    if request.method=='POST':
        for key in data:
            try:
                myWorld.update(entity, key, data[key])
            except Exception as e:
                return Response(str(e), status=500)
    elif request.method=='PUT':
        try:
            myWorld.set(entity, data)
        except Exception as e:
            return Response(str(e), status=500)
        return json.dumps(myWorld.get(entity)) # "returns the obj that was PUT"
    else:
        print(request.method)
        return Response(status=405) # Method Not Allowed
    if create_mode:
        return Response(status=201) # Created
    else:
        return Response(status=204) # No Content


@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    return json.dumps(myWorld.world())


@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return json.dumps(myWorld.get(entity))


@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    return json.dumps(myWorld.world()) # should be empty {}


@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return redirect("/static/index.html")


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
