#!/bin/bash
if [ $1 == "CMD" ]; then
    docker run --rm --gpus all patent-rag-cuda:v1.1
else
    docker run -it --rm --gpus all --entrypoint /bin/bash patent-rag-cuda:v1.1
fi