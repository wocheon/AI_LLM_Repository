#!/bin/bash


readarray -t index_list < <(curl -s "http://localhost:9200/_cat/indices?v" | grep -v .internal | grep -v status | gawk '{print $3}')

select index in "${index_list[@]}"; do
    [[ -n $index ]] && selected_index="$index" && break
done

echo "selected : $selected_index"
