#!/bin/bash

rm /public_share/*
cp /public_share/Install/pravila_ponasanja.txt /public_share/1.pravila_ponasanja.txt
cd /home/rada/Applications/flask-file-server/

IPLIST=$(ifconfig|grep "inet ")

OUTPUT=""

while IFS=';' read -ra ADDR; do
      for i in "${ADDR[@]}"; do
          IFS=' ' read -ra ADDR <<< "$i"
		for i in "${ADDR[@]}"; do
			if [[ $i == *"."* ]]; then
				if [[ $i != *"255"* ]]; then
				  OUTPUT="$i;  $OUTPUT"
				fi			  
			fi		    
		done
      done
 done <<< "$IPLIST"

notify-send "IP address list:   $OUTPUT"

python3 fileserver.py
