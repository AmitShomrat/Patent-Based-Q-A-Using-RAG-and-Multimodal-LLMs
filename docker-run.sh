#!/bin/bash
if [ $1 == "CMD" ]; then # CMD - run the CMD in the Dockerfile
    docker run -p 8000:8000 --rm --gpus all patent-rag-cuda:v1.3
else # default - run the container in interactive mode
    docker run -p 8000:8000 -it --rm --gpus all --entrypoint /bin/bash patent-rag-cuda:v1.3
fi