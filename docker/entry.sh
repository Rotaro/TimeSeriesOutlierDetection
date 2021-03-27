#!/bin/sh
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
    exec /usr/bin/aws-lambda-rie /opt/conda/bin/python -m awslambdaric $1
else
    exec /opt/conda/bin/python -m awslambdaric $1
fi
