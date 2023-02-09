#!/bin/bash

containername="libro-exp"

docker ps -aq --filter "name=$containername" | grep -q . && docker stop $containername && docker rm $containername
docker run -dt --name $containername -v $(pwd)/data:/root/data -v $(pwd)/scripts:/root/scripts -v $(pwd)/results:/root/results greenmon/libro-env:latest 
docker exec -it $containername /bin/bash
