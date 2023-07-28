#!/bin/sh -x
while read -r line; do
	echo "$line"
	python create_map.py $line 0
done < <(python grab_ids.py)