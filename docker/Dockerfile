# Copied from https://aws.amazon.com/blogs/aws/new-for-aws-lambda-container-image-support/
FROM continuumio/miniconda3:latest AS miniconda
ARG FUNCTION_DIR="/app/"

# Install aws-lambda-cpp build dependencies
RUN apt-get update && \
  apt-get install -y \
  g++ \
  make \
  cmake \
  unzip \
  libcurl4-openssl-dev \
  && rm -rf /var/lib/apt/lists/*

## Create function directory
RUN mkdir -p ${FUNCTION_DIR}

# Install environment
COPY environment.yml ${FUNCTION_DIR}
RUN conda env update --file "${FUNCTION_DIR}environment.yml"

RUN conda clean --all -y
RUN pip cache purge

# Copy application
COPY app/* ${FUNCTION_DIR}

# Add Lambda Runtime Interface Emulator and use a script in the ENTRYPOINT for simpler local runs
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie
COPY entry.sh /
RUN chmod 755 /usr/bin/aws-lambda-rie /entry.sh

WORKDIR ${FUNCTION_DIR}

ENTRYPOINT [ "/entry.sh" ]
CMD [ "app.handler" ]
