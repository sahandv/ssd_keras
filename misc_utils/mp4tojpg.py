#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  5 23:04:24 2018

@author: sahandv
"""
import cv2
def mp4tojpg(video,output_dir)
	print(cv2.__version__)
	vidcap = cv2.VideoCapture(video)
	success,image = vidcap.read()
	count = 0
	success = True
	while success:
	  cv2.imwrite(output_dir+"/frame%d.jpg" % count, image)     # save frame as JPEG file
	  success,image = vidcap.read()
	  print('Read a new frame: ', success)
	  count += 1
	
