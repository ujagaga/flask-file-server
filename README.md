# Ohana-flaskfileServer

A flask file server with an elegant frontend for browsing, uploading and streaming files, argument support...

This is a fork of "Wildog/flask-file-server", so thanks for the startup point.

The goal is to have a file server configurable enough for a corporate environment where other file sharing solutions do not work like 
windows file share and samba file sharing due to different OS used on various machines, windows active directory, proxy and port management,...

What we are trying to achieve is to have a standalone, easy to start solution. 
For now, the server is sharing user home folder on port 8888, so after you run it, 
open your web browser and type the computer IP address on port 8888 (eg. 192.168.0.10:8888).

You can specify root folder to list via command line parameter like:
python3 Ohana_fileServer.py <folder to list>

If no folder is specified, user home folder will be used.

Additionaly you can specify the password and bad password lock time in the python file.

