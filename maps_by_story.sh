#!/bin/sh -x
for i in {1..22}; 
do
	python create_map.py $i 0
done