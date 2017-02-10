#!/bin/bash

pkill python

bg
bg
bg

rm tosend.*
rm text*

python /home/ubuntu/one-to-many-N-segment/N_Segment_Data_Propagator.py
