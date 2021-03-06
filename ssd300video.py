#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Aug  5 23:20:53 2018

@author: https://github.com/sahandv
"""
import time
import cv2
import matplotlib.pyplot as plt
import io
import urllib, base64
from keras import backend as K
from keras.models import load_model
from keras.preprocessing import image
from keras.optimizers import Adam
from imageio import imread
from imageio import get_reader
from imageio import imwrite
from imageio import get_writer
import numpy as np
from matplotlib import pyplot as plt

from models.keras_ssd300 import ssd_300
from keras_loss_function.keras_ssd_loss import SSDLoss
from keras_layers.keras_layer_AnchorBoxes import AnchorBoxes
from keras_layers.keras_layer_DecodeDetections import DecodeDetections
from keras_layers.keras_layer_DecodeDetectionsFast import DecodeDetectionsFast
from keras_layers.keras_layer_L2Normalization import L2Normalization

from ssd_encoder_decoder.ssd_output_decoder import decode_detections, decode_detections_fast

from data_generator.object_detection_2d_data_generator import DataGenerator
from data_generator.object_detection_2d_photometric_ops import ConvertTo3Channels
from data_generator.object_detection_2d_geometric_ops import Resize
from data_generator.object_detection_2d_misc_utils import apply_inverse_transforms

def imageio2cvimg(image):
    shape = image.shape
    out = np.zeros(shape).astype('uint8')
    out[:,:,2] = image[:,:,0]
    out[:,:,1] = image[:,:,1]
    out[:,:,0] = image[:,:,2]
    return out

# =============================================================================
# Project Config
# =============================================================================
video_url = '/home/sahand/720-24-rendered.mp4'
output_video_path = 'output.avi'
model_compile = True
model_path = 'weights/VGG_VOC0712Plus_SSD_300x300_ft_iter_160000.h5'
weights_path = 'weights/VGG_VOC0712Plus_SSD_300x300_ft_iter_160000.h5'
#video_out_res = (1280,720)
video_out_fps = 24
img_height = 300
img_width = 300
font = cv2.FONT_HERSHEY_COMPLEX_SMALL
font_scale = 0.7
thickness = 1
baseline = 0 
# =============================================================================

K.clear_session() # Clear previous models from memory.

if model_compile == True:    
    model = ssd_300(image_size=(img_height, img_width, 3),
                    n_classes=8,
                    mode='inference',
                    l2_regularization=0.0005,
                    scales=[0.1, 0.2, 0.37, 0.54, 0.71, 0.88, 1.05], # The scales for MS COCO are [0.07, 0.15, 0.33, 0.51, 0.69, 0.87, 1.05]
                    aspect_ratios_per_layer=[[1.0, 2.0, 0.5],
                                             [1.0, 2.0, 0.5, 3.0, 1.0/3.0],
                                             [1.0, 2.0, 0.5, 3.0, 1.0/3.0],
                                             [1.0, 2.0, 0.5, 3.0, 1.0/3.0],
                                             [1.0, 2.0, 0.5],
                                             [1.0, 2.0, 0.5]],
                    two_boxes_for_ar1=True,
                    steps=[8, 16, 32, 64, 100, 300],
                    offsets=[0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
                    clip_boxes=False,
                    variances=[0.1, 0.1, 0.2, 0.2],
                    normalize_coords=True,
                    subtract_mean=[123, 117, 104],
                    swap_channels=[2, 1, 0],
                    confidence_thresh=0.5,
                    iou_threshold=0.45,
                    top_k=200,
                    nms_max_output_size=400)

    model.load_weights(weights_path, by_name=True)
    adam = Adam(lr=0.001, beta_1=0.9, beta_2=0.999, epsilon=1e-08, decay=0.0)
    ssd_loss = SSDLoss(neg_pos_ratio=3, alpha=1.0)
    model.compile(optimizer=adam, loss=ssd_loss.compute_loss)
else:
    # We need to create an SSDLoss object in order to pass that to the model loader.
    ssd_loss = SSDLoss(neg_pos_ratio=3, n_neg_min=0, alpha=1.0)
    K.clear_session() # Clear previous models from memory.
    model = load_model(model_path, custom_objects={'AnchorBoxes': AnchorBoxes,
                                                   'L2Normalization': L2Normalization,
                                                   'DecodeDetections': DecodeDetections,
                                                   'compute_loss': ssd_loss.compute_loss})

# =============================================================================
## OpenCV for video frames
#
#vidcap = cv2.VideoCapture(video_url)
#success,image_cv = vidcap.read()
#success = True
#counter = 0
#while success:
#    success,image_cv = vidcap.read()
#    print('Read a new frame: ', success)
#    counter += 1
#    if counter > 10:
#        break
# =============================================================================

# =============================================================================
# # ImageIO use webcam data
#
# import visvis as vv
# reader = imageio.get_reader('<video0>')
# t = vv.imshow(reader.get_next_data(), clim=(0, 255))
# for im in reader:
#     vv.processEvents()
#     t.SetData(im)
# =============================================================================

#orig_images = [] # Store the images here.
#input_images = [] # Store resized versions of the images here.
image_out = []
#videowriter = get_writer('prediction_ssd.mp4', fps=24)
#video = cv2.VideoWriter('out_video.avi',-1,24,(1280,720))
reader = get_reader(video_url)
video_out_res = reader.get_meta_data(index=1)['size']
fourcc = cv2.VideoWriter_fourcc(*'XVID')
out_vid = cv2.VideoWriter(output_video_path,fourcc, video_out_fps, video_out_res)
y_pred_thresh_backup = []
y_pred_thresh = []

for i, frame in enumerate(reader):
    orig_images = []
    orig_images.append(frame)
    img = cv2.resize(frame, (img_height, img_width)) 
    img = image.img_to_array(img) 
    input_images = []
    input_images.append(img)
    input_images = np.array(input_images)
    start_time = time.time()
    y_pred = model.predict(input_images)
    prediction_time = (time.time() - start_time)
    FPS = int(1/prediction_time)
    FPS = 'Pred '+str(FPS)+' FPS'
    confidence_threshold = 0.1
    y_pred_thresh = [y_pred[k][y_pred[k,:,1] > confidence_threshold] for k in range(y_pred.shape[0])]

# =============================================================================
#     if i % 2 == 0 and i>3:
#         y_pred_thresh = y_pred_thresh_backup.copy()
#     else:
#         y_pred_thresh = [y_pred[k][y_pred[k,:,1] > confidence_threshold] for k in range(y_pred.shape[0])]
#         y_pred_thresh_backup = y_pred_thresh.copy()
# =============================================================================
        
    np.set_printoptions(precision=2, suppress=True, linewidth=90)
#    print("Predicted boxes:\n")
#    print('   class   conf xmin   ymin   xmax   ymax')
#    print(y_pred_thresh[0])

    # Display the image and draw the predicted boxes onto it.
    
    # Set the colors for the bounding boxes
    colors = plt.cm.hsv(np.linspace(0, 1, 21)).tolist()
    classes = ['0','33', '34', '35', '36',
               '37', '38', '39', '81']

    
    cv2.rectangle(frame, (10, 10), (180, 35), (255, 255, 255), cv2.FILLED)
    cv2.putText(frame,FPS,(30, 30), font, font_scale,(00,00,00),thickness)
    
    for box in y_pred_thresh[0]:
        label = '{}: {:.2f}'.format(classes[int(box[0])], box[1])
        if classes[int(box[0])]=='':
            continue
        # Transform the predicted bounding boxes for the 300x300 image to the original image dimensions.
        xmin = box[2] * orig_images[0].shape[1] / img_width
        ymin = box[3] * orig_images[0].shape[0] / img_height
        xmax = box[4] * orig_images[0].shape[1] / img_width
        ymax = box[5] * orig_images[0].shape[0] / img_height
        color = colors[int(box[0])]

        cv2.rectangle(frame, (int(xmin), int(ymin)), (int(xmax), int(ymin-17)), (00, 150, 00), cv2.FILLED)
        cv2.rectangle(frame, (int(xmin), int(ymin)), (int(xmax), int(ymax)), (00, 180, 00), 2)
        cv2.putText(frame,label,(int(xmin),int(ymin-5)), font, font_scale,(255,255,255),thickness)
        
        
    imwrite('out.jpg',frame)
    #fig = plt.gcf()
    #videowriter.append_data(frame)
    out_img = imageio2cvimg(frame)
    out_vid.write(out_img)
    if i > 1000:
        break
#videowriter.close()     
#cv2.destroyAllWindows()
out_vid.release()
#cv2.destroyAllWindows()
    
