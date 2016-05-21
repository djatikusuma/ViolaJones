#!/usr/bin/python3
# Copyright (C) 2016 Van Thien Nhat <nhat.vtvn@gmail.com>
#                    Florent Revest <revestflo@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os, sys, math
from lxml import etree   # lxml explores the OpenCV's haarcascade .xml file
from PIL import Image    # PIL.Image loads converts and shows the img to analyze
from PIL import ImageOps # PIL.ImageOps provides several handy filters
from PIL import ImageDraw #PIL.ImageDraw draw the figure to cover face

##### Image and Integral Image #####
# PIL provides a "I" channel which let us store large values of brightness.
# This is useful to store the integral image which makes computing faster.
# ImageOps.autocontrast ensures we use the full histogram's scale.
# pix is an array of pixels that is faster to use when reading pixels.
# pix2 contains the squared values of the pixels for variance calculation.

if len(sys.argv) != 2:
    print("Usage :", sys.argv[0], "FileName")
    sys.exit(1)
im = Image.open(sys.argv[1])
imageWidth, imageHeight = im.size
pixels = im.load()
pix  = [[int((30*pixels[y,x][0]+59*pixels[y,x][1]+11*pixels[y,x][2])/100) \
        for x in range(imageWidth)] for y in range(imageHeight)]
pix2 = [[int((30*pixels[y,x][0]+59*pixels[y,x][1]+11*pixels[y,x][2])/100) \
        for x in range(imageWidth)] for y in range(imageHeight)]

# Sobel or Canny Edge filters amplify edges and can provide better results :
# im.filter(ImageFilter.FIND_EDGES)

pix2[0][0] = pow(pix2[0][0],2)
for x in range(imageWidth) :
    for y in range(imageHeight) :
        if x == 0 and y != 0 :
            pix[x][y] += pix[x][y-1] 
            pix2[x][y] = pix2[x][y-1] + pow(pix2[x][y],2)
        elif y == 0  and x != 0:
            pix[x][y] += pix[x-1][y]
            pix2[x][y] = pix2[x-1][y] + pow(pix2[x][y],2)
        elif x != 0 and y != 0 :
            pix[x][y] += pix[x-1][y] + pix[x][y-1] - pix[x-1][y-1]
            pix2[x][y]=pix2[x-1][y]+pix2[x][y-1]-pix2[x-1][y-1]+pow(pix2[x][y],2)

##### XML Parsing #####
# This file format comes from the OpenCV project. It describes an "Haar cascade"
# A "cascade" is a succession of stages made of several weak classifiers. Each
# classifier describes an Haar Feature and a threshold to validate the feature.
cascade = etree.parse("haarcascade_frontalface_alt2.xml").getroot() \
                .find("haarcascade_frontalface_alt2")
stages = cascade.find("stages")

#A list is made to stock haar cascade's database
#This list is made by appending the lists represent the stages
#Each stage include some trees and a stage threshold
#Each tree include rects, node threshold, left/right value/node
listHaarCascade = []
for stage in stages :
    stageList = []

    trees = stage.find("trees")
    for tree in trees :
        treeArray = []
        for idx in range(2) :
            nodeList = []
            node = tree[idx+1]
            feature = node.find("feature")
            rects = feature.find("rects")

            rectsList = ()
            for rect in rects :
                rectTextSplit = rect.text.split()
                rectsList += (rectTextSplit,)
            nodeList.append(rectsList)
            nodeThreshold = float(node.find("threshold").text)
            nodeList.append(nodeThreshold)
            leftValue = node.find("left_val")
            nodeList.append(leftValue)
            rightValue = node.find("right_val")
            nodeList.append(rightValue)
            leftNode = node.find("left_node")
            nodeList.append(leftNode)
            rightNode = node.find("right_node")
            nodeList.append(rightNode)

            treeArray.append(nodeList)

        stageList.append(treeArray)

    stageThreshold = float(stage.find("stage_threshold").text)
    stageList.append(stageThreshold)

    listHaarCascade.append(stageList)

##### Detector #####
# This detector is made of a couple of nested loops. The first three loops
# define a "window" in which stages are tested. This window is scaled at 
# different sizes and carried at different positions. (scale, windowX, windowY)
listResult = []
scale, scaleFactor = 1, 1.25
windowWidth, windowHeight = (int(n) for n in cascade.find("size").text.split())
while windowWidth < imageWidth and windowHeight < imageHeight:
    windowWidth = windowHeight = int(scale*20)
    step = int(scale*2.4)
    windowX = 0
    while windowX < imageHeight-scale*24:
        windowY = 0
        while windowY < imageWidth-scale*24:

            ##### Stages #####
            # For each window, we successively test every stage of the cascade.
            # A stage is validated if its "stageSum" is greater than its
            # stageThreshold. All the stages must be validated to detect a face
            stagePass = True

            stageNb = 0
            for stage in listHaarCascade:
                stageNb = stageNb+1
                stageThreshold = stage[-1]
                stageSum = 0

                ##### Trees #####
                # A stage is made of several weak classifiers trees. This code
                # explores each trees from their root. (idx=0) and computes the
                # corresponding stageSum.
                for tree in stage[:-1]:
                    treeValue = 0
                    idx = 0

                    while True:
                        node = tree[idx]
                        rects = node[0]
                        nodeThreshold = node[1]
                        leftValue = node[2]
                        rightValue = node[3]
                        leftNode = node[4]
                        rightNode = node[5]

                        ##### Feature #####
                        # A feature is made of several rects. Its value comes
                        # from the linear combination of pixels intensity in
                        # those rects with their respective weights.
                        invArea=1/(windowWidth*windowHeight)
                        featureSum = 0
                        totalX=pix[windowX+windowWidth][windowY+windowHeight] \
                              +pix[windowX][windowY] \
                              -pix[windowX+windowWidth][windowY] \
                              -pix[windowX][windowY+windowHeight]
                        totalX2=pix2[windowX+windowWidth][windowY+windowHeight] \
                               +pix2[windowX][windowY] \
                               -pix2[windowX+windowWidth][windowY] \
                               -pix2[windowX][windowY+windowHeight]
                        vnorm=totalX2*invArea-pow(totalX*invArea,2)
                        if vnorm > 1: vnorm = math.sqrt(vnorm)
                        else        : vnorm = 1
                        for rect in rects:
                            x = int(scale*int(rect[0]))
                            y = int(scale*int(rect[1]))
                            width = int(scale*int(rect[2]))
                            height = int(scale*int(rect[3]))
                            weight = float(rect[4])
                            featureSum += weight * \
                              (pix[windowX+x+width][windowY+y+height] \
                             + pix[windowX+x][windowY+y] \
                             - pix[windowX+x+width][windowY+y] \
                             - pix[windowX+x][windowY+y+height])
                        if featureSum*invArea < nodeThreshold*vnorm:
                            if leftNode is None:
                                treeValue = float(leftValue.text)
                                break
                            else:
                                idx = int(leftNode.text)
                        else:
                            if rightNode is None:
                                treeValue = float(rightValue.text)
                                break
                            else:
                                idx = int(rightNode.text)

                    stageSum += treeValue
                
                stagePass = stageSum >= stageThreshold
                if not stagePass:
                    break

            if stagePass:
                # All stages are validated, it means we detected something !
                listResult.append((windowX, windowY, windowWidth, windowHeight))

            windowY += step
        windowX += step
    scale = scale * scaleFactor

##### Cover the detected face #####
# Draw a rectangle to cover the face

width = 3 #width of line
newList=[]

def picRect(listResult):
    maxX,maxY,maxWidth,maxHeight=listResult[0]
    newList.append((listResult[0]))
    for rect in listResult :
        x,y,width,height = rect
        #detected a new big rectange then add to new list
        if x+width<maxX or maxX+maxWidth<x or y+height<maxY or maxY+maxHeight<y:
            maxX=x
            maxY=y
            maxWidth=width
            maxHeight=height
            newList.append((rect))
    return newList

picRect(listResult)

for rect in newList :
    windowX,windowY,windowWidth,windowHeight = rect
    draw = ImageDraw.Draw(im)
    #addition half of width to have a perfect corner
    draw.line((windowX, windowY, windowX, windowY+windowHeight),
              (255,0,0,255),width)
    draw.line((windowX, windowY+width/2, windowX+windowWidth, windowY+width/2),
              (255,0,0,255),width)#addition half of width
    draw.line((windowX+windowWidth,windowY,windowX+windowWidth,windowY+windowHeight),
              (255,0,0,255),width)
    draw.line((windowX, windowY+windowHeight-width/2, windowX+windowWidth, 
               windowY+windowHeight-width/2),(255,0,0,255),width)
    del draw

im.show()
