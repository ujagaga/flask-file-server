#!/usr/bin/env python3

from flask import Flask, make_response, request, render_template, send_file, Response, redirect, send_from_directory
from flask.views import MethodView
from werkzeug import secure_filename
from datetime import datetime, timedelta
import humanize
import re
import stat
import json
import mimetypes
import sys
import shutil
import random
import string
import os
import time


# Configuration
USER_PASSWORD = 'mypassword123'       # access password
LOCK_MINUTES = 5                # minutes to lock for when wrong password is entered 3 times

ROOT = os.path.expanduser('~') # folder to list unless one is provided as a parameter

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
SHAREABLE_URL_LEN = 13
SHARED_FILES = os.path.join(SCRIPT_PATH, "shared.db")
SHARE_LINK_TTL = 60*60*24

app = Flask(__name__, static_url_path='/assets', static_folder='assets')
ignored = ['.bzr', '$RECYCLE.BIN', '.DAV', '.DS_Store', '.git', '.hg', '.htaccess', '.htpasswd', '.Spotlight-V100', '.svn', '__MACOSX', 'ehthumbs.db', 'robots.txt', 'Thumbs.db', 'thumbs.tps']
datatypes = {'audio': 'm4a,mp3,oga,ogg,webma,wav', 'archive': '7z,zip,rar,gz,tar', 'image': 'gif,ico,jpe,jpeg,jpg,png,svg,webp', 'pdf': 'pdf', 'quicktime': '3g2,3gp,3gp2,3gpp,mov,qt', 'source': 'atom,bat,bash,c,cmd,coffee,css,hml,js,json,java,less,markdown,md,php,pl,py,rb,rss,sass,scpt,swift,scss,sh,xml,yml,plist', 'text': 'txt', 'video': 'mp4,m4v,ogv,webm', 'website': 'htm,html,mhtm,mhtml,xhtm,xhtml'}
icontypes = {'fa-music': 'm4a,mp3,oga,ogg,webma,wav', 'fa-archive': '7z,zip,rar,gz,tar', 'fa-picture-o': 'gif,ico,jpe,jpeg,jpg,png,svg,webp', 'fa-file-text': 'pdf', 'fa-film': '3g2,3gp,3gp2,3gpp,mov,qt', 'fa-code': 'atom,plist,bat,bash,c,cmd,coffee,css,hml,js,json,java,less,markdown,md,php,pl,py,rb,rss,sass,scpt,swift,scss,sh,xml,yml', 'fa-file-text-o': 'txt', 'fa-film': 'mp4,m4v,ogv,webm', 'fa-globe': 'htm,html,mhtm,mhtml,xhtm,xhtml'}

failed_logins = 0
login_list = {}


@app.template_filter('size_fmt')
def size_fmt(size):
    return humanize.naturalsize(size)


@app.template_filter('time_fmt')
def time_desc(timestamp):
    mdate = datetime.fromtimestamp(timestamp)
    str = mdate.strftime('%Y-%m-%d %H:%M:%S')
    return str


@app.template_filter('data_fmt')
def data_fmt(filename):
    t = 'unknown'
    for type, exts in datatypes.items():
        if filename.split('.')[-1] in exts:
            t = type
    return t


@app.template_filter('icon_fmt')
def icon_fmt(filename):
    i = 'fa-file-o'
    for icon, exts in icontypes.items():
        if filename.split('.')[-1] in exts:
            i = icon
    return i


@app.template_filter('humanize')
def time_humanize(timestamp):
    mdate = datetime.utcfromtimestamp(timestamp)
    return humanize.naturaltime(mdate)


def get_type(mode):
    if stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
        type = 'dir'
    else:
        type = 'file'
    return type


def partial_response(path, start, end=None):
    file_size = os.path.getsize(path)

    if end is None:
        end = file_size - start - 1
    end = min(end, file_size - 1)
    length = end - start + 1

    with open(path, 'rb') as fd:
        fd.seek(start)
        bytes = fd.read(length)
    assert len(bytes) == length

    response = Response(
        bytes,
        206,
        mimetype=mimetypes.guess_type(path)[0],
        direct_passthrough=True,
    )
    response.headers.add(
        'Content-Range', 'bytes {0}-{1}/{2}'.format(
            start, end, file_size,
        ),
    )
    response.headers.add(
        'Accept-Ranges', 'bytes'
    )
    return response


def get_range(request):
    range = request.headers.get('Range')
    m = re.match('bytes=(?P<start>\d+)-(?P<end>\d+)?', range)
    if m:
        start = m.group('start')
        end = m.group('end')
        start = int(start)
        if end is not None:
            end = int(end)
        return start, end
    else:
        return 0, None


def get_shareable_link(file_path):
    quicklink = None

    if os.path.isfile(os.path.join(ROOT, file_path)):

        file_urls = {}

        if os.path.isfile(SHARED_FILES):
            f = open(SHARED_FILES, "r")
            lines = f.readlines()
            f.close()

            for line in lines:
                data = line.split('=')
                if len(data) == 3:
                    path = data[0].strip()
                    if os.path.exists(os.path.join(ROOT, path)):
                        file_urls[path] = {'qurl': data[1], 'timestamp': data[2].strip()}

        letters = string.ascii_lowercase
        quicklink = ''.join(random.choice(letters) for i in range(SHAREABLE_URL_LEN))
        timestamp = f"{time.time():.0f}"

        file_urls[file_path] = {'qurl': quicklink, 'timestamp': timestamp}

        f = open(SHARED_FILES, "w")
        for relative_path in file_urls.keys():
            data = file_urls[relative_path]
            print("DATA: ".format(data))
            if (time.time() - int(data['timestamp'])) < SHARE_LINK_TTL:
                f.write("{0}={1}={2}\n".format(relative_path, data['qurl'], data['timestamp']))
        f.close()

    return quicklink


def get_file_from_shareable_link(quicklink):

    if (len(quicklink) == SHAREABLE_URL_LEN) and os.path.isfile(SHARED_FILES):
        f = open(SHARED_FILES, "r")
        lines = f.readlines()
        f.close()

        for line in lines:
            data = line.split('=')
            if len(data) == 2:
                file_path = data[0].strip()
                if (quicklink == data[1].strip()) and os.path.isfile(os.path.join(ROOT, file_path)):
                    return file_path
    return None


def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))


class PathView(MethodView):
    global login_list

    def get(self, p=''):
        client_ip = request.remote_addr

        quicklink_result = get_file_from_shareable_link(p)

        if quicklink_result is not None:
            absolute_path = os.path.join(ROOT, quicklink_result)
            file_path, file_name = os.path.split(absolute_path)

            return send_from_directory(file_path, file_name, as_attachment=True)
        else:
            client_data = login_list.get(client_ip,
                                         {'tstamp': (datetime.now() - timedelta(minutes=(LOCK_MINUTES + 1))), 'failed': 0,
                                          'loginok': False})
            if not client_data['loginok']:
                return redirect("/login")

        hide_dotfile = request.args.get('hide-dotfile', request.cookies.get('hide-dotfile', 'yes'))

        if p == "favicon.ico":
            path = os.path.join(SCRIPT_PATH, p)
        else:
            path = os.path.join(ROOT, p)

        # Check if an action is requested
        action = request.args.get('action', '')
        if action != '':
            item_name = request.args.get('name', '')
            item_parent = request.args.get('path', '')

            item_path = os.path.join(ROOT, item_parent)
            relative_path = os.path.join(item_parent, item_name)
            absolute_path = os.path.join(item_path, item_name)
            share = ""
            error_msg = ""
            status = 0

            if len(item_name) > 1:
                if action == "new":
                    if not os.path.isdir(item_path):
                        status = 1
                        error_msg = "Path not found: {}".format(item_path)
                    elif os.path.isdir(absolute_path):
                        status = 1
                        error_msg = "Target already exists: {}".format(absolute_path)
                    else:
                        os.mkdir(absolute_path)

                elif action == "del":
                    if not os.path.exists(absolute_path):
                        status = 1
                        error_msg = "Path not found: {}".format(absolute_path)
                    else:
                        try:
                            if os.path.isdir(absolute_path):
                                print("Removing: ", absolute_path)
                                shutil.rmtree(absolute_path)
                            else:
                                os.remove(absolute_path)
                        except Exception as e:
                            status = 1
                            error_msg = "{}".format(e)

                elif action == "share":
                    if not os.path.exists(absolute_path):
                        status = 1
                        error_msg = "Path not found: {}".format(absolute_path)
                    else:
                        share = get_shareable_link(relative_path)

                elif action == "archive":
                    if not os.path.isdir(absolute_path):
                        status = 1
                        error_msg = "Path is not a folder: {}".format(absolute_path)
                    else:
                        shutil.make_archive(absolute_path + '_archived', 'zip', absolute_path)
            else:
                status = 1
                error_msg = "Path not complete. Parent is: {0}, Item is: {1}".format(item_parent, item_name)

            res = make_response(json.JSONEncoder().encode({'status': status, 'error': error_msg, 'share': share}), 200)
            return res

        # Serve the requested item
        if os.path.isdir(path):
            contents = []
            total = {'size': 0, 'dir': 0, 'file': 0}
            for filename in os.listdir(path):
                if filename in ignored:
                    continue
                if hide_dotfile == 'yes' and filename[0] == '.':
                    continue

                try:
                    filepath = os.path.join(path, filename)
                    stat_res = os.stat(filepath)
                    info = {}
                    info['name'] = filename
                    info['mtime'] = stat_res.st_mtime
                    ft = get_type(stat_res.st_mode)
                    info['type'] = ft
                    total[ft] += 1
                    sz = stat_res.st_size
                    info['size'] = sz
                    total['size'] += sz
                    contents.append(info)
                except:
                    continue

            page = render_template('index.html', path=p, contents=contents, total=total, hide_dotfile=hide_dotfile)
            res = make_response(page, 200)
            res.set_cookie('hide-dotfile', hide_dotfile, max_age=16070400)
        elif os.path.isfile(path):
            if 'Range' in request.headers:
                start, end = get_range(request)
                res = partial_response(path, start, end)
            else:
                res = send_file(path)
                res.headers.add('Content-Disposition', 'attachment')
        else:
            res = make_response('Not found', 404)
        return res

    def post(self, p=''):
        client_ip = request.remote_addr
        client_data = login_list.get(client_ip,
                                     {'tstamp': (datetime.now() - timedelta(minutes=(LOCK_MINUTES + 1))), 'failed': 0,
                                      'loginok': False})
        if not client_data['loginok']:
            return "ERROR: Please login first"

        path = os.path.join(ROOT, p)
        info = {}
        if os.path.isdir(path):
            files = request.files.getlist('files[]')
            for file in files:
                try:
                    filename = secure_filename(file.filename)
                    file.save(os.path.join(path, filename))
                except Exception as e:
                    info['status'] = 'error'
                    info['msg'] = str(e)
                else:
                    info['status'] = 'success'
                    info['msg'] = 'File Saved'
        else:
            info['status'] = 'error'
            info['msg'] = 'Invalid Operation'
        res = make_response(json.JSONEncoder().encode(info), 200)
        res.headers.add('Content-type', 'application/json')
        return res


@app.route('/login', methods=['GET', 'POST'])
def login():
    global USER_PASSWORD
    global LOCK_MINUTES
    global login_list

    if request.method == 'POST':
        password = request.form.get("password")
        client_ip = request.remote_addr

        client_data = login_list.get(client_ip, {'tstamp': (datetime.now()-timedelta(minutes=(LOCK_MINUTES + 1))), 'failed': 0, 'loginok': False})

        target_url = "login"
        message = ""

        if (datetime.now() - client_data["tstamp"]).seconds > (LOCK_MINUTES * 60):
            client_data['failed'] = 0

        if password == USER_PASSWORD and client_data['failed'] < 3:
            client_data['loginok'] = True
            client_data['failed'] = 0
            login_list[client_ip] = client_data
            return redirect("/")
        else:
            client_data['loginok'] = False
            client_data['failed'] += 1
            client_data['tstamp'] = datetime.now()
            login_list[client_ip] = client_data

            if client_data['failed'] == 1:
                message = 'ERROR: Wrong password!'
            elif client_data['failed'] == 2:
                message = 'ERROR: Wrong password second time. One more and we will lock up the server.'
            elif client_data['failed'] > 2:
                message = 'ERROR: Wrong password too many times. The server is temporarely locked. Please try again later.'

            return render_template('login.html', message=message)

    else:
        return render_template('login.html')


@app.route('/logout', methods=['GET'])
def logout():
    global login_list

    client_ip = request.remote_addr
    client_data = login_list.get(client_ip,
                                 {'tstamp': (datetime.now() - timedelta(minutes=(LOCK_MINUTES + 1))), 'failed': 0,
                                  'loginok': False})
    client_data['loginok'] = False
    login_list[client_ip] = client_data

    return render_template('login.html')


@app.route('/admin', methods=['GET'])
def admin():
    cmd = request.args.get('cmd', '')
    password = request.args.get('password', '')
    client_ip = request.remote_addr

    client_data = login_list.get(client_ip,
                                 {'tstamp': (datetime.now() - timedelta(minutes=(LOCK_MINUTES + 1))), 'failed': 0,
                                  'loginok': False})

    if password == USER_PASSWORD and client_data['failed'] < 3:
        if cmd == "shutdown":
            func = request.environ.get('werkzeug.server.shutdown')
            func()
            message = 'Server shutting down!'
        else:
            message = 'Error: command not implemented!'
    else:
        client_data['loginok'] = False
        client_data['failed'] += 1
        client_data['tstamp'] = datetime.now()
        login_list[client_ip] = client_data

        if client_data['failed'] == 2:
            message = 'ERROR: Wrong password second time. One more and we will lock up the server.'
        elif client_data['failed'] > 2:
            message = 'ERROR: Wrong password too many times. The server is temporarely locked. Please try again later.'
        else:
            message = 'ERROR: Wrong password!'

    return make_response(json.JSONEncoder().encode({'msg': message}), 200)


if len(sys.argv) > 1:
    start_folder = sys.argv[1]

    if os.path.isdir(start_folder):
        ROOT = start_folder

path_view = PathView.as_view('path_view')
app.add_url_rule('/', view_func=path_view)
app.add_url_rule('/<path:p>', view_func=path_view)

try:
    app.run('0.0.0.0', 8888, threaded=True, debug=False)
except Exception as e:
    print("ERROR: Port not available.")
