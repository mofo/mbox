#!/usr/bin/env python

from flask import Flask, render_template
from flask import jsonify

import sys
sys.path.insert(0, 'modules')

import ytlib

app = Flask(__name__)

ytlib.init()

#
#  Here are the "API" endpoints
#
@app.route('/')
def index():
	return render_template('index.html')

@app.route('/api/playlist/add/<num>', methods=['GET', 'OPTIONS', 'POST'])
def pl_add(num):
	songNumInt = int(num)
	ytlib.songlist_rm_add("add", songNumInt)
	songs = ytlib.g.active.songs
	header = {'pl_token' : ytlib.g.pl_token}
	results = {'header' : header, 'songs' : songs}
	return jsonify(results)

@app.route('/api/playlist/get', methods=['GET', 'OPTIONS', 'POST'])
def pl_get():
	songs = ytlib.g.active.songs
	header = {'pl_token' : ytlib.g.pl_token}
	results = {'header' : header, 'songs' : songs}
	return jsonify(results)

@app.route('/api/playctrl/<cmd>', methods=['GET', 'OPTIONS', 'POST'])
def pl_ctrl(cmd):
	ytlib.playCtrl(cmd)
	results = ytlib.g.active.songs
	return jsonify(results)

@app.route('/api/playstatus', methods=['GET', 'OPTIONS', 'POST'])
def pl_status():
	if len(ytlib.g.active.songs):
		title = ytlib.g.active.songs[0]['title']
	else:
		title = "No Songs Playing"

	response = {'isplaying' : ytlib.g.playing, 'nowPlaying' : title, 'percentElapsed' : ytlib.g.percentElapsed, 'pl_token' : ytlib.g.pl_token}

	return jsonify(response)

@app.route('/api/search/text/<searchtext>', methods=['GET', 'OPTIONS', 'POST'])
def searchtext(searchtext):
	ytlib.searchstring(searchtext)
	results = ytlib.g.model.songs
	return jsonify(results)

@app.route('/api/search/<nextprev>', methods=['GET', 'OPTIONS', 'POST'])
def searchnextprev(nextprev):
	
	print (nextprev)

	if nextprev == 'next':
		ytlib.nextprev("n")
	else:
		ytlib.nextprev("p")

	results = ytlib.g.model.songs
	return jsonify(results)

@app.route('/api/search/album/<searchtext>', methods=['GET', 'OPTIONS', 'POST'])
def searchalbum(searchtext):
	ytlib.searchstring(searchtext)
	results = ytlib.g.model.songs
	return jsonify(results)

@app.route('/api/search/volume/<direction>', methods=['GET', 'OPTIONS', 'POST'])
def volumecontro(searchtext):
    return jsonify(builds[corr].keys())

@app.route('/api/search/add/<id>', methods=['GET', 'OPTIONS', 'POST'])
def addsong(searchtext):
    return jsonify(builds[corr].keys())

@app.route('/api/search/skip', methods=['GET', 'OPTIONS', 'POST'])
def skipsong(searchtext):
    return jsonify(builds[corr].keys())

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/graph')
def graph():
	(the_script, the_div) = simpleGraph.domultiple()
	return render_template('graph.html', the_script=the_script, the_div=the_div)

#
#  Here are the "partials" endpoints
#

@app.route('/templates/playlist', methods=['GET', 'OPTIONS', 'POST'])
def playlist():
    return render_template('/partials/playlist.html')

@app.route('/templates/search', methods=['GET', 'OPTIONS', 'POST'])
def search():
    return render_template('/partials/search.html')


@app.route('/dashboard') #default page @ localhost:5000/
def dash():
	return render_template('/partials/dashboard2.html')

#
#  Catch all
#
@app.errorhandler(404)
def page_not_found(e):
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int("5000"), debug=True)
