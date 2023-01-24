#!/bin/bash

containername="libro-exp"

docker ps -aq --filter "name=$containername" | grep -q . && docker stop $containername && docker rm $containername
docker run -dt --name $containername --env-file ./env.list -v $(pwd)/data:/root/data -v $(pwd)/scripts:/root/workspace -v $(pwd)/results:/root/results libro-env:latest 
docker exec -it $containername /bin/bash
